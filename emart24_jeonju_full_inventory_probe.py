"""Read-only full Jeonju inventory diagnostic; never changes state or sends alerts."""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

SEED = Path(__file__).resolve().parent / 'emart24_jeonju_seed.json'
API = 'https://mcp.aka.page/api/emart24/inventory'
PLU = '8800286275732'
BATCH_SIZE = 3
MAX_REQUESTS = 21
DELAY_SECONDS = 2
TIMEOUT_SECONDS = 12


def stores():
    data = json.loads(SEED.read_text(encoding='utf-8'))
    if data.get('version') != 1 or data.get('region_id') != 'jeonju':
        raise ValueError('Invalid Jeonju seed metadata')
    rows = data.get('stores')
    if not isinstance(rows, dict) or len(rows) != 63:
        raise ValueError('Expected 63 seed stores')
    selected = []
    districts = Counter()
    for code, item in sorted(rows.items()):
        if not isinstance(code, str) or not code.isdigit() or not isinstance(item, dict):
            raise ValueError('Invalid store entry')
        name, address = item.get('name'), item.get('address')
        if not isinstance(name, str) or not name.strip() or not isinstance(address, str):
            raise ValueError('Invalid name or address')
        found = [d for d in ('완산구', '덕진구') if address.startswith('전북특별자치도 전주시 ' + d + ' ')]
        if len(found) != 1:
            raise ValueError('Invalid district: ' + code)
        selected.append((code, name, found[0]))
        districts[found[0]] += 1
    if districts != {'완산구': 27, '덕진구': 36}:
        raise ValueError('Unexpected district totals')
    return selected


def query(codes):
    params = urllib.parse.urlencode({'pluCd': PLU, 'bizNoArr': ','.join(codes)})
    request = urllib.request.Request(API + '?' + params, headers={
        'User-Agent': 'PokemonStockMonitor/1.1', 'Accept': 'application/json'
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        return {}, 'HTTP_' + str(exc.code)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {}, 'REQUEST_ERROR_' + type(exc).__name__
    if not isinstance(payload, dict) or payload.get('success') is not True:
        return {}, 'API_UNSUCCESSFUL'
    data = payload.get('data')
    if not isinstance(data, dict) or not isinstance(data.get('stores'), list):
        return {}, 'INVALID_PAYLOAD'
    results = {}
    for row in data['stores']:
        if not isinstance(row, dict):
            continue
        code = str(row.get('bizNo') or '').strip()
        if code not in codes:
            continue
        qty = row.get('bizQty')
        if type(qty) is int and qty >= 0:
            results[code] = ('NUMERIC_QTY', qty)
        elif code not in results or results[code][0] != 'NUMERIC_QTY':
            results[code] = ('NULL_OR_INVALID_QTY', None)
    return results, None


def main():
    selected = stores()
    counts = Counter()
    district_counts = {'완산구': Counter(), '덕진구': Counter()}
    started = time.monotonic()
    print('EMART24_JEONJU_FULL_READ_ONLY_PROBE_START', flush=True)
    print(f'PRODUCT_PLU={PLU} STORES=63 BATCH_SIZE=3 REQUESTS_MAX={MAX_REQUESTS}', flush=True)
    for index, start in enumerate(range(0, len(selected), BATCH_SIZE), 1):
        if index > MAX_REQUESTS:
            raise RuntimeError('Request budget exceeded')
        batch = selected[start:start+BATCH_SIZE]
        result, error = query([code for code, _, _ in batch])
        print(f'BATCH={index}/{MAX_REQUESTS} STATUS={error or "RESPONSE_OK"}', flush=True)
        for code, name, district in batch:
            status, qty = (error, None) if error else result.get(code, ('MISSING_IN_RESPONSE', None))
            counts[status] += 1
            district_counts[district][status] += 1
            print(f'DISTRICT={district} STORE={code} NAME={name} STATUS={status} QTY={qty if qty is not None else "UNKNOWN"}', flush=True)
        if start+BATCH_SIZE < len(selected):
            time.sleep(DELAY_SECONDS)
    print('SUMMARY_TOTAL ' + ' '.join(f'{k}={v}' for k, v in sorted(counts.items())), flush=True)
    for district, group in district_counts.items():
        print('SUMMARY_DISTRICT ' + district + ' ' + ' '.join(f'{k}={v}' for k, v in sorted(group.items())), flush=True)
    print(f'SUMMARY_REQUESTS=21 ELAPSED_SECONDS={time.monotonic()-started:.1f}', flush=True)
    print('EMART24_JEONJU_FULL_READ_ONLY_PROBE_FINISHED', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f'PROBE_ERROR: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
