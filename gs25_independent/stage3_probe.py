#!/usr/bin/env python3
"""GS25 manual identity and positive-stock controls. No state writes or alerts."""
import json
import re
import urllib.parse
import urllib.request
import urllib.error
from collections import Counter

BASE = 'https://mcp.aka.page/api/actions/query'
TARGET = '8800286275732'  # identity NOT verified
INVALID = '9999999999999'
SEARCHES = ('포켓몬 30주년', '포켓몬카드', '30주년', '코카콜라캔350ML', '핫식스250ML')
STORES = ('GS25제주', '제주시', '애월', '강남', '역삼')
MAX_BYTES = 500_000


def fetch(action, **params):
    url = BASE + '?' + urllib.parse.urlencode({'action': action, 'format': 'json', **params})
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'gs25-manual-identity-check/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=18) as response:
            raw = response.read(MAX_BYTES + 1)
            if response.status != 200 or len(raw) > MAX_BYTES:
                return None, 'BAD_HTTP_OR_SIZE'
    except urllib.error.HTTPError as e:
        return None, f'HTTP_{e.code}'
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, 'NETWORK_' + type(e).__name__
    try:
        obj = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError):
        return None, 'BAD_JSON'
    if not isinstance(obj, dict) or obj.get('success') is not True or obj.get('error') or obj.get('isError'):
        return None, 'API_UNCONFIRMED'
    return obj.get('data'), 'OK'


def clean(value):
    return re.sub(r'\s+', ' ', ''.join(c if c.isprintable() else ' ' for c in str(value)))[:90]


def product_info(p):
    name = next((p[k] for k in ('itemName', 'productName', 'name', 'goodsName', 'itemNm', 'productNm') if isinstance(p.get(k), str) and p[k].strip()), '')
    code = next((str(p[k]) for k in ('itemCode', 'barcode', 'barCode', 'ean', 'gtin') if isinstance(p.get(k), (str, int)) and re.fullmatch(r'\d{8,14}', str(p[k]))), '')
    return clean(name), code


def inventory(code, keyword):
    data, status = fetch('gs25CheckInventory', itemCode=code, storeKeyword=keyword, storeLimit=60)
    if status != 'OK':
        return [], status
    inv = data.get('inventory') if isinstance(data, dict) else None
    rows = inv.get('stores') if isinstance(inv, dict) else None
    return (rows, 'OK') if isinstance(rows, list) else ([], 'STORES_MISSING')


def qty(store):
    v = store.get('realStockQuantity')
    if type(v) is int and v >= 0:
        return v
    if isinstance(v, str) and v.isdigit():
        return int(v)
    return None


def main():
    print('GS25_IDENTITY_AND_POSITIVE_CONTROL; MANUAL_ONLY; NO_ALERTS; NO_STATE_WRITES')
    print(f'TARGET={TARGET}; IDENTITY_UNVERIFIED; INVALID_CONTROL={INVALID}')
    found_target = []
    controls = []
    failures = 0
    for term in SEARCHES:
        data, status = fetch('gs25SearchProducts', keyword=term, limit=100)
        rows = data.get('products') if isinstance(data, dict) else None
        if status == 'OK' and not isinstance(rows, list):
            status = 'PRODUCTS_MISSING'
        if status != 'OK':
            failures += 1
            print(f'CATALOG term={clean(term)}; status={status}')
            continue
        print(f'CATALOG term={clean(term)}; status=OK; rows={len(rows)}; truncated_possible={len(rows)>=100}')
        for p in rows:
            if not isinstance(p, dict):
                continue
            name, code = product_info(p)
            if code == TARGET:
                found_target.append(name)
                print(f'TARGET_CATALOG_MATCH name={name}; code={code}')
            if code and name and term in ('코카콜라캔350ML', '핫식스250ML') and (('코카콜라' in name and '350' in name) or ('핫식스' in name and '250' in name)):
                controls.append((name, code))
    print(f'TARGET_CATALOG_FOUND={bool(found_target)}; NOT_FOUND_IS_NOT_PROOF_OF_INVALIDITY')
    unique_controls = list(dict.fromkeys(controls))[:2]
    print('CONTROL_PRODUCTS=' + json.dumps(unique_controls, ensure_ascii=False))
    if not unique_controls:
        print('NO_CATALOG_VERIFIED_CONTROLS; POSITIVE_STOCK_VALIDATION_INCONCLUSIVE')
    # Bounded requests: 2 controls x 5 locations, plus target and invalid on 2 locations.
    for name, code in unique_controls:
        positives = []
        for term in STORES:
            rows, status = inventory(code, term)
            if status != 'OK':
                failures += 1
                print(f'CONTROL_INVENTORY code={code}; keyword={term}; status={status}')
                continue
            counts = Counter(qty(s) for s in rows if isinstance(s, dict))
            print(f'CONTROL_INVENTORY code={code}; keyword={term}; stores={len(rows)}; positive={sum(n for q,n in counts.items() if q is not None and q>0)}; zero={counts[0]}; missing={counts[None]}')
            for s in rows:
                if isinstance(s, dict) and qty(s) is not None and qty(s) > 0:
                    positives.append((clean(s.get('storeName') or s.get('name') or s.get('storeCode') or 'unknown'), qty(s)))
        print(f'CONTROL_POSITIVE_SUMMARY code={code}; positive_rows={len(positives)}; examples={json.dumps(positives[:8],ensure_ascii=False)}')
    for term in ('GS25제주', '강남'):
        for kind, code in (('TARGET', TARGET), ('INVALID', INVALID)):
            rows, status = inventory(code, term)
            if status != 'OK':
                failures += 1
                print(f'COMPARISON kind={kind}; keyword={term}; status={status}')
                continue
            values = [qty(s) for s in rows if isinstance(s, dict)]
            print(f'COMPARISON kind={kind}; keyword={term}; stores={len(values)}; positive={sum(v is not None and v>0 for v in values)}; zero={values.count(0)}; unknown={values.count(None)}')
    print(f'REQUEST_FAILURES={failures}')
    print('CAUTION: Positive controls establish service behavior, not target identity.')
    print('CAUTION: 70_PERCENT_RULE_UNVERIFIED; ZERO_IS_NOT_PHYSICAL_STOCKOUT')
    print('NO_STATE_WRITES; NO_ALERTS; NO_AUTOMATIC_SCHEDULE')
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
