#!/usr/bin/env python3
"""Manual, read-only GS25 stock recheck. No alert/state mutations."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/actions/query'
TARGET = '8800286275732'
INVALID = '9999999999999'
CONTROL = '8801094083205'
KEYWORDS = ('제주봉성점', 'GS25제주', '제주노형점', '제주베스트웨스턴점')
MAX_BYTES = 500000


def query(action, **params):
    url = BASE + '?' + urllib.parse.urlencode({'action': action, 'format': 'json', **params})
    request = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'gs25-manual-recheck/1.0'})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=22) as response:
                raw = response.read(MAX_BYTES + 1)
                if response.status != 200 or len(raw) > MAX_BYTES:
                    return None, 'BAD_RESPONSE'
            result = json.loads(raw.decode('utf-8'))
            if not isinstance(result, dict) or result.get('success') is not True or result.get('error') or result.get('isError'):
                return None, 'API_UNCONFIRMED'
            return result.get('data'), 'OK'
        except urllib.error.HTTPError as e:
            err = f'HTTP_{e.code}'
            if e.code not in (502, 503, 504):
                break
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            err = 'NETWORK_' + type(e).__name__
        except (ValueError, UnicodeError):
            return None, 'INVALID_JSON'
        if attempt == 0:
            time.sleep(1)
    return None, err


def stock_value(row):
    value = row.get('realStockQuantity')
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


def main():
    print('GS25_TARGET_RECHECK; MANUAL_ONLY; READ_ONLY; NO_ALERTS; NO_STATE_WRITES', flush=True)
    print('TARGET=8800286275732; GS1_IDENTITY_CONFLICT; NOT_FINAL_PRODUCT_VERIFICATION', flush=True)
    failures = 0
    for kind, code in (('TARGET', TARGET), ('INVALID', INVALID), ('CONTROL', CONTROL)):
        for term in KEYWORDS:
            data, status = query('gs25CheckInventory', itemCode=code, storeKeyword=term, storeLimit=100)
            inventory = data.get('inventory') if isinstance(data, dict) else None
            rows = inventory.get('stores') if isinstance(inventory, dict) else None
            if status != 'OK' or not isinstance(rows, list):
                failures += 1
                print(f'QUERY kind={kind}; keyword={term}; status={status if status != "OK" else "MISSING_STORES"}', flush=True)
                continue
            positives = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get('storeName') or row.get('name') or '').strip()
                code_store = str(row.get('storeCode') or '').strip()
                amount = stock_value(row)
                if amount is not None and amount > 0:
                    positives.append((name, code_store, amount))
                if '봉성' in name or code_store == 'VHX62':
                    print(f'BONGSEONG kind={kind}; keyword={term}; name={name}; storeCode={code_store}; realStockQuantity={amount}', flush=True)
            print(f'QUERY kind={kind}; keyword={term}; stores={len(rows)}; positive={len(positives)}; examples={json.dumps(positives[:12], ensure_ascii=False)}', flush=True)
    for term in ('30주년', '셀레브레이션', '포켓몬카드', '30th'):
        data, status = query('gs25SearchProducts', keyword=term, limit=100)
        rows = data.get('products') if isinstance(data, dict) else None
        if status != 'OK' or not isinstance(rows, list):
            failures += 1
            print(f'CATALOG keyword={term}; status={status if status != "OK" else "MISSING_PRODUCTS"}', flush=True)
            continue
        candidates = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get('itemName') or row.get('productName') or row.get('name') or '')
            item = str(row.get('itemCode') or '')
            if item == TARGET or ('포켓몬' in name and ('30주년' in name or '셀레브레이션' in name or '기념' in name)):
                candidates.append((name[:80], item))
        print(f'CATALOG keyword={term}; rows={len(rows)}; candidates={json.dumps(candidates[:20],ensure_ascii=False)}', flush=True)
    print(f'REQUEST_FAILURES={failures}; ERRORS_DO_NOT_INVALIDATE_SUCCESSFUL_ROWS', flush=True)
    print('CAUTION: QUANTITY_MATCH_IS_CORROBORATION_NOT_PROOF_OF_PRODUCT_IDENTITY; 70_PERCENT_UNVERIFIED', flush=True)
    print('NO_ALERTS; NO_STATE_WRITES; NO_SCHEDULE_CHANGES', flush=True)
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
