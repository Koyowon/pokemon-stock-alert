#!/usr/bin/env python3
"""Manual GS25 product identity audit: read only; no state writes or alerts."""
import json
import urllib.parse
import urllib.request
import urllib.error

BASE = 'https://mcp.aka.page/api/actions/query'
TARGET = '8800286275732'  # Assumed, not verified
TERMS = ('8800286275732', '포켓몬 30주년', '30주년 기념팩', '포켓몬카드', '포켓몬', '30주년', '기념팩', 'MEGA')
NAME_KEYS = ('itemName', 'productName', 'name', 'goodsName', 'itemNm', 'productNm')
CODE_KEYS = ('itemCode', 'barcode', 'barCode', 'ean', 'gtin')
HINTS = ('포켓몬', 'pokemon', '30주년', '30th', '기념팩', 'mega')

def fetch(action, **params):
    url = BASE + '?' + urllib.parse.urlencode({'action': action, 'format': 'json', **params})
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'gs25-manual-identity-audit/2.1'})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            status, body = res.status, res.read(262145)
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read(262145)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, 'NETWORK_' + type(exc).__name__
    if status != 200:
        return None, 'HTTP_' + str(status)
    if not body or len(body) > 262144:
        return None, 'EMPTY_OR_OVERSIZE'
    try:
        obj = json.loads(body.decode('utf-8'))
    except (UnicodeError, ValueError):
        return None, 'INVALID_JSON'
    if not isinstance(obj, dict) or obj.get('success') is not True or obj.get('error') or obj.get('isError'):
        return None, 'API_NOT_CONFIRMED_SUCCESS'
    data = obj.get('data')
    return (data, 'OK') if isinstance(data, dict) else (None, 'DATA_SCHEMA_UNKNOWN')

def exact_code(p):
    return isinstance(p, dict) and any(str(p.get(k, '')).strip() == TARGET for k in CODE_KEYS)

def name_hint(p):
    if not isinstance(p, dict):
        return 'NOT_PRESENT'
    names = [p[k] for k in NAME_KEYS if isinstance(p.get(k), str)]
    if not names:
        return 'NOT_PRESENT'
    return 'TARGET_RELATED_HINT' if any(h in ' '.join(names).lower() for h in HINTS) else 'NO_TARGET_HINT'

def main():
    print('GS25_CATALOG_IDENTITY_AUDIT; MANUAL_ONLY; READ_ONLY; NO_SECRETS; NO_STATE_WRITES; NO_ALERTS')
    print('TARGET_CODE_ASSUMED=' + TARGET)
    matched = []
    for i, term in enumerate(TERMS, 1):
        data, status = fetch('gs25SearchProducts', keyword=term, limit=100)
        products = data.get('products') if data else None
        if not isinstance(products, list):
            print(f'SEARCH_{i}: status={status}; products=UNKNOWN')
            continue
        hits = [p for p in products if exact_code(p)]
        matched.extend(hits)
        print(f'SEARCH_{i}: status=OK; products={len(products)}; exact_code_matches={len(hits)}; result_limit_reached={len(products)>=100}')
        for p in hits[:2]:
            print(f'SEARCH_{i}: MATCH_NAME_EVIDENCE={name_hint(p)}')
    data, status = fetch('gs25CheckInventory', itemCode=TARGET, storeKeyword='남원', storeLimit=1)
    if status != 'OK':
        print(f'DIRECT_LOOKUP: status={status}; IDENTITY_UNKNOWN')
    else:
        inv = data.get('inventory')
        stores = inv.get('stores') if isinstance(inv, dict) else None
        print(f'DIRECT_LOOKUP: status=OK; echoed_code_matches={str(data.get("itemCode")) == TARGET}; '
              f'metadata_name_hint={name_hint(data)}; stores_array_present={isinstance(stores,list)}; '
              f'stores_count={len(stores) if isinstance(stores,list) else "UNKNOWN"}')
        print('DIRECT_LOOKUP: STOCK_VALUES_HIDDEN; ECHOED_CODE_IS_NOT_IDENTITY_PROOF')
    if matched and any(name_hint(p) == 'TARGET_RELATED_HINT' for p in matched):
        print('TARGET_IDENTITY=CATALOG_CODE_AND_NAME_HINT_MATCH; HUMAN_CONFIRMATION_RECOMMENDED')
    elif matched:
        print('TARGET_IDENTITY=CATALOG_CODE_MATCH_NAME_UNCONFIRMED')
    else:
        print('TARGET_IDENTITY=NOT_CONFIRMED; ABSENCE_IN_SEARCH_IS_NOT_PROOF_OF_INVALID_CODE')
    print('NO_STOCK_ALERTS; ZERO_STOCK_NOT_INFERRED')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
