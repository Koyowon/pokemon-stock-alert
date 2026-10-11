"""Read-only, bounded Emart24 inventory diagnostic for Jeonju seed stores.

Does not import monitor.py, access Telegram, or write any repository files.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEED_PATH = ROOT / 'emart24_jeonju_seed.json'
API_URL = 'https://mcp.aka.page/api/emart24/inventory'
PLU = '8800286275732'
PER_DISTRICT = 3


def selected_stores():
    doc = json.loads(SEED_PATH.read_text(encoding='utf-8'))
    if doc.get('version') != 1 or doc.get('region_id') != 'jeonju':
        raise ValueError('Invalid Jeonju seed metadata')
    stores = doc.get('stores')
    if not isinstance(stores, dict) or len(stores) != 63:
        raise ValueError('Expected exactly 63 Jeonju seed stores')
    groups = {'완산구': [], '덕진구': []}
    for code, item in sorted(stores.items()):
        if not isinstance(code, str) or not code.isdigit() or not isinstance(item, dict):
            raise ValueError('Invalid seed store entry')
        addr = item.get('address', '')
        name = item.get('name', '')
        if not isinstance(addr, str) or not isinstance(name, str) or not name.strip():
            raise ValueError('Invalid seed store details')
        matches = [district for district in groups if addr.startswith(f'전북특별자치도 전주시 {district} ')]
        if len(matches) != 1:
            raise ValueError(f'Unexpected store district: {code}')
        groups[matches[0]].append((code, name))
    if len(groups['완산구']) != 27 or len(groups['덕진구']) != 36:
        raise ValueError('Unexpected district totals')
    return [(district, code, name) for district, rows in groups.items() for code, name in rows[:PER_DISTRICT]]


def probe(code):
    query = urllib.parse.urlencode({'pluCd': PLU, 'bizNoArr': code})
    request = urllib.request.Request(API_URL + '?' + query, headers={
        'User-Agent': 'PokemonStockMonitor/1.1', 'Accept': 'application/json'
    })
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        return f'HTTP_{exc.code}', None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return f'REQUEST_ERROR_{type(exc).__name__}', None
    if not isinstance(data, dict) or data.get('success') is not True:
        return 'API_UNSUCCESSFUL', None
    payload = data.get('data')
    if not isinstance(payload, dict) or not isinstance(payload.get('stores'), list):
        return 'INVALID_PAYLOAD', None
    matching = [row for row in payload['stores'] if isinstance(row, dict) and str(row.get('bizNo', '')).strip() == code]
    if not matching:
        return 'MISSING_IN_RESPONSE', None
    qty = matching[0].get('bizQty')
    if type(qty) is int and qty >= 0:
        return 'NUMERIC_QTY', qty
    return 'NULL_OR_INVALID_QTY', None


def main():
    stores = selected_stores()
    print('EMART24_JEONJU_READ_ONLY_PROBE_START', flush=True)
    print(f'PRODUCT_PLU={PLU} SAMPLE_SIZE={len(stores)} REQUESTS_MAX={len(stores)}', flush=True)
    statuses = Counter()
    for index, (district, code, name) in enumerate(stores):
        status, qty = probe(code)
        statuses[status] += 1
        print(f'DISTRICT={district} STORE={code} NAME={name} STATUS={status} QTY={qty if qty is not None else "UNKNOWN"}', flush=True)
        if index + 1 < len(stores):
            time.sleep(2)
    print('SUMMARY ' + ' '.join(f'{key}={value}' for key, value in sorted(statuses.items())), flush=True)
    print('EMART24_JEONJU_READ_ONLY_PROBE_FINISHED', flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'PROBE_SETUP_ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)
