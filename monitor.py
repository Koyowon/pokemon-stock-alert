"""Monitor Emart24 Pokemon card inventory in Namwon-si and Asan-si.

Uses an independent public API, not an official Emart24 integration.
Unknown quantities are never treated as zero. Store search completeness is
not guaranteed by the upstream service.
"""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / 'state.json'
BASE = 'https://mcp.aka.page/api/emart24'
PRODUCTS = {
    '8809945338207': '초전브레이커 낱개팩',
    '8809945338214': '초전브레이커 박스',
    '8800286278535': '인페르노X 낱개팩',
}
REGIONS = {'남원': '남원시', '아산': '아산시'}
KST = timezone(timedelta(hours=9))


def get_json(path, params):
    url = f'{BASE}/{path}?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'User-Agent': 'PokemonStockMonitor/1.0',
        'Accept': 'application/json',
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.load(response)
            if result.get('success') is not True:
                raise RuntimeError(f'API unsuccessful: {path}, {params}')
            return result.get('data') or {}
        except (OSError, ValueError) as exc:
            if attempt == 2:
                raise RuntimeError(f'API request failed: {path}, {params}') from exc
            time.sleep(2 * (attempt + 1))


def find_stores():
    stores = {}
    for keyword, city in REGIONS.items():
        data = get_json('stores', {'keyword': keyword})
        results = data.get('stores')
        if not isinstance(results, list):
            raise RuntimeError(f'Invalid store search response for {keyword}')
        matched = 0
        for item in results:
            code = str(item.get('storeCode') or '').strip()
            address = str(item.get('address') or '')
            if code and city in address:
                stores[code] = {'name': item.get('storeName') or code, 'address': address}
                matched += 1
        print(f'{city}: search returned {len(results)} stores, {matched} address matches')
        if matched == 0:
            raise RuntimeError(f'No stores found for {city}; stopping to avoid silent gaps')
        # An upstream search may impose limits; report rather than claim full coverage.
        meta = data.get('meta') or {}
        print(f'{city}: metadata={meta!r}')
    print(f'Total unique matched stores: {len(stores)}')
    return stores


def telegram(message):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        raise RuntimeError('Missing Telegram secrets')
    body = urllib.parse.urlencode({'chat_id': chat_id, 'text': message}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=body)
    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.load(response)
    if not result.get('ok'):
        raise RuntimeError('Telegram rejected message')


def chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def main():
    stores = find_stores()
    previous = json.loads(STATE_FILE.read_text(encoding='utf-8')) if STATE_FILE.exists() else {}
    updated = dict(previous)
    numeric = 0
    unknown = 0
    for plu, product in PRODUCTS.items():
        for group in chunks(list(stores), 10):
            data = get_json('inventory', {'pluCd': plu, 'bizNoArr': ','.join(group)})
            results = data.get('stores')
            if not isinstance(results, list):
                raise RuntimeError(f'Invalid inventory response for {product}')
            seen = set()
            for item in results:
                code = str(item.get('bizNo') or '').strip()
                if code not in stores:
                    continue
                seen.add(code)
                qty = item.get('bizQty')
                if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
                    unknown += 1
                    print(f'UNKNOWN {product} | {stores[code]["name"]}: {qty!r}')
                    continue
                numeric += 1
                key = f'emart24|{code}|{plu}'
                old = previous.get(key)
                print(f'{product} | {stores[code]["name"]} | {qty}개 (previous={old})')
                if qty > 0 and (old is None or (type(old) is int and qty > old)):
                    store = stores[code]
                    telegram('🎉 포켓몬카드 재고 발견!\n'
                             f'편의점: 이마트24\n매장: {store["name"]}\n'
                             f'주소: {store["address"]}\n상품: {product}\n'
                             f'재고: {qty}개\n'
                             f'조회: {datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")}\n'
                             '※ 방문 전 매장에 확인하세요.')
                updated[key] = qty
            missing = set(group) - seen
            if missing:
                unknown += len(missing)
                print(f'UNKNOWN {product}: missing store codes {sorted(missing)}')
            time.sleep(0.3)
    if numeric == 0:
        raise RuntimeError('No numeric inventory received; state not changed')
    if updated != previous:
        STATE_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Finished: {numeric} numeric entries, {unknown} unknown entries')


if __name__ == '__main__':
    main()
