"""Emart24 Pokemon card stock watcher (verified Namwon pilot stores)."""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / 'state.json'
API = 'https://mcp.aka.page/api/emart24/inventory'
PRODUCTS = {
    '8809945338207': '초전브레이커 낱개팩',
    '8809945338214': '초전브레이커 박스',
    '8800286278535': '인페르노X 낱개팩',
}
# Verified in user-provided API responses. Expand only after checking other store IDs.
STORES = {
    '21475': 'R남원이그린점',
    '21598': '남원중앙하이츠점',
    '22612': '남원센트럴점',
    '23439': '남원요천로점',
    '24252': '남원도통점',
}

def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'PokemonStockMonitor/1.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)

def telegram(message):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        raise RuntimeError('Missing Telegram secrets')
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': message}).encode('utf-8')
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=data)
    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.load(response)
    if not result.get('ok'):
        raise RuntimeError('Telegram rejected message')

def main():
    previous = json.loads(STATE_FILE.read_text(encoding='utf-8')) if STATE_FILE.exists() else {}
    updated = dict(previous)
    checked = 0
    for plu, product in PRODUCTS.items():
        params = urllib.parse.urlencode({'pluCd': plu, 'bizNoArr': ','.join(STORES)})
        payload = get_json(f'{API}?{params}')
        if payload.get('success') is not True:
            raise RuntimeError(f'Inventory API failed: {product}')
        data = payload.get('data') or {}
        inventory = data.get('stores')
        if not isinstance(inventory, list) or not inventory:
            raise RuntimeError(f'No store inventory returned for {product}; refusing to mark as sold out')
        for store in inventory:
            biz_no = str(store.get('bizNo', ''))
            if biz_no not in STORES:
                continue
            qty = store.get('bizQty')
            if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
                print(f'UNKNOWN {product} {STORES[biz_no]}: {qty!r}')
                continue
            checked += 1
            key = f'emart24|{biz_no}|{plu}'
            old = previous.get(key)
            print(f'{product} | {STORES[biz_no]} | {qty}개 (previous={old})')
            if qty > 0 and (old is None or (isinstance(old, int) and qty > old)):
                name = store.get('storeName') or STORES[biz_no]
                address = store.get('address') or '주소 미확인'
                telegram(f'🎉 포켓몬카드 재고 발견!\n편의점: 이마트24\n매장: {name}\n주소: {address}\n상품: {product}\n재고: {qty}개\n조회: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}\n※ 방문 전 매장 확인 필수')
            updated[key] = qty
    if checked == 0:
        raise RuntimeError('No numeric inventory received; state not changed')
    if updated != previous:
        STATE_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Finished: {checked} numeric inventory entries')

if __name__ == '__main__':
    main()
