"""Emart24 Pokemon card stock monitor for Namwon and Asan.
Uses a third-party public API; missing stock is never interpreted as zero.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = 'https://mcp.aka.page/api/emart24'
ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / 'state.json'
REGIONS = {'남원': '남원시', '아산': '아산시'}
PRODUCTS = {
    '초전브레이커 낱개팩': '8809945338207',
    '초전브레이커 박스': '8809945338214',
    '인페르노X 낱개팩': '8800286278535',
}


def api(path, params, attempts=2):
    url = BASE + '/' + path + '?' + urllib.parse.urlencode(params)
    last = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'PokemonStockMonitor/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=18) as response:
                result = json.load(response)
            if not isinstance(result, dict) or result.get('success') is not True:
                raise ValueError('API returned unsuccessful response')
            return result.get('data') or {}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(2)
    raise RuntimeError(f'{path} request failed: {type(last).__name__}: {last}')


def notify(message):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        print('WARNING: Telegram secrets missing; notification skipped')
        return False
    payload = urllib.parse.urlencode({'chat_id': chat_id, 'text': message}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=payload)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.load(response)
        return result.get('ok') is True
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f'WARNING: Telegram send failed: {type(exc).__name__}')
        return False


def discover_stores():
    found = {}
    for keyword, city in REGIONS.items():
        try:
            data = api('stores', {'keyword': keyword})
            results = data.get('stores', [])
            if not isinstance(results, list):
                raise ValueError('stores is not a list')
            matched = 0
            for item in results:
                if not isinstance(item, dict):
                    continue
                code = str(item.get('storeCode') or '').strip()
                address = str(item.get('address') or '')
                if code and city in address:
                    found[code] = {'name': str(item.get('storeName') or code), 'address': address}
                    matched += 1
            print(f'{city}: search returned {len(results)} stores, matched {matched}')
            if len(results) >= 100:
                print(f'WARNING: {city} store list may be truncated; check API pagination/limits')
        except Exception as exc:
            print(f'ERROR: {city} store search failed: {exc}')
    print(f'Total unique matched stores: {len(found)}')
    return found


def read_state():
    try:
        data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def fetch_inventory(plu, codes):
    """Small batches first; fall back to one store if a batch fails."""
    found = {}
    for start in range(0, len(codes), 3):
        group = codes[start:start + 3]
        try:
            data = api('inventory', {'pluCd': plu, 'bizNoArr': ','.join(group)})
            rows = data.get('stores', [])
            if not isinstance(rows, list):
                raise ValueError('inventory stores is not a list')
        except Exception as exc:
            print(f'WARNING: batch lookup failed ({len(group)} stores): {exc}')
            rows = []
            for code in group:
                try:
                    single = api('inventory', {'pluCd': plu, 'bizNoArr': code}, attempts=1)
                    rows.extend(single.get('stores') or [])
                except Exception as one_exc:
                    print(f'UNKNOWN store {code}: {one_exc}')
                time.sleep(0.4)
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get('bizNo') or '').strip()
            qty = row.get('bizQty')
            if code and type(qty) is int and qty >= 0:
                found[code] = qty
        time.sleep(0.5)
    return found


def main():
    stores = discover_stores()
    if not stores:
        raise RuntimeError('No stores found in Namwon or Asan; no inventory checked')
    previous = read_state()
    updated = dict(previous)
    count = 0
    unknown = 0
    for product, plu in PRODUCTS.items():
        inventory = fetch_inventory(plu, list(stores))
        for code, store in stores.items():
            key = f'이마트24|{code}|{plu}'
            qty = inventory.get(code)
            if qty is None:
                unknown += 1
                print(f'UNKNOWN {product} | {store["name"]}: None')
                continue
            count += 1
            old = previous.get(key)
            print(f'{product} | {store["name"]} | {qty}개 (previous={old})')
            if qty > 0 and (not isinstance(old, int) or qty > old):
                msg = (f'🎉 포켓몬카드 재고 발견!\n상품: {product}\n편의점: 이마트24\n'
                       f'매장: {store["name"]}\n주소: {store["address"]}\n'
                       f'수량: {qty}개\n조회: {datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")}\n'
                       '※ 방문 전 매장에 확인하세요.')
                if not notify(msg):
                    print(f'WARNING: notification not delivered for {key}; keeping previous state')
                    continue
            updated[key] = qty
    # Existing workflow must commit state.json for persistence across runs.
    STATE_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Finished: {count} numeric inventory entries, {unknown} unknown entries')


if __name__ == '__main__':
    main()
