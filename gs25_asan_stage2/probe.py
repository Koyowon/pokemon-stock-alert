"""Isolated GS25 Asan API probe: no production imports, no Telegram, no repo writes."""
import argparse
import csv
import datetime as dt
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from asan_expansion_safe import Limits, scan

API = 'https://mcp.aka.page/api/actions/query'
ITEM = '8800286275732'  # Product identity still needs verification.
HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get('GITHUB_WORKSPACE', '.')).resolve() / 'asan_stage2_artifacts'


def normalized(name):
    s = re.sub(r'\s+', '', str(name)).replace('GS25', '')
    return s


def load_candidates(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    result = {}
    for row in rows:
        name = row['store_name'].strip()
        if not name:
            continue
        key = normalized(name)
        if key in result and result[key]['address'] != row['address']:
            # Ambiguous name -> do not silently merge distinct addresses.
            result[key]['ambiguous'] = True
        else:
            result[key] = dict(row, ambiguous=False)
    return result


def api_query(term, *, opener=urllib.request.urlopen, timeout=6):
    params = urllib.parse.urlencode({'action': 'gs25CheckInventory', 'format': 'json',
        'itemCode': ITEM, 'storeKeyword': term, 'storeLimit': 100})
    req = urllib.request.Request(API + '?' + params, headers={'Accept': 'application/json', 'User-Agent': 'gs25-asan-readonly-probe/1.0'})
    with opener(req, timeout=timeout) as resp:
        raw = resp.read(800001)
        if getattr(resp, 'status', 200) != 200 or len(raw) > 800000:
            raise ValueError('HTTP_OR_SIZE')
    doc = json.loads(raw)
    if not isinstance(doc, dict) or doc.get('success') is not True or doc.get('error') or doc.get('isError'):
        raise ValueError('API_FAILURE')
    inv = doc.get('data', {}).get('inventory')
    rows = inv.get('stores') if isinstance(inv, dict) else None
    if not isinstance(rows, list):
        raise ValueError('INVALID_STORES')
    if len(rows) >= 100:
        raise ValueError('TRUNCATED_STORES')
    return rows


def evaluate(rows, candidates, existing_codes):
    """Name/code discovery only; NEVER implies address verification or approval."""
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code, name = row.get('storeCode'), row.get('storeName') or row.get('name')
        q = row.get('realStockQuantity')
        if not isinstance(code, str) or not re.fullmatch(r'V[A-Z0-9]{4}', code):
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if type(q) is not int or q < 0:
            continue
        key = normalized(name)
        candidate = candidates.get(key)
        if not candidate or candidate['ambiguous']:
            continue
        if code in found and (found[code]['quantity'] != q or found[code]['name'] != name):
            raise ValueError('CONFLICTING_CODE')
        found[code] = {'name': name, 'quantity': q, 'candidate': candidate}
    results = []
    for code, entry in sorted(found.items()):
        results.append({'store_code': code, 'api_name': entry['name'],
            'candidate_name': entry['candidate']['store_name'], 'candidate_address': entry['candidate']['address'],
            'quantity_at_probe': entry['quantity'], 'existing_13': 'yes' if code in existing_codes else 'no',
            'name_matched': 'yes', 'code_address_verified': 'no', 'approval': 'pending',
            'status': 'existing' if code in existing_codes else 'name_only_candidate'})
    return results


def run(args, *, query=api_query):
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = load_candidates(HERE / 'candidates.csv')
    existing_codes = {'V4537','V5K43','V6N57','VD542','VDQ67','VEP77','VFK62','VFM85','VFZ93','VJE48','VJH65','VM481','VY928'}
    # Never scan existing 13. Exclude all entries marked as already monitored.
    pending = [v for v in candidates.values() if v['status'] != 'existing_monitor' and not v['ambiguous']]
    pending.sort(key=lambda x: x['store_name'])
    start = args.batch * args.batch_size
    batch = pending[start:start + args.batch_size]
    if not batch:
        raise ValueError('EMPTY_BATCH')
    terms = [x['store_name'] for x in batch]
    gathered = []
    calls = 0
    def controlled(term):
        nonlocal calls
        calls += 1
        rows = query(term)
        gathered.extend(rows)
        return rows
    # Prototype engine remains the sole state/alert decision point. Empty allowed
    # codes deliberately prevents monitoring/approvals; discovery is evaluated separately.
    prior = {}
    if args.prior_baseline:
        with open(args.prior_baseline, encoding='utf-8') as f:
            prior_doc = json.load(f)
        if prior_doc.get('item_code') != ITEM or prior_doc.get('source') != 'gs25_asan_stage2':
            raise ValueError('BASELINE_IDENTITY_MISMATCH')
        prior = prior_doc['stores']
    config = {'enabled': True, 'alerts_enabled': False, 'approved_codes': []}
    _, alerts, report = scan(config, prior, terms, controlled,
        limits=Limits(max_queries=args.batch_size, max_seconds=args.max_seconds, max_results_per_query=100))
    # Only publish matches and baseline if the whole batch succeeded.
    matches = evaluate(gathered, candidates, existing_codes) if report['status'] == 'OK' else []
    # Baseline from valid exact-name matches, independent of production state.
    baseline = dict(prior)
    if report['status'] == 'OK':
        for row in matches:
            if row['existing_13'] == 'no':
                baseline[row['store_code']] = {'name': row['api_name'], 'quantity': row['quantity_at_probe']}
    fieldnames = ['store_code','api_name','candidate_name','candidate_address','quantity_at_probe','existing_13','name_matched','code_address_verified','approval','status']
    with (OUT / 'matches.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader(); writer.writerows(matches)
    with (OUT / 'baseline.json').open('w', encoding='utf-8') as f:
        json.dump({'source':'gs25_asan_stage2','item_code':ITEM,'stores':baseline,
            'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'status':report['status']}, f, ensure_ascii=False, indent=2)
    with (OUT / 'report.json').open('w', encoding='utf-8') as f:
        json.dump({'batch':args.batch,'requested_names':terms,'api_calls':calls,'report':report,
            'matches':len(matches),'alerts_sent':0,'approved':0,'production_modified':False,
            'warning':'Name match does not verify store-code/address pairing. Artifact baseline is NOT production state.'},f,ensure_ascii=False,indent=2)
    print('ASAN_STAGE2',json.dumps({'status':report['status'],'queries':calls,'matches':len(matches),'alerts':len(alerts),'batch':args.batch},ensure_ascii=False))
    return 0 if report['status'] == 'OK' else 2


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--batch',type=int,default=0)
    parser.add_argument('--batch-size',type=int,default=10)
    parser.add_argument('--max-seconds',type=float,default=90)
    parser.add_argument('--prior-baseline',default='')
    args=parser.parse_args()
    if args.batch < 0 or not 1 <= args.batch_size <= 12 or not 10 <= args.max_seconds <= 120:
        parser.error('unsafe limits')
    raise SystemExit(run(args))

if __name__=='__main__':
    main()
