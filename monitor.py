"""Jeonbuk Pokemon 30th anniversary stock monitor: safe integration scaffold."""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
STATE = ROOT / 'state.json'


def telegram(message):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        raise RuntimeError('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID secrets')
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': message}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=data)
    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.load(response)
    if not result.get('ok'):
        raise RuntimeError('Telegram rejected the message')


def load_stock():
    """Return stock records only from VERIFIED, permitted store integrations.

    Expected record keys: chain, store, address, product, quantity, checked_at.
    IMPORTANT: No CU, GS25 or emart24 integration has been verified yet.
    Never treat unavailable data as zero stock.
    """
    return []


def main():
    if '--test-telegram' in sys.argv:
        telegram('✅ 포켓몬카드 30주년 재고 알리미 테스트 성공!\n대상: 전북특별자치도 / CU·GS25·이마트24\n※ 실제 재고조회 연동은 아직 준비 중입니다.')
        print('Telegram test sent')
        return
    records = load_stock()
    if not records:
        print('No verified store data source connected; no stock claims or alerts sent.')
        return
    # This section activates only when verified adapters return actual observations.
    previous = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    updated = dict(previous)
    for r in records:
        if not all(k in r for k in ('chain', 'store', 'address', 'product', 'quantity', 'checked_at')):
            continue
        if not isinstance(r['quantity'], int) or r['quantity'] < 0:
            continue
        if r['chain'] not in CONFIG['chains']:
            continue
        if not any(x in r['product'].lower() for x in CONFIG['product_keywords']):
            continue
        if not any(x in r['address'] for x in CONFIG['region_address_keywords']):
            continue
        key = '|'.join([r['chain'], r['store'], r['product']])
        old = previous.get(key)
        qty = r['quantity']
        if qty > 0 and (old is None or qty > old):
            telegram(f"🎉 포켓몬카드 30주년 재고 발견\n편의점: {r['chain']}\n매장: {r['store']}\n주소: {r['address']}\n상품: {r['product']}\n수량: {qty}개\n조회: {r['checked_at']}\n※ 방문 전 매장에 확인하세요.")
        updated[key] = qty
    STATE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Processed {len(records)} records')


if __name__ == '__main__':
    main()
