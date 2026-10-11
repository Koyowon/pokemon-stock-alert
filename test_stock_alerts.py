#!/usr/bin/env python3
"""Non-destructive integration simulation: no live inventory queries or state writes."""
import importlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CASES = [(0, 5, '🟢'), (5, 4, '🟠'), (4, 0, '🔴')]
BARCODE = '8800286275732'


def check(message, old, new, icon):
    assert icon in message, (old, new, message)
    assert f'{old}개' in message and f'{new}개' in message, message
    assert 'https://map.naver.com/p/search/' in message, message
    assert '※' in message, message


def emart(tmp):
    mod = importlib.import_module('monitor')
    store = {'name': '테스트남원점', 'address': '전북특별자치도 남원시 테스트로 1'}
    messages = []
    state = tmp / 'emart.json'
    with patch.object(mod, 'STATE_FILE', state), patch.object(mod, 'get_stores', return_value={'TEST001': store}), \
         patch.object(mod, 'notify', side_effect=lambda msg: messages.append(msg) or True), \
         patch('unified_settings.enabled', return_value={'namwon'}), \
         patch.object(mod, 'load_enabled_regions', return_value={'namwon'}):
        for old, new, icon in CASES:
            state.write_text(json.dumps({f'이마트24|TEST001|{BARCODE}': old}), encoding='utf-8')
            with patch.object(mod, 'stock', return_value=({'TEST001': new}, {'TEST001': 'OK'})):
                mod.main()
            check(messages[-1], old, new, icon)
    return messages


def cu(tmp):
    mod = importlib.import_module('cu_stock_monitor')
    messages = []
    state = tmp / 'cu.json'
    item = {'code': '99999', 'name': '테스트남원점', 'address': '전북특별자치도 남원시 테스트로 1', 'city': '남원'}
    with patch.object(mod, 'STATE_FILE', state), patch.object(mod, 'POINTS', {'남원': [(35.416, 127.39)]}), \
         patch.object(mod, 'telegram', side_effect=lambda msg: messages.append(msg) or True), \
         patch('unified_settings.enabled', return_value={'namwon'}), \
         patch.object(mod, 'load_enabled_regions', return_value={'namwon'}):
        for old, new, icon in CASES:
            state.write_text(json.dumps({'stores': {'99999': {**item, 'stock': old, 'alerted': True}}}), encoding='utf-8')
            with patch.object(mod, 'query', return_value=[{**item, 'stock': new}]):
                mod.main()
            check(messages[-1], old, new, icon)
    return messages


def gs25(tmp):
    mod = importlib.import_module('gs25_independent.gs25_auto_monitor')
    messages = []
    state = tmp / 'gs25.json'
    config = tmp / 'gs25_config.json'
    config.write_text(json.dumps({'provider': 'GS25', 'item_code': BARCODE, 'regions': [{'id': 'namwon', 'name': '남원', 'enabled': True}]}), encoding='utf-8')
    with patch.object(mod, 'STATE', state), patch.object(mod, 'CONFIG', config), \
         patch.object(mod, 'KEYWORDS', {'namwon': ['TEST']}), \
         patch.object(mod, 'telegram', side_effect=lambda msg: messages.append(msg)), \
         patch('unified_settings.enabled', return_value={'namwon'}):
        for old, new, icon in CASES:
            state.write_text(json.dumps({'version': 2, 'item_code': BARCODE, 'regions': {'namwon': {'stores': {'99999': {'name': '테스트남원점', 'quantity': old}}}}}), encoding='utf-8')
            with patch.object(mod, 'api_query', return_value=[{'storeCode': '99999', 'storeName': '테스트남원점', 'realStockQuantity': new}]):
                assert mod.main() == 0
            check(messages[-1], old, new, icon)
    return messages


def send_telegram(message):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        raise RuntimeError('Telegram secrets missing')
    payload = urlencode({'chat_id': chat, 'text': message, 'disable_web_page_preview': 'true'}).encode()
    with urlopen(Request('https://api.telegram.org/bot' + token + '/sendMessage', data=payload), timeout=20) as response:
        result = json.load(response)
    if result.get('ok') is not True:
        raise RuntimeError('Telegram send failed')


def main():
    with tempfile.TemporaryDirectory(prefix='pokemon-alert-test-') as directory:
        tmp = Path(directory)
        results = {'이마트24': emart(tmp), 'CU': cu(tmp), 'GS25': gs25(tmp)}
    for chain, messages in results.items():
        print('TEST_PASS', chain, '0->5 5->4 4->0', 'NAVER_MAP=OK', flush=True)
        assert len(messages) == 3
    summary = ('🧪 [테스트] 포켓몬카드 재고 변동 알림 검증 성공\n'
               '⚠️ 실제 재고·실제 매장이 아닙니다.\n\n'
               '🟢 이마트24: 0개 → 5개 (입고)\n'
               '🟠 CU: 5개 → 4개 (재고 감소)\n'
               '🔴 GS25: 4개 → 0개 (품절)\n\n'
               '각 편의점에서 세 가지 변화(총 9개)와 네이버지도 링크 생성까지 자동 검증했습니다.\n'
               '🗺 네이버지도 링크 예시 (가상 주소):\n'
               'https://map.naver.com/p/search/%EC%A0%84%EB%B6%81%ED%8A%B9%EB%B3%84%EC%9E%90%EC%B9%98%EB%8F%84%20%EB%82%A8%EC%9B%90%EC%8B%9C\n\n'
               '실제 재고 기록 파일은 변경하지 않았습니다.')
    send_telegram(summary)
    print('TELEGRAM_TEST_SENT', flush=True)


if __name__ == '__main__':
    main()
