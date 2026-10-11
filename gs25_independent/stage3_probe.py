#!/usr/bin/env python3
"""Read-only GS25 Jeju Bongseong targeted diagnostic; manual GitHub Actions only."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/actions/query'
PHOTO_CODE = '8800286275732'  # physical packaging photo; GS1 product identity conflicts
INVALID_CODE = '9999999999999'
CONTROL_CODE = '8801094083205'  # catalog-confirmed Coca-Cola Zero 350ml
KNOWN_POKEMON = {'8800286278085': '메가브레이브', '8800286278115': '메가심포니아'}
STORE_TERMS = ('제주봉성', '봉성', '제주봉성점', 'GS25제주', '애월')
PRODUCT_TERMS = ('30주년', '셀레브레이션', '포켓몬카드', '기념 확장팩')
MAX_BYTES = 500000


def fetch(action, **params):
    url = BASE + '?' + urllib.parse.urlencode({'action': action, 'format': 'json', **params})
    request = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'gs25-manual-bongseong-probe/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(MAX_BYTES + 1)
            if response.status != 200 or len(raw) > MAX_BYTES:
                return None, 'HTTP_OR_SIZE_ERROR'
    except urllib.error.HTTPError as exc:
        return None, 'HTTP_' + str(exc.code)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, 'NETWORK_' + type(exc).__name__
    try:
        root = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError):
        return None, 'BAD_JSON'
    if not isinstance(root, dict) or root.get('success') is not True or root.get('error') or root.get('isError'):
        return None, 'API_NOT_CONFIRMED'
    return root.get('data'), 'OK'


def clean(value):
    return re.sub(r'\s+', ' ', ''.join(c if c.isprintable() else ' ' for c in str(value)))[:90]


def stock(row):
    v = row.get('realStockQuantity')
    if type(v) is int and v >= 0:
        return v
    if isinstance(v, str) and v.isdecimal():
        return int(v)
    return None


def is_bongseong(row):
    name = str(row.get('storeName') or row.get('name') or '')
    return '봉성' in name.replace(' ', '')


def main():
    print('GS25_JEJU_BONGSEONG_TARGETED_CHECK; MANUAL_ONLY; READ_ONLY; NO_ALERTS')
    print('COMMUNITY_REPORT=14_PACKS_ARRIVED; UNVERIFIED; NOT_CURRENT_STOCK')
    print('PHOTO_CODE=' + PHOTO_CODE + '; GS1_IDENTITY_CONFLICT; NOT_VERIFIED_AS_API_ITEMCODE')
    failures = 0
    for term in PRODUCT_TERMS:
        data, status = fetch('gs25SearchProducts', keyword=term, limit=100)
        rows = data.get('products') if isinstance(data, dict) else None
        if status != 'OK' or not isinstance(rows, list):
            print(f'PRODUCT_SEARCH term={term}; status={status if status != "OK" else "MISSING_PRODUCTS"}')
            failures += 1
            continue
        print(f'PRODUCT_SEARCH term={term}; rows={len(rows)}; truncated_possible={len(rows)>=100}')
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get('itemName') or row.get('productName') or row.get('name') or '')
            code = str(row.get('itemCode') or '')
            if code == PHOTO_CODE or ('포켓몬' in name and any(s in name for s in ('30주년', '셀레브레이션', '기념'))):
                print(f'PRODUCT_CANDIDATE name={clean(name)}; itemCode={clean(code)}; NEEDS_VERIFICATION')
    found_names = set()
    # Only a small bounded number of public requests. No auth bypass or scanning.
    for kind, code in [('PHOTO', PHOTO_CODE), ('INVALID', INVALID_CODE), ('CONTROL', CONTROL_CODE),
                       *[('KNOWN_' + label, code) for code, label in KNOWN_POKEMON.items()]]:
        for term in STORE_TERMS:
            data, status = fetch('gs25CheckInventory', itemCode=code, storeKeyword=term, storeLimit=100)
            inv = data.get('inventory') if isinstance(data, dict) else None
            rows = inv.get('stores') if isinstance(inv, dict) else None
            if status != 'OK' or not isinstance(rows, list):
                print(f'LOOKUP kind={kind}; term={term}; status={status if status != "OK" else "MISSING_STORES"}')
                failures += 1
                continue
            matched = [r for r in rows if isinstance(r, dict) and is_bongseong(r)]
            print(f'LOOKUP kind={kind}; term={term}; returned_stores={len(rows)}; bongseong_matches={len(matched)}; positives={sum(stock(r) is not None and stock(r)>0 for r in rows if isinstance(r, dict))}')
            for r in matched:
                name = clean(r.get('storeName') or r.get('name') or 'UNKNOWN')
                found_names.add(name)
                print(f'BONGSEONG kind={kind}; term={term}; name={name}; storeCode={clean(r.get("storeCode") or "UNKNOWN")}; realStockQuantity={stock(r)}')
    print('BONGSEONG_STORE_NAMES=' + json.dumps(sorted(found_names), ensure_ascii=False))
    print('REQUEST_FAILURES=' + str(failures))
    print('ZERO_NOT_PROOF_OF_STOCKOUT; 14_PACK_REPORT_UNVERIFIED; 70_PERCENT_RULE_UNVERIFIED')
    print('NO_STATE_WRITES; NO_ALERTS; NO_SCHEDULE_CHANGES')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
