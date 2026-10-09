"""Emart24 stock monitor: Namwon + Asan, cached store directory, cautious API use."""
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
    '초전브레이커 박스': '8809945338214',
    '인페르노X 낱개팩': '8800286278535',
}
# Known-good store records: available even when directory API is temporarily down.
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
        obj = json.loads(path.read_text(encoding='utf-8'))
        return obj if isinstance(obj, dict) else default
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def api(path, params, attempts=2):
    url = BASE + '/' + path + '?' + urllib.parse.urlencode(params)
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'PokemonStockMonitor/1.0', 'Accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                obj = json.load(resp)
            if not isinstance(obj, dict) or obj.get('success') is not True:
                raise ValueError('API returned unsuccessful response')
            return obj.get('data') or {}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403, 429):
                break
            if i + 1 < attempts:
                time.sleep(2)
    raise RuntimeError(f'{path}: {type(last).__name__}: {last}')


def get_stores():
    cached = read_json(STORES_FILE, {})
    stores = dict(SEED)
    for code, item in cached.get('stores', {}).items():
        if isinstance(item, dict) and any(city in str(item.get('address', '')) for city in REGIONS.values()):
            stores[str(code)] = item
    now = datetime.now(timezone.utc)
    try:
        last = datetime.fromisoformat(cached.get('last_refresh', ''))
        refresh = now - last >= timedelta(hours=24)
    except (ValueError, TypeError):
        refresh = True
    if refresh:
        successful = 0
        for keyword, city in REGIONS.items():
            try:
                data = api('stores', {'keyword': keyword})
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
                        stores[code] = {'name': str(row.get('storeName') or code), 'address': address}
                        matched += 1
                if matched == 0:
                    raise ValueError('no matching addresses')
                successful += 1
                print(f'{city}: search returned {len(rows)}, matched {matched}')
                if len(rows) >= 20:
                    print(f'WARNING: {city} search returned {len(rows)} rows; completeness/pagination not verified')
            except Exception as exc:
                print(f'WARNING: {city} store search failed; using cached/seed stores: {exc}')
            time.sleep(0.7)
        # If all failed, retry discovery on the next run, rather than persisting a false refresh.
        save_json(STORES_FILE, {
            'last_refresh': now.isoformat() if successful else cached.get('last_refresh'),
            'stores': stores,
        })
    print('남원시:', sum('남원시' in s['address'] for s in stores.values()), 'cached/matched stores')
    print('아산시:', sum('아산시' in s['address'] for s in stores.values()), 'cached/matched stores')
    print('Total unique matched stores:', len(stores))
    return stores


def notify(message):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        print('WARNING: Telegram secrets missing')
        return False
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=urllib.parse.urlencode({'chat_id': chat_id, 'text': message}).encode(),
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.load(resp).get('ok') is True
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f'WARNING: Telegram send failed: {type(exc).__name__}')
        return False


def stock(plu, codes):
    """Use bounded batches; never equate missing/null quantities with zero."""
    values = {}
    failures = 0
    # Small batches reduce request count; if server fails, do not flood with individual retries.
    for start in range(0, len(codes), 3):
        batch = codes[start:start + 3]
        try:
            data = api('inventory', {'pluCd': plu, 'bizNoArr': ','.join(batch)}, attempts=1)
            rows = data.get('stores')
            if not isinstance(rows, list):
                raise ValueError('missing stores array')
            for row in rows:
                if not isinstance(row, dict):
                    continue
                code = str(row.get('bizNo') or '').strip()
                qty = row.get('bizQty')
                if code in batch and type(qty) is int and qty >= 0:
                    values[code] = qty
            failures = 0
        except Exception as exc:
            failures += 1
            print(f'WARNING: inventory batch failed ({len(batch)} stores): {exc}')
            if failures >= 3:
                print('WARNING: 3 consecutive failed batches; stop this product to protect API')
                break
        time.sleep(1)
    return values


def main():
    stores = get_stores()
    if not stores:
        raise RuntimeError('No saved or discoverable stores')
    previous = read_json(STATE_FILE, {})
    updated = dict(previous)
    numeric = unknown = 0
    for product, plu in PRODUCTS.items():
        values = stock(plu, list(stores))
        for code, store in stores.items():
            key = f'이마트24|{code}|{plu}'
            qty = values.get(code)
            if qty is None:
                unknown += 1
                continue
            numeric += 1
            old = previous.get(key)
            if qty > 0 and (type(old) is not int or qty > old):
                message = (f'🎉 포켓몬카드 재고 발견!\n상품: {product}\n'
                           f'매장: 이마트24 {store["name"]}\n주소: {store["address"]}\n'
                           f'재고: {qty}개\n※ 방문 전 매장에 확인하세요.')
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
