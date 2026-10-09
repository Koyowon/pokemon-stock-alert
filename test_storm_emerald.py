"""One-time Emart24 inventory diagnostic; does not alter monitor state or send alerts."""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/emart24'
PRODUCT = '스톰에메랄다'
PLU = '8800286279709'
STORE_NAME = '남원더라우점'
APP_QTY = 30


def get(path, params):
    url = BASE + '/' + path + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={
        'User-Agent': 'PokemonStockMonitor/1.1',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get('success') is not True:
        raise ValueError('API success flag missing or false')
    data = payload.get('data')
    if not isinstance(data, dict):
        raise ValueError('API data is not an object')
    return data


def main():
    print(f'TEST PRODUCT: {PRODUCT} | PLU: {PLU}')
    print(f'OFFICIAL APP: {STORE_NAME} | {APP_QTY} units (user-reported)')
    # Search the known regional directory, never assume a store code.
    directory = get('stores', {'keyword': '남원', 'limit': 100})
    rows = directory.get('stores', [])
    if not isinstance(rows, list):
        raise ValueError('Store directory missing stores list')
    print(f'DIRECTORY: returned {len(rows)} stores')
    exact = [row for row in rows if isinstance(row, dict)
             and str(row.get('storeName', '')).strip() == STORE_NAME]
    if not exact:
        print(f'STORE_NOT_FOUND: {STORE_NAME} not found in directory response')
        print('RESULT: Cannot test inventory until store code is verified')
        return
    for row in exact:
        code = str(row.get('storeCode') or '').strip()
        if not code:
            print('STORE_CODE_MISSING: matching store has no storeCode')
            continue
        print(f'STORE_FOUND: name={STORE_NAME} | code={code} | address={row.get("address", "")}')
        try:
            inventory = get('inventory', {'pluCd': PLU, 'bizNoArr': code})
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            print(f'INVENTORY_ERROR: {type(exc).__name__}: {exc}')
            continue
        entries = inventory.get('stores')
        if not isinstance(entries, list):
            print(f'INVENTORY_INVALID: stores field type={type(entries).__name__}')
            continue
        found = [item for item in entries if isinstance(item, dict)
                 and str(item.get('bizNo') or '').strip() == code]
        if not found:
            print(f'INVENTORY_MISSING: no matching bizNo; returned entries={len(entries)}')
            continue
        for item in found:
            qty = item.get('bizQty')
            print(f'INVENTORY_RESULT: qty_type={type(qty).__name__} | qty_value={qty!r}')
            print(f'RESPONSE_FIELDS: {sorted(str(k) for k in item)}')
            if type(qty) is int and qty >= 0:
                print(f'COMPARISON: official_app={APP_QTY}, api={qty}, difference={qty-APP_QTY}')
                print('NOTE: Results may differ if inventory changed between checks')
            else:
                print('COMPARISON: API quantity unavailable; do not interpret null as zero')


if __name__ == '__main__':
    try:
        main()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f'TEST_FAILED: {type(exc).__name__}: {exc}')
        raise SystemExit(1)
