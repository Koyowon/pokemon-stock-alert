#!/usr/bin/env python3
"""Read-only GS25 Jeju candidate inventory diagnostic; no alerts or state writes."""
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

BASE = 'https://mcp.aka.page/api/actions/query'
CODE = '8800286275732'  # UNVERIFIED product identity
KEYWORDS = ('제주', '제주시', '서귀포', '애월')
MAX_BYTES = 512_000


def request_inventory(keyword):
    query = urllib.parse.urlencode({
        'action': 'gs25CheckInventory',
        'format': 'json',
        'itemCode': CODE,
        'storeKeyword': keyword,
        'storeLimit': 100,
    })
    req = urllib.request.Request(BASE + '?' + query, headers={
        'Accept': 'application/json',
        'User-Agent': 'gs25-jeju-manual-stock-diagnostic/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read(MAX_BYTES + 1)
            if response.status != 200 or len(body) > MAX_BYTES:
                return None, 'BAD_RESPONSE'
    except urllib.error.HTTPError as exc:
        return None, f'HTTP_{exc.code}'
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f'NETWORK_{type(exc).__name__}'
    try:
        root = json.loads(body.decode('utf-8'))
    except (UnicodeError, ValueError):
        return None, 'INVALID_JSON'
    if not isinstance(root, dict) or root.get('success') is not True or root.get('error') or root.get('isError'):
        return None, 'API_UNCONFIRMED'
    data = root.get('data')
    inventory = data.get('inventory') if isinstance(data, dict) else None
    stores = inventory.get('stores') if isinstance(inventory, dict) else None
    if not isinstance(stores, list):
        return None, 'STORES_MISSING'
    return stores, 'OK'


def label(store):
    for key in ('storeName', 'name', 'shopName', 'storeNm'):
        value = store.get(key)
        if isinstance(value, str) and value.strip():
            return ' '.join(value.split())[:55]
    return '(store_name_missing)'


def quantity(store):
    value = store.get('realStockQuantity')
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0 and float(value).is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def main():
    print('GS25_JEJU_MANUAL_PROBE; READ_ONLY; NO_ALERTS; NO_STATE_WRITES')
    print(f'ITEM_CODE={CODE}; PRODUCT_IDENTITY=UNVERIFIED')
    print('PERCENT_70=HYPOTHESIS_ONLY; QUANTITIES_ARE_RAW_API_VALUES')
    unique = {}
    errors = 0
    for keyword in KEYWORDS:
        stores, status = request_inventory(keyword)
        if stores is None:
            print(f'QUERY keyword={keyword}; status={status}')
            errors += 1
            continue
        print(f'QUERY keyword={keyword}; status=OK; returned_stores={len(stores)}; limit_may_apply={len(stores)>=100}')
        for store in stores:
            if not isinstance(store, dict):
                continue
            name, qty = label(store), quantity(store)
            identifier = str(store.get('storeCode') or store.get('storeId') or store.get('storeCd') or name)
            old = unique.get(identifier)
            if old is None or (old[1] is None and qty is not None):
                unique[identifier] = (name, qty)
    values = [qty for _, qty in unique.values() if qty is not None]
    positives = sorted(((name, qty) for name, qty in unique.values() if qty is not None and qty > 0), key=lambda row: (-row[1], row[0]))
    print(f'SUMMARY unique_stores={len(unique)}; numeric_quantities={len(values)}; positive={len(positives)}; zero={sum(v==0 for v in values)}; missing={len(unique)-len(values)}; failed_queries={errors}')
    print('POSITIVE_QUANTITY_COUNTS=' + json.dumps(dict(sorted(Counter(q for _, q in positives).items())), ensure_ascii=False))
    print(f'POSITIVE_MULTIPLES_OF_14={sum(q%14==0 for _, q in positives)}; POSITIVE_TOTAL={len(positives)}')
    for name, qty in positives[:60]:
        safe = ''.join(c if c.isprintable() else ' ' for c in name)
        print(f'POSITIVE_STORE name={safe}; raw_quantity={qty}; multiple_of_14={qty%14==0}')
    if len(positives) > 60:
        print(f'POSITIVE_STORES_OMITTED={len(positives)-60}')
    print('CAUTION: API may echo arbitrary item codes; positive results do not verify product identity.')
    print('CAUTION: 0 does not prove physical stockout; no conversion to actual packs performed.')
    print('NO_STOCK_ALERTS; NO_STATE_CHANGES; NO_AUTOMATIC_SCHEDULE')
    return 0 if errors == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
