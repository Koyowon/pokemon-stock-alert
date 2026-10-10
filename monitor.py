
"""Emart24 stock monitor for Namwon and Asan, with conservative API retries."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = 'https://mcp.aka.page/api/emart24'
STATE_FILE = ROOT / 'state.json'
STORES_FILE = ROOT / 'stores.json'
REGIONS = {'남원': '남원시', '아산': '아산시'}
PRODUCTS = {
    '초전브레이커 낱개팩': '8809945338207',
    '인페르노X 낱개팩': '8800286278535',
    '30주년 셀레브레이션 팩': '8800286275732',
}
SEED = {
    '21475': {'name': 'R남원이그린점', 'address': '전북특별자치도 남원시 황죽로 11'},
    '21598': {'name': '남원중앙하이츠점', 'address': '전북특별자치도 남원시 동림로 129'},
    '22612': {'name': '남원센트럴점', 'address': '전북특별자치도 남원시 요천로 1306-8'},
    '23439': {'name': '남원요천로점', 'address': '전북특별자치도 남원시 요천로 1976'},
    '24252': {'name': '남원도통점', 'address': '전북특별자치도 남원시 춘향로 81'},
    '01073': {'name': '아산음봉점', 'address': '충청남도 아산시 음봉면 연암율금로 399'},
}


def read_json(path, default):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else default
    except (OSError, ValueError):
        return default


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def api(path, params, attempts=2):
    url = BASE + '/' + path + '?' + urllib.parse.urlencode(params)
    last = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'PokemonStockMonitor/1.1',
                'Accept': 'application/json',
            })
            with urllib.request.urlopen(req, timeout=15) as response:
                payload = json.load(response)
            if not isinstance(payload, dict) or payload.get('success') is not True:
                raise ValueError('API returned unsuccessful response')
            data = payload.get('data')
            if not isinstance(data, dict):
                raise ValueError('API returned invalid data')
            return data
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (400, 401, 403, 404, 429):
                break
            if attempt + 1 < attempts:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'{path}: {type(last).__name__}: {last}')


def get_stores():
    cache = read_json(STORES_FILE, {})
    stores = dict(SEED)
    cached_stores = cache.get('stores', {})
    if isinstance(cached_stores, dict):
        for code, item in cached_stores.items():
            if isinstance(item, dict) and any(city in str(item.get('address', '')) for city in REGIONS.values()):
                stores[str(code)] = item

    now = datetime.now(timezone.utc)
    try:
        last = datetime.fromisoformat(cache.get('last_refresh', ''))
        refresh = last.tzinfo is None or now - last >= timedelta(hours=24)
    except (ValueError, TypeError):
        refresh = True

    if refresh:
        successful = 0
        for keyword, city in REGIONS.items():
            try:
                data = api('stores', {'keyword': keyword, 'limit': 100})
                rows = data.get('stores')
                if not isinstance(rows, list) or not rows:
                    raise ValueError('empty or invalid store list')
                matched = 0
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    code = str(row.get('storeCode') or '').strip()
                    address = str(row.get('address') or '')
                    if code and city in address:
                        stores[code] = {
                            'name': str(row.get('storeName') or code),
                            'address': address,
                        }
                        matched += 1
                if matched == 0:
                    raise ValueError('no matching addresses')
                successful += 1
                print(f'{city}: search returned {len(rows)}, matched {matched}')
                if len(rows) >= 20:
                    print(f'WARNING: {city} returned {len(rows)} rows; completeness not verified')
            except (RuntimeError, ValueError) as exc:
                print(f'WARNING: {city} directory unavailable; using cached stores: {exc}')
            time.sleep(1)
        save_json(STORES_FILE, {
            'last_refresh': now.isoformat() if successful == len(REGIONS) else cache.get('last_refresh'),
            'stores': stores,
        })

    for city in REGIONS.values():
        print(f'{city}: {sum(city in str(s.get("address", "")) for s in stores.values())} cached/matched stores')
    print(f'Total unique matched stores: {len(stores)}')
    return stores


def notify(message):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        print('WARNING: Telegram secrets missing')
        return False
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=urllib.parse.urlencode({'chat_id': chat_id, 'text': message}).encode(),
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response).get('ok') is True
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f'WARNING: Telegram send failed: {type(exc).__name__}')
        return False


def stock(plu, codes):
    """Return quantities and per-store diagnostics without increasing API traffic."""
    values = {}
    statuses = {code: 'NOT_CHECKED' for code in codes}
    consecutive_failures = 0
    fallback_calls = 0
    max_fallback_calls = 4

    def collect(data, expected):
        rows = data.get('stores')
        if not isinstance(rows, list):
            raise ValueError('missing stores array')
        returned = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get('bizNo') or '').strip()
            if code not in expected:
                continue
            returned.add(code)
            qty = row.get('bizQty')
            if type(qty) is int and qty >= 0:
                values[code] = qty
                statuses[code] = 'OK'
            elif statuses[code] != 'OK':
                statuses[code] = 'NULL_OR_INVALID_QTY'
        for code in expected:
            if code not in returned and statuses[code] != 'OK':
                statuses[code] = 'MISSING_IN_RESPONSE'

    for start in range(0, len(codes), 3):
        batch = codes[start:start + 3]
        try:
            data = api('inventory', {'pluCd': plu, 'bizNoArr': ','.join(batch)}, attempts=2)
            collect(data, batch)
            consecutive_failures = 0
        except (RuntimeError, ValueError) as exc:
            consecutive_failures += 1
            for code in batch:
                statuses[code] = 'BATCH_ERROR'
            print(f'WARNING: inventory batch failed ({len(batch)} stores): {exc}')
            if fallback_calls < max_fallback_calls:
                for code in batch:
                    if fallback_calls >= max_fallback_calls:
                        break
                    fallback_calls += 1
                    time.sleep(2)
                    try:
                        data = api('inventory', {'pluCd': plu, 'bizNoArr': code}, attempts=1)
                        collect(data, [code])
                    except (RuntimeError, ValueError) as single_exc:
                        statuses[code] = 'SINGLE_ERROR'
                        print(f'WARNING: single-store lookup failed ({code}): {single_exc}')
            if consecutive_failures >= 3:
                print('WARNING: 3 consecutive failed batches; stopping this product to protect API')
                break
        time.sleep(1.5)
    print(f'Inventory diagnostics: {fallback_calls} bounded single-store probes')
    return values, statuses


def main():
    stores = get_stores()
    if not stores:
        raise RuntimeError('No saved or discoverable stores')
    previous = read_json(STATE_FILE, {})
    updated = dict(previous)
    numeric = unknown = 0

    for product, plu in PRODUCTS.items():
        values, statuses = stock(plu, list(stores))
        print(f"--- Per-store diagnostics: {product} ---")
        for code, status in statuses.items():
            print(f"STORE {code} | {stores[code]['name']} | {status}")
        for code, store in stores.items():
            key = f'이마트24|{code}|{plu}'
            qty = values.get(code)
            if qty is None:
                unknown += 1
                continue
            numeric += 1
            old = previous.get(key)
            message = None
            if type(old) is int:
                if qty > old:
                    message = (
                        f'🟢 포켓몬카드 재고 입고/증가!\n상품: {product}\n'
                        f'매장: 이마트24 {store["name"]}\n주소: {store["address"]}\n'
                        f'이전 재고: {old}개 → 현재 재고: {qty}개 (+{qty - old}개)'
                    )
                elif qty < old:
                    if qty == 0:
                        message = (
                            f'🔴 포켓몬카드 품절 확인!\n상품: {product}\n'
                            f'매장: 이마트24 {store["name"]}\n주소: {store["address"]}\n'
                            f'이전 재고: {old}개 → 현재 재고: 0개'
                        )
                    else:
                        message = (
                            f'🟠 포켓몬카드 재고 감소!\n상품: {product}\n'
                            f'매장: 이마트24 {store["name"]}\n주소: {store["address"]}\n'
                            f'이전 재고: {old}개 → 현재 재고: {qty}개 (-{old - qty}개)'
                        )
            elif qty > 0:
                message = (
                    f'🟢 포켓몬카드 첫 재고 확인!\n상품: {product}\n'
                    f'매장: 이마트24 {store["name"]}\n주소: {store["address"]}\n'
                    f'현재 재고: {qty}개'
                )
            if message is not None:
                message += '\n※ 조회 시점의 수량이며, 방문 전 매장에 확인하세요.'
                if not notify(message):
                    print(f'WARNING: alert failed, state not advanced: {key}')
                    continue
            updated[key] = qty
        print(f'{product}: {len(values)}/{len(stores)} numeric results')

    save_json(STATE_FILE, updated)
    print(f'Finished: {numeric} numeric inventory entries, {unknown} unknown entries')
    if numeric == 0:
        print('WARNING: No numeric stock values; API health needs investigation')


if __name__ == '__main__':
    main()
