"""Read-only CU / Emart24 Jeonju and Jeju discovery diagnostic.

Does not send Telegram messages or modify any state/cache files.
"""
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BARCODE = '8800286275732'
PRODUCT = '포켓몬)30주년기념카드'

# Representative geographic probes, not yet a completeness guarantee.
CU_POINTS = {
    '전주': [
        (35.824, 127.148), (35.811, 127.119), (35.788, 127.131),
        (35.844, 127.126), (35.858, 127.113), (35.865, 127.161),
        (35.830, 127.175), (35.798, 127.170),
    ],
    '제주': [
        (33.500, 126.531), (33.490, 126.490), (33.513, 126.520),
        (33.476, 126.545), (33.486, 126.430), (33.470, 126.390),
        (33.542, 126.665), (33.542, 126.828), (33.449, 126.570),
    ],
}

PREFIXES = {
    '전주': ('전북특별자치도 전주시', '전라북도 전주시', '전북 전주시'),
    '제주': ('제주특별자치도 제주시', '제주도 제주시', '제주시 '),
}


class Tokens(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []

    def handle_data(self, data):
        if data.strip():
            self.items.append(data.strip())


def field(tokens, key):
    try:
        i = tokens.index(key)
        return tokens[i + 1]
    except (ValueError, IndexError):
        return None


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': 'PokemonRegionDiagnostic/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read(1500000).decode('utf-8', 'replace')


def check_cu():
    for city, points in CU_POINTS.items():
        seen = {}
        success = 0
        errors = 0
        for lat, lng in points:
            params = {
                'keyword': PRODUCT, 'size': 100, 'offset': 0,
                'storeCheck': 'true', 'lat': lat, 'lng': lng, 'format': 'html',
            }
            url = 'https://mcp.aka.page/api/cu/inventory?' + urllib.parse.urlencode(params)
            try:
                parser = Tokens()
                parser.feed(fetch(url, timeout=40))
                tokens = parser.items
                if field(tokens, 'success') != 'true':
                    raise ValueError('API success is not true')
                if field(tokens, 'stockItemCode') != BARCODE:
                    raise ValueError('Wrong product selection')
                starts = [i for i, t in enumerate(tokens) if t == 'storeCode']
                matched = 0
                for n, start in enumerate(starts):
                    end = starts[n + 1] if n + 1 < len(starts) else len(tokens)
                    block = tokens[start:end]
                    code = field(block, 'storeCode')
                    address = ' '.join(str(field(block, 'address') or '').split())
                    name = field(block, 'storeName')
                    if not code or not re.fullmatch(r'[0-9]+', code):
                        continue
                    if not any(address.startswith(p) for p in PREFIXES[city]):
                        continue
                    if not name:
                        continue
                    seen[code] = {'name': name, 'address': address}
                    matched += 1
                success += 1
                print(f'CU_QUERY_OK city={city} lat={lat} lng={lng} matched={matched}', flush=True)
            except Exception as exc:
                errors += 1
                print(f'CU_QUERY_ERROR city={city} lat={lat} lng={lng} {type(exc).__name__}: {str(exc)[:120]}', flush=True)
        print(f'CU_REGION_SUMMARY city={city} queries_ok={success} queries_failed={errors} unique_stores={len(seen)}', flush=True)
        for code, item in sorted(seen.items()):
            print(f'CU_STORE city={city} code={code} name={item["name"]} address={item["address"]}', flush=True)


def check_emart():
    # Search both the municipality and its subdivisions; each call has a 100-row cap.
    keywords = {
        '전주': ['전주', '완산', '덕진'],
        '제주': ['제주', '애월', '한림', '조천', '구좌', '한경'],
    }
    for city, words in keywords.items():
        seen = {}
        success = 0
        errors = 0
        for word in words:
            url = 'https://mcp.aka.page/api/emart24/stores?' + urllib.parse.urlencode({'keyword': word, 'limit': 100})
            try:
                payload = json.loads(fetch(url, timeout=20))
                if payload.get('success') is not True:
                    raise ValueError('API unsuccessful')
                rows = payload.get('data', {}).get('stores')
                if not isinstance(rows, list):
                    raise ValueError('Invalid stores list')
                matched = 0
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    code = str(item.get('storeCode') or '').strip()
                    address = ' '.join(str(item.get('address') or '').split())
                    if code and any(address.startswith(p) for p in PREFIXES[city]):
                        seen[code] = {'name': str(item.get('storeName') or code), 'address': address}
                        matched += 1
                success += 1
                print(f'EMART_QUERY_OK city={city} keyword={word} returned={len(rows)} matched={matched} at_limit={len(rows)>=100}', flush=True)
            except Exception as exc:
                errors += 1
                print(f'EMART_QUERY_ERROR city={city} keyword={word} {type(exc).__name__}: {str(exc)[:120]}', flush=True)
        print(f'EMART_REGION_SUMMARY city={city} queries_ok={success} queries_failed={errors} unique_stores={len(seen)}', flush=True)
        for code, item in sorted(seen.items()):
            print(f'EMART_STORE city={city} code={code} name={item["name"]} address={item["address"]}', flush=True)


if __name__ == '__main__':
    print('REGION_EXPANSION_DIAGNOSTIC_START', flush=True)
    check_cu()
    check_emart()
    print('REGION_EXPANSION_DIAGNOSTIC_FINISHED', flush=True)
