#!/usr/bin/env python3
"""Manual, read-only GS25 REST JSON structure audit; never print response values.

This is NOT a stock monitor. No credentials, alerts, state writes, or retries.
"""
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/actions/query'
TARGET = '8800286275732'  # Unverified item code
TIMEOUT = 15
MAX_BODY = 131072
MAX_DEPTH = 4
MAX_KEYS = 14

# Only known generic schema keys are ever printed; unknown keys are counted.
SAFE_KEYS = frozenset({
    'success', 'ok', 'status', 'code', 'error', 'errors', 'isError',
    'data', 'result', 'results', 'items', 'products', 'stores',
    'inventory', 'inventories', 'stock', 'stocks', 'quantity',
    'stockQuantity', 'stockQty', 'remainingQuantity', 'total',
    'count', 'totalCount', 'hasMore', 'pagination', 'meta',
    'content', 'structuredContent', 'productList', 'storeList',
    'storeInventory', 'itemCode', 'storeCode', 'storeId',
})
# Never print store IDs, item names, location, error messages or any scalar values.
PRODUCT_LIST_KEYS = {'items', 'products', 'productList', 'results'}
STORE_LIST_KEYS = {'stores', 'storeList', 'inventories'}
QUANTITY_KEYS = {'quantity', 'stockQuantity', 'stockQty', 'remainingQuantity'}


def typename(v):
    if v is None: return 'null'
    if isinstance(v, bool): return 'bool'
    if isinstance(v, dict): return 'object'
    if isinstance(v, list): return 'array'
    if isinstance(v, (int, float)): return 'number'
    if isinstance(v, str): return 'string'
    return 'other'


def inspect_tree(value, path='root', depth=0, stats=None):
    """Inspect bounded shape, never printing raw/unknown keys or values."""
    if stats is None:
        stats = {'product_arrays': 0, 'store_arrays': 0, 'quantity_fields': 0,
                 'numeric_quantity_fields': 0, 'error_fields': 0, 'nodes': 0}
    if depth > MAX_DEPTH or stats['nodes'] >= 75:
        return stats
    stats['nodes'] += 1
    if isinstance(value, dict):
        keys = sorted(k for k in value if isinstance(k, str) and k in SAFE_KEYS)
        unknown = len(value) - len(keys)
        print(f'SHAPE {path}: object fields={len(value)} safe_keys={",".join(keys[:MAX_KEYS]) or "none"} '
              f'other_keys={unknown} safe_keys_truncated={max(0,len(keys)-MAX_KEYS)}')
        for key in keys[:MAX_KEYS]:
            child = value[key]
            if key in ('error', 'errors', 'isError') and child is not None:
                stats['error_fields'] += 1  # Presence, not truthiness
            if key in PRODUCT_LIST_KEYS and isinstance(child, list):
                stats['product_arrays'] += 1
                print(f'INDICATOR {path}.{key}: array_present count={len(child)}')
            if key in STORE_LIST_KEYS and isinstance(child, list):
                stats['store_arrays'] += 1
                print(f'INDICATOR {path}.{key}: array_present count={len(child)}')
            if key in QUANTITY_KEYS:
                stats['quantity_fields'] += 1
                if isinstance(child, (int, float)) and not isinstance(child, bool):
                    stats['numeric_quantity_fields'] += 1
                print(f'INDICATOR {path}.{key}: type={typename(child)} value_hidden')
            if isinstance(child, (dict, list)):
                inspect_tree(child, path + '.' + key, depth + 1, stats)
            else:
                print(f'FIELD {path}.{key}: type={typename(child)} value_hidden')
    elif isinstance(value, list):
        print(f'SHAPE {path}: array count={len(value)}')
        if value:
            inspect_tree(value[0], path + '[sample]', depth + 1, stats)
    else:
        print(f'SHAPE {path}: type={typename(value)} value_hidden')
    return stats


def probe(label, action, **params):
    query = urllib.parse.urlencode({'action': action, 'format': 'json', **params})
    request = urllib.request.Request(BASE + '?' + query, headers={
        'Accept': 'application/json',
        'User-Agent': 'gs25-independent-shape-audit/1.2',
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            status = response.status
            content_type = response.headers.get('Content-Type', '').split(';')[0].lower()
            raw = response.read(MAX_BODY + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get('Content-Type', '').split(';')[0].lower()
        raw = exc.read(MAX_BODY + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f'{label}: NETWORK_ERROR type={type(exc).__name__}; STOCK_UNKNOWN')
        return 'NETWORK_ERROR'
    print(f'{label}: HTTP_{status} content_type={content_type if content_type in ("application/json", "text/html") else "other"}')
    if status in (401, 403, 429):
        result = {401: 'AUTH_REQUIRED', 403: 'ACCESS_DENIED', 429: 'RATE_LIMITED'}[status]
    elif status != 200:
        result = 'HTTP_ERROR'
    elif len(raw) > MAX_BODY:
        result = 'BODY_TOO_LARGE'
    elif not raw.strip():
        result = 'EMPTY_RESPONSE'
    else:
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            result = 'NON_JSON_RESPONSE'
        else:
            stats = inspect_tree(payload)
            error = isinstance(payload, dict) and (payload.get('isError') is True or
                     bool(payload.get('error')) or payload.get('success') is False)
            result = 'API_ERROR_IN_200' if error else 'JSON_STRUCTURE_INSPECTED_NOT_VERIFIED'
            print(f'{label}: product_arrays={stats["product_arrays"]} store_arrays={stats["store_arrays"]} '
                  f'quantity_fields={stats["quantity_fields"]} numeric_quantity_fields={stats["numeric_quantity_fields"]} '
                  f'error_fields_present={stats["error_fields"]}')
    print(f'{label}: {result}; STOCK_UNKNOWN; ZERO_NOT_INFERRED')
    return result


def main():
    print('GS25_STAGE3_SCHEMA_AUDIT; READ_ONLY; NO_CREDENTIALS; NO_STATE_WRITES; NO_ALERTS')
    print('TARGET_ITEM_CODE_ASSUMED=' + TARGET)
    outcomes = [
        probe('CONTROL_PRODUCT_SEARCH', 'gs25SearchProducts', keyword='코카콜라캔350ML', limit=3),
        probe('TARGET_PRODUCT_SEARCH', 'gs25SearchProducts', keyword='포켓몬', limit=3),
        probe('TARGET_INVENTORY_BY_CODE', 'gs25CheckInventory', itemCode=TARGET, storeKeyword='남원', storeLimit=3),
    ]
    print('GS25_STAGE3_RESULTS=' + ','.join(outcomes))
    print('GS25_STOCK_NOT_VERIFIED; ZERO_STOCK_NOT_INFERRED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
