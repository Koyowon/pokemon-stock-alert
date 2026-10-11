#!/usr/bin/env python3
"""Manual GS25 Pokemon catalog/itemCode cross-check; read-only, no alerts."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/actions/query'
TARGET = '8800286275732'  # Physical pack photo; GS1 identifies this GTIN as a paper bag.
TERMS = ('포켓몬카드', '포켓몬 카드', '메가브레이브', '메가심포니아', '메가드림', '30주년', '기념 확장팩')
KNOWN = {'8800286278085': '메가브레이브', '8800286278115': '메가심포니아', '8800286278689': '메가드림EX'}
STORE_TERMS = ('GS25제주', '강남')
MAX_BYTES = 400000


def fetch(action, **kwargs):
    url = BASE + '?' + urllib.parse.urlencode({'action': action, 'format': 'json', **kwargs})
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'pokemon-gs25-manual-code-audit/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=18) as response:
            data = response.read(MAX_BYTES + 1)
            if response.status != 200 or len(data) > MAX_BYTES:
                return None, 'BAD_RESPONSE'
    except urllib.error.HTTPError as e:
        return None, 'HTTP_' + str(e.code)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return None, 'NETWORK_' + type(e).__name__
    try:
        root = json.loads(data.decode('utf-8'))
    except (UnicodeError, ValueError):
        return None, 'INVALID_JSON'
    if not isinstance(root, dict) or root.get('success') is not True or root.get('error') or root.get('isError'):
        return None, 'UNCONFIRMED_API'
    return root.get('data'), 'OK'


def info(row):
    name = next((row[k].strip() for k in ('itemName', 'productName', 'name', 'goodsName', 'itemNm', 'productNm') if isinstance(row.get(k), str) and row[k].strip()), '')
    code = next((str(row[k]).strip() for k in ('itemCode', 'barcode', 'barCode', 'ean', 'gtin') if type(row.get(k)) in (str, int) and re.fullmatch(r'\d{8,14}', str(row[k]).strip())), '')
    name = re.sub(r'\s+', ' ', ''.join(ch if ch.isprintable() else ' ' for ch in name))[:90]
    return name, code


def qty(row):
    v = row.get('realStockQuantity')
    if type(v) is int and v >= 0:
        return v
    if isinstance(v, str) and v.isdecimal():
        return int(v)
    return None


def main():
    print('GS25_POKEMON_CODE_CROSSCHECK; MANUAL_ONLY; READ_ONLY; NO_ALERTS')
    print('PHOTO_GTIN=' + TARGET + '; GS1_RECORD=PAPER_BAG; PRODUCT_IDENTITY_CONFLICT')
    print('NOTE: catalog itemCode may be GTIN-shaped but this alone cannot prove it is the physical GTIN.')
    discovered = {}
    errors = 0
    for term in TERMS:
        data, status = fetch('gs25SearchProducts', keyword=term, limit=100)
        rows = data.get('products') if isinstance(data, dict) else None
        if status != 'OK' or not isinstance(rows, list):
            print(f'CATALOG term={term}; status={status if status != "OK" else "MISSING_PRODUCTS"}')
            errors += 1
            continue
        print(f'CATALOG term={term}; status=OK; rows={len(rows)}; limit_reached={len(rows)>=100}')
        for row in rows:
            if isinstance(row, dict):
                name, code = info(row)
                if name and code:
                    discovered[code] = name
    for code, expected in KNOWN.items():
        name = discovered.get(code)
        print(f'KNOWN_POKEMON code={code}; expected={expected}; catalog_name={name or "NOT_FOUND"}; name_matches={bool(name and expected.replace(" ", "") in name.replace(" ", ""))}')
    for code, name in sorted(discovered.items()):
        normalized = name.replace(' ', '').casefold()
        if ('포켓몬' in normalized or 'pokemon' in normalized) and ('30주년' in normalized or '기념' in normalized):
            print(f'ANNIVERSARY_CANDIDATE code={code}; name={name}; VERIFY_INDEPENDENTLY')
    print(f'PHOTO_GTIN_IN_CATALOG={TARGET in discovered}; catalog_name={discovered.get(TARGET, "NOT_FOUND")}')
    # Inventory cross-check only for codes actually returned by product search.
    for code, expected in KNOWN.items():
        if code not in discovered:
            print(f'SKIP_INVENTORY code={code}; reason=NOT_IN_SEARCH_RESULTS')
            continue
        for keyword in STORE_TERMS:
            data, status = fetch('gs25CheckInventory', itemCode=code, storeKeyword=keyword, storeLimit=60)
            inv = data.get('inventory') if isinstance(data, dict) else None
            stores = inv.get('stores') if isinstance(inv, dict) else None
            if status != 'OK' or not isinstance(stores, list):
                errors += 1
                print(f'INVENTORY code={code}; keyword={keyword}; status={status if status != "OK" else "MISSING_STORES"}')
                continue
            values = [qty(s) for s in stores if isinstance(s, dict)]
            print(f'INVENTORY code={code}; keyword={keyword}; stores={len(values)}; positive={sum(v is not None and v>0 for v in values)}; zero={values.count(0)}; unknown={values.count(None)}')
    print(f'REQUEST_FAILURES={errors}')
    print('NO_PRODUCT_IDENTITY_INFERENCE_FROM_ZERO; NO_70_PERCENT_CONVERSION')
    print('NO_STATE_WRITES; NO_ALERTS; NO_SCHEDULE_CHANGES')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
