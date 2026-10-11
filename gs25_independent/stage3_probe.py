#!/usr/bin/env python3
"""Manual, read-only GS25 public third-party API diagnostic. No alerts/state writes."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

BASE = 'https://mcp.aka.page/api/actions/query'
TARGET = '8800286275732'  # Unverified candidate
INVALID = '9999999999999'  # Deliberately invalid control; not a product
KNOWN = '8800286278085'  # Previously catalog-listed Pokemon Mega Brave; reverify live
KEYWORDS = ('제주', '제주시', '서귀포', '애월', 'GS25제주', '제주공항', '제주대', '연동', '노형', '한림', '성산', '중문')
MAX_BYTES = 512_000


def api(action, **params):
    url = BASE + '?' + urllib.parse.urlencode({'action': action, 'format': 'json', **params})
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'gs25-manual-validation/2.0'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read(MAX_BYTES + 1)
            if resp.status != 200 or len(raw) > MAX_BYTES:
                return None, 'BAD_RESPONSE'
    except urllib.error.HTTPError as e:
        return None, 'HTTP_' + str(e.code)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, 'NETWORK_' + type(e).__name__
    try:
        obj = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError):
        return None, 'INVALID_JSON'
    if not isinstance(obj, dict) or obj.get('success') is not True or obj.get('error') or obj.get('isError'):
        return None, 'API_UNCONFIRMED'
    return obj.get('data'), 'OK'


def clean(s):
    return re.sub(r'\s+', ' ', ''.join(c if c.isprintable() else ' ' for c in str(s)))[:75]


def name(store):
    for key in ('storeName', 'name', 'shopName', 'storeNm'):
        if isinstance(store.get(key), str) and store[key].strip():
            return clean(store[key])
    return '(name_missing)'


def ident(store):
    return str(store.get('storeCode') or store.get('storeId') or store.get('storeCd') or name(store))


def qty(store):
    v = store.get('realStockQuantity')
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and v >= 0 and float(v).is_integer():
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def inventory(code, keyword, limit=100):
    data, status = api('gs25CheckInventory', itemCode=code, storeKeyword=keyword, storeLimit=limit)
    if status != 'OK':
        return None, status, None
    inv = data.get('inventory') if isinstance(data, dict) else None
    stores = inv.get('stores') if isinstance(inv, dict) else None
    if not isinstance(stores, list):
        return None, 'STORES_MISSING', None
    return stores, 'OK', inv


def catalog_check(code):
    # Product catalog searches are independent evidence of item identity.
    for term in ('메가브레이브', '포켓몬 30주년', '포켓몬카드'):
        data, status = api('gs25SearchProducts', keyword=term, limit=100)
        products = data.get('products') if isinstance(data, dict) else None
        if status != 'OK' or not isinstance(products, list):
            print(f'CATALOG term={clean(term)}; status={status if status != "OK" else "PRODUCTS_MISSING"}')
            continue
        matches = []
        for p in products:
            if not isinstance(p, dict):
                continue
            itemcode = str(p.get('itemCode') or p.get('barcode') or p.get('barCode') or '')
            if itemcode in (TARGET, KNOWN):
                nm = next((str(p[k]) for k in ('itemName', 'productName', 'name', 'goodsName') if p.get(k)), '?')
                matches.append((itemcode, clean(nm)))
        print(f'CATALOG term={clean(term)}; rows={len(products)}; matched_codes={matches}; limit_reached={len(products)>=100}')


def main():
    print('GS25_STAGE3_VALIDATION; MANUAL_ONLY; THIRD_PARTY_PUBLIC_API; READ_ONLY')
    print(f'TARGET={TARGET}; IDENTITY_UNVERIFIED; CONTROL_KNOWN={KNOWN}; CONTROL_INVALID={INVALID}')
    print('NO_70_PERCENT_CONVERSION; RAW_API_VALUES_ONLY')
    catalog_check(TARGET)
    combined = {}
    failures = 0
    for keyword in KEYWORDS:
        stores, status, _ = inventory(TARGET, keyword)
        if stores is None:
            print(f'TARGET_QUERY keyword={clean(keyword)}; status={status}')
            failures += 1
            continue
        print(f'TARGET_QUERY keyword={clean(keyword)}; status=OK; returned={len(stores)}; limit_reached={len(stores)>=100}')
        for s in stores:
            if isinstance(s, dict):
                combined[ident(s)] = (name(s), qty(s))
    positives = sorted([(n, q) for n, q in combined.values() if q is not None and q > 0], key=lambda x: (-x[1], x[0]))
    print(f'TARGET_SUMMARY unique_stores={len(combined)}; positive={len(positives)}; zero={sum(q==0 for _,q in combined.values())}; unknown={sum(q is None for _,q in combined.values())}; failed_queries={failures}')
    print('TARGET_POSITIVE_COUNTS=' + json.dumps(dict(sorted(Counter(q for _,q in positives).items())), ensure_ascii=False))
    for n, q in positives[:30]:
        print(f'TARGET_POSITIVE_STORE name={n}; raw_quantity={q}; multiple_of_14={q%14==0}')
    # Compare the same small selection of keywords for valid and invalid controls.
    # A zero response for an invalid code means zero alone cannot validate identity.
    for keyword in ('제주시', '애월', '연동'):
        results = {}
        for label, code in (('TARGET', TARGET), ('CATALOG_CONTROL', KNOWN), ('INVALID_CONTROL', INVALID)):
            stores, status, _ = inventory(code, keyword, limit=30)
            if stores is None:
                print(f'CONTROL keyword={clean(keyword)}; type={label}; status={status}')
                continue
            values = [qty(s) for s in stores if isinstance(s, dict)]
            results[label] = {ident(s): qty(s) for s in stores if isinstance(s, dict)}
            print(f'CONTROL keyword={clean(keyword)}; type={label}; status=OK; returned={len(stores)}; positive={sum(v is not None and v>0 for v in values)}; zero={sum(v==0 for v in values)}; missing={sum(v is None for v in values)}')
        common = set.intersection(*(set(d) for d in results.values())) if len(results)==3 else set()
        for sid in sorted(common)[:10]:
            print(f'SAME_STORE keyword={clean(keyword)}; store_id={clean(sid)}; target={results["TARGET"][sid]}; catalog_control={results["CATALOG_CONTROL"][sid]}; invalid_control={results["INVALID_CONTROL"][sid]}')
    print('INTERPRETATION: INVALID_CONTROL returning stores/zeros means response does not prove product existence.')
    print('NO_ALERTS; NO_STATE_WRITES; NO_REGION_SETTING_CHANGES; NO_AUTOMATIC_SCHEDULE')
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
