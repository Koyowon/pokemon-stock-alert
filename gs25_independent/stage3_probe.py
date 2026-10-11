#!/usr/bin/env python3
"""GS25 independent manual item identity check; read-only, no credentials.

Only publicly documented Daiso MCP REST actions. Does not log response bodies,
product/store names, store identifiers, addresses or stock numbers. No alerts.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/actions/query'
TARGET = '8800286275732'  # NOT VERIFIED as the desired product
TIMEOUT = 15
MAX_BYTES = 131072
SEARCH_TERMS = ('포켓몬 30주년', '30주년 기념팩', '포켓몬카드', '포켓몬')


def fetch(action, **params):
    url = BASE + '?' + urllib.parse.urlencode({'action': action, 'format': 'json', **params})
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'gs25-independent-identity-probe/2.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            status, body = res.status, res.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read(MAX_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, 'NETWORK_' + type(exc).__name__
    if status in (401, 403, 429):
        return None, 'HTTP_' + str(status)
    if status != 200:
        return None, 'HTTP_UNEXPECTED_' + str(status)
    if not body or len(body) > MAX_BYTES:
        return None, 'EMPTY_OR_OVERSIZE'
    try:
        obj = json.loads(body.decode('utf-8'))
    except (UnicodeError, ValueError):
        return None, 'INVALID_JSON'
    if not isinstance(obj, dict) or obj.get('success') is not True or obj.get('isError') or obj.get('error'):
        return None, 'API_UNCONFIRMED_SUCCESS'
    data = obj.get('data')
    if not isinstance(data, dict):
        return None, 'DATA_SCHEMA_UNKNOWN'
    return data, 'OK'


def code_of(item):
    value = item.get('itemCode') if isinstance(item, dict) else None
    return value if isinstance(value, str) and value.isdigit() else None


def numeric_stock(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 0
    if isinstance(value, float):
        return value.is_integer() and value >= 0
    if isinstance(value, str):
        return value.strip().isdigit()
    return False


def check_inventory(label, code):
    data, status = fetch('gs25CheckInventory', itemCode=code, storeKeyword='남원', storeLimit=3)
    if status != 'OK':
        print(f'{label}: {status}; STOCK_UNKNOWN')
        return
    same = data.get('itemCode') == code
    inv = data.get('inventory')
    stores = inv.get('stores') if isinstance(inv, dict) else None
    if not isinstance(stores, list):
        print(f'{label}: returned_code_matches={same}; STORES_SCHEMA_UNKNOWN; STOCK_UNKNOWN')
        return
    valid = sum(isinstance(s, dict) and numeric_stock(s.get('realStockQuantity')) for s in stores)
    print(f'{label}: returned_code_matches={same}; stores_returned={len(stores)}; numeric_stock_fields={valid}; STOCK_VALUES_HIDDEN')
    print(f'{label}: ITEM_IDENTITY_' + ('SEARCH_CONFIRMED' if label == 'TARGET_INVENTORY' else 'CONTROL_ONLY'))
    print(f'{label}: NO_STOCK_ALERTS; ZERO_NOT_INFERRED')


def main():
    print('GS25_IDENTITY_PROBE; MANUAL_ONLY; READ_ONLY; NO_SECRETS; NO_STATE_WRITES; NO_ALERTS')
    print('TARGET_CODE_ASSUMED=' + TARGET)
    control, status = fetch('gs25SearchProducts', keyword='코카콜라캔350ML', limit=5)
    control_codes = [code_of(x) for x in control.get('products', [])] if status == 'OK' and isinstance(control.get('products'), list) else []
    control_code = next((x for x in control_codes if x), None)
    print(f'CONTROL_SEARCH: status={status}; valid_product_codes={sum(bool(x) for x in control_codes)}')
    if control_code:
        check_inventory('CONTROL_INVENTORY', control_code)
    else:
        print('CONTROL_INVENTORY: SKIPPED_NO_SEARCH_CONFIRMED_CODE')

    found = False
    for idx, term in enumerate(SEARCH_TERMS, 1):
        data, state = fetch('gs25SearchProducts', keyword=term, limit=50)
        products = data.get('products') if state == 'OK' else None
        if not isinstance(products, list):
            print(f'TARGET_SEARCH_{idx}: status={state}; PRODUCTS_UNAVAILABLE')
            continue
        matches = sum(code_of(p) == TARGET for p in products)
        print(f'TARGET_SEARCH_{idx}: status=OK; products_returned={len(products)}; exact_code_matches={matches}')
        found = found or matches > 0
    print('TARGET_IDENTITY=' + ('SEARCH_CODE_CONFIRMED' if found else 'NOT_CONFIRMED'))
    if found:
        check_inventory('TARGET_INVENTORY', TARGET)
    else:
        print('TARGET_INVENTORY: SKIPPED_UNVERIFIED_ITEM_CODE')
        print('NEXT_ACTION: VERIFY_TARGET_CODE_FROM_GS25_PRODUCT_SEARCH_OR_PRODUCT_LABEL')
    print('NO_STOCK_ALERTS; ZERO_STOCK_NOT_INFERRED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
