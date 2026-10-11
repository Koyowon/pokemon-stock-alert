#!/usr/bin/env python3
"""Manual GS25 catalog candidate discovery. Public catalog only, no stock or alerts."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/actions/query'
ASSUMED_CODE = '8800286275732'  # Unverified; do not treat as product identity
TERMS = ('포켓몬 30주년', '포켓몬카드', '포켓몬 카드', '포켓몬', '30주년', '메가진화', 'MEGA')
NAME_KEYS = ('itemName', 'productName', 'name', 'goodsName', 'itemNm', 'productNm')
CODE_KEYS = ('itemCode', 'barcode', 'barCode', 'ean', 'gtin')
MAX_BYTES = 262144


def fetch(term):
    url = BASE + '?' + urllib.parse.urlencode({
        'action': 'gs25SearchProducts', 'format': 'json', 'keyword': term, 'limit': 100})
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json', 'User-Agent': 'gs25-catalog-candidate-audit/3.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status, body = response.status, response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return [], 'HTTP_' + str(exc.code), False
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return [], 'NETWORK_' + type(exc).__name__, False
    if status != 200 or len(body) > MAX_BYTES:
        return [], 'BAD_HTTP_OR_OVERSIZE', False
    try:
        obj = json.loads(body.decode('utf-8'))
    except (UnicodeError, ValueError):
        return [], 'INVALID_JSON', False
    if not isinstance(obj, dict) or obj.get('success') is not True or obj.get('error') or obj.get('isError'):
        return [], 'API_UNCONFIRMED', False
    data = obj.get('data')
    products = data.get('products') if isinstance(data, dict) else None
    if not isinstance(products, list):
        return [], 'PRODUCTS_MISSING', False
    return products, 'OK', len(products) >= 100


def product_name(p):
    for k in NAME_KEYS:
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ''


def product_code(p):
    for k in CODE_KEYS:
        v = p.get(k)
        if isinstance(v, (str, int)) and re.fullmatch(r'\d{8,14}', str(v).strip()):
            return str(v).strip()
    return ''


def classify(name):
    text = re.sub(r'\s+', '', name).casefold()
    pokemon = '포켓몬' in text or 'pokemon' in text
    anniversary = '30주년' in text or '30th' in text
    pack = any(w in text for w in ('기념팩', '확장팩', '카드', '팩', 'pack'))
    if pokemon and anniversary and pack:
        return 'STRONG_NAME_MATCH'
    if pokemon and (anniversary or pack):
        return 'RELATED_POKEMON'
    return 'OTHER'


def safe_name(name):
    # Public catalog product names only; prevent terminal/control character injection.
    clean = re.sub(r'[\x00-\x1f\x7f\x1b]', ' ', name)
    return re.sub(r'\s+', ' ', clean).strip()[:85]


def main():
    print('GS25_CANDIDATE_DISCOVERY; MANUAL_ONLY; PUBLIC_CATALOG_ONLY; NO_STOCK_REQUESTS')
    print('ASSUMED_CODE=' + ASSUMED_CODE + '; UNVERIFIED')
    unique = {}
    for index, term in enumerate(TERMS, 1):
        products, status, limited = fetch(term)
        print(f'SEARCH_{index}: status={status}; rows={len(products)}; limit_reached={limited}')
        for p in products:
            if not isinstance(p, dict):
                continue
            name, code = product_name(p), product_code(p)
            if not name or not code:
                continue
            category = classify(name)
            if category == 'OTHER':
                continue
            key = (code, name)
            unique[key] = (category, code, name)
    strong = sorted((v for v in unique.values() if v[0] == 'STRONG_NAME_MATCH'), key=lambda x: x[2])
    related = sorted((v for v in unique.values() if v[0] == 'RELATED_POKEMON'), key=lambda x: x[2])
    print(f'UNIQUE_STRONG_NAME_MATCHES={len(strong)}; UNIQUE_RELATED_POKEMON={len(related)}')
    for category, code, name in (strong[:20] + related[:12]):
        print(f'CANDIDATE: class={category}; code={code}; name={safe_name(name)}; IDENTITY_NOT_VERIFIED')
    matches = [v for v in unique.values() if v[1] == ASSUMED_CODE]
    print(f'ASSUMED_CODE_IN_RELATED_CATALOG={bool(matches)}')
    print('NO_INVENTORY_LOOKUPS; NO_STATE_WRITES; NO_ALERTS; NO_ZERO_STOCK_INFERENCE')
    print('CANDIDATES_REQUIRE_INDEPENDENT_IDENTITY_CONFIRMATION')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
