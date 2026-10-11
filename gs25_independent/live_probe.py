#!/usr/bin/env python3
"""GS25 four-region read-only manual stock sample. Third-party API; no alerts/state."""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = 'https://mcp.aka.page/api/actions/query'
CONFIG = Path(__file__).with_name('config.json')
# These are store-name searches, NOT guaranteed geographic coverage.
KEYWORDS = {
    'namwon': ['남원', 'GS25남원', '남원시'],
    'asan': ['아산', 'GS25아산', '배방', '탕정', '온양'],
    'jeonju': ['전주', 'GS25전주', '효자', '송천', '서신'],
    'jeju': ['GS25제주', '제주봉성점', '제주', '제주시', '애월', '연동', '노형', '서귀포'],
}

def request(code, keyword):
    url = API + '?' + urllib.parse.urlencode({
        'action': 'gs25CheckInventory', 'format': 'json',
        'itemCode': code, 'storeKeyword': keyword, 'storeLimit': 100,
    })
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json', 'User-Agent': 'gs25-four-region-manual-probe/1.0',
    })
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = response.read(800001)
                if response.status != 200 or len(raw) > 800000:
                    raise ValueError('BAD_HTTP_OR_SIZE')
            root = json.loads(raw.decode('utf-8'))
            if not isinstance(root, dict) or root.get('success') is not True or root.get('error') or root.get('isError'):
                raise ValueError('API_NOT_SUCCESS')
            data = root.get('data')
            inv = data.get('inventory') if isinstance(data, dict) else None
            rows = inv.get('stores') if isinstance(inv, dict) else None
            if not isinstance(rows, list):
                raise ValueError('MISSING_STORES')
            return rows, None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, UnicodeError) as exc:
            error = type(exc).__name__
            if attempt == 0:
                time.sleep(1)
    return [], error

def quantity(row):
    val = row.get('realStockQuantity')
    if type(val) is int and val >= 0:
        return val
    if isinstance(val, str) and re.fullmatch(r'\d+', val):
        return int(val)
    return None

def clean(value):
    return re.sub(r'\s+', ' ', ''.join(c if c.isprintable() else ' ' for c in str(value)))[:90]

def main():
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    assert config.get('provider') == 'GS25'
    code = config['item_code']
    assert re.fullmatch(r'\d{8,14}', code)
    print('GS25_FOUR_REGION_MANUAL_SAMPLE; READ_ONLY; NO_ALERTS; NO_STATE_WRITES')
    print('THIRD_PARTY_API; PRODUCT_IDENTITY_NOT_INDEPENDENTLY_VERIFIED')
    print('CODE=' + code)
    failures = 0
    total_positive = 0
    for region in config['regions']:
        rid = region['id']
        if not region.get('enabled'):
            continue
        if rid not in KEYWORDS:
            print('REGION_UNKNOWN ' + clean(rid))
            failures += 1
            continue
        seen = {}
        for term in KEYWORDS[rid]:
            rows, err = request(code, term)
            if err:
                failures += 1
                print(f'QUERY region={rid}; term={term}; status=ERROR_{err}')
                continue
            print(f'QUERY region={rid}; term={term}; returned={len(rows)}; possible_limit={len(rows)>=100}')
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = clean(row.get('storeName') or row.get('name') or '')
                sid = clean(row.get('storeCode') or '')
                if not name or not sid:
                    continue
                q = quantity(row)
                # Duplicate store across queries: preserve largest reported quantity;
                # this is a sampling summary, not a synchronized snapshot.
                prev = seen.get(sid)
                if prev is None or (q is not None and (prev[1] is None or q > prev[1])):
                    seen[sid] = (name, q)
        positive = sorted([(name, sid, q) for sid, (name, q) in seen.items() if q is not None and q > 0], key=lambda x: (-x[2], x[0]))
        total_positive += len(positive)
        print(f'REGION_SUMMARY region={rid}; unique_stores={len(seen)}; positive_stores={len(positive)}; keyword_sample_only=True')
        for name, sid, q in positive[:60]:
            print(f'POSITIVE region={rid}; store={name}; storeCode={sid}; api_quantity={q}')
        if len(positive) > 60:
            print(f'POSITIVE_TRUNCATED region={rid}; remaining={len(positive)-60}')
    print(f'FINAL positive_store_rows={total_positive}; request_failures={failures}')
    print('NOT_A_COMPLETE_GEOGRAPHIC_SCAN; QUANTITIES_NOT_REALTIME_GUARANTEED')
    print('NO_ALERTS; NO_STATE_WRITES; NO_SCHEDULE_CHANGES')
    return 0 if failures == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
