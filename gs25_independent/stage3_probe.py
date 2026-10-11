#!/usr/bin/env python3
"""Read-only GS25 schema and item-code validation probe.

No secrets, no state writes, no alerts, no raw JSON, no store identifiers.
Only a small number of explicit GET requests to the public Daiso MCP API.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/actions/query'
TARGET = '8800286275732'  # Unverified product code
MAX_BODY = 131072
TIMEOUT = 15
SAFE_FIELDS = {
    'realStockQuantity', 'stockQuantity', 'remainQuantity',
    'quantity', 'stock', 'stockCount', 'availableQuantity',
    'inventoryQuantity', 'o2oRemainQuantity', 'stockStatus',
    'stockLabel', 'inStock', 'itemCode', 'count', 'total',
    'success', 'error', 'isError', 'message', 'code',
}
QUANTITY_FIELDS = {
    'realStockQuantity', 'stockQuantity', 'remainQuantity',
    'quantity', 'stock', 'stockCount', 'availableQuantity',
    'inventoryQuantity', 'o2oRemainQuantity',
}


def type_name(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, (int, float)):
        return 'number'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, list):
        return 'array'
    if isinstance(value, dict):
        return 'object'
    return 'other'


def request(label, action, **params):
    url = BASE + '?' + urllib.parse.urlencode({'action': action, 'format': 'json', **params})
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'gs25-independent-schema-probe/1.3',
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            raw = resp.read(MAX_BODY + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read(MAX_BODY + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f'{label}: NETWORK_ERROR type={type(exc).__name__}; STOCK_UNKNOWN')
        return
    print(f'{label}: HTTP_{status}')
    if status in (401, 403, 429):
        print(f'{label}: ACCESS_OR_RATE_LIMIT; STOCK_UNKNOWN')
        return
    if status != 200 or not raw or len(raw) > MAX_BODY:
        print(f'{label}: HTTP_OR_BODY_ERROR; STOCK_UNKNOWN')
        return
    try:
        root = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        print(f'{label}: NON_JSON_RESPONSE; STOCK_UNKNOWN')
        return
    if not isinstance(root, dict):
        print(f'{label}: UNEXPECTED_ROOT={type_name(root)}; STOCK_UNKNOWN')
        return
    print(f'{label}: root_safe_keys={",".join(sorted(SAFE_FIELDS & root.keys())) or "none"}')
    print(f'{label}: success_type={type_name(root.get("success"))}; success_true={root.get("success") is True}')
    if root.get('success') is not True or root.get('error') or root.get('isError'):
        print(f'{label}: API_NOT_CONFIRMED_SUCCESS; STOCK_UNKNOWN')
        return
    data = root.get('data')
    if not isinstance(data, dict):
        print(f'{label}: DATA_NOT_OBJECT; STOCK_UNKNOWN')
        return
    print(f'{label}: data_safe_keys={",".join(sorted(SAFE_FIELDS & data.keys())) or "none"}')
    if label == 'TARGET_PRODUCT_SEARCH':
        products = data.get('products')
        if not isinstance(products, list):
            print(f'{label}: PRODUCTS_ARRAY_MISSING; TARGET_CODE_UNVERIFIED')
            return
        exact = sum(isinstance(p, dict) and str(p.get('itemCode', '')) == TARGET for p in products)
        print(f'{label}: products_returned={len(products)}; exact_target_code_matches={exact}')
        print(f'{label}: TARGET_CODE_' + ('MATCH_IN_SEARCH_RESULTS' if exact else 'NOT_CONFIRMED_BY_SEARCH'))
    elif label == 'TARGET_INVENTORY_BY_CODE':
        code = data.get('itemCode')
        print(f'{label}: response_item_code_type={type_name(code)}; target_code_matches={str(code) == TARGET}')
        inv = data.get('inventory')
        if not isinstance(inv, dict):
            print(f'{label}: INVENTORY_OBJECT_MISSING; STOCK_UNKNOWN')
            return
        print(f'{label}: inventory_safe_keys={",".join(sorted(SAFE_FIELDS & inv.keys())) or "none"}')
        stores = inv.get('stores')
        if not isinstance(stores, list):
            print(f'{label}: STORES_ARRAY_MISSING; STOCK_UNKNOWN')
            return
        print(f'{label}: stores_returned={len(stores)}')
        # Inspect up to 3 entries without printing store names, IDs, addresses, or values.
        for i, store in enumerate(stores[:3]):
            if not isinstance(store, dict):
                print(f'{label}: store_sample_{i}_type={type_name(store)}')
                continue
            print(f'{label}: store_sample_{i}_safe_keys={",".join(sorted(SAFE_FIELDS & store.keys())) or "none"}; other_key_count={len(store.keys() - SAFE_FIELDS)}')
            for key in sorted(QUANTITY_FIELDS & store.keys()):
                val = store[key]
                numeric = (isinstance(val, (int, float)) and not isinstance(val, bool)) or (isinstance(val, str) and val.strip().isdigit())
                print(f'{label}: store_sample_{i}.{key}: type={type_name(val)} numeric_compatible={numeric} value_hidden')
            for key in ('stockStatus', 'stockLabel', 'inStock'):
                if key in store:
                    print(f'{label}: store_sample_{i}.{key}: type={type_name(store[key])} value_hidden')
        print(f'{label}: STORE_COUNTS_ARE_NOT_QUANTITIES; STOCK_NOT_VERIFIED')
    else:
        products = data.get('products')
        print(f'{label}: products_returned={len(products) if isinstance(products, list) else "unavailable"}')


def main():
    print('GS25_STAGE3_FIELD_AUDIT; READ_ONLY; NO_SECRETS; NO_STATE_WRITES; NO_ALERTS')
    print('TARGET_CODE_ASSUMED=' + TARGET)
    request('CONTROL_PRODUCT_SEARCH', 'gs25SearchProducts', keyword='코카콜라캔350ML', limit=3)
    request('TARGET_PRODUCT_SEARCH', 'gs25SearchProducts', keyword='포켓몬', limit=20)
    request('TARGET_INVENTORY_BY_CODE', 'gs25CheckInventory', itemCode=TARGET, storeKeyword='남원', storeLimit=3)
    print('GS25_STOCK_NOT_VERIFIED; ZERO_STOCK_NOT_INFERRED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
