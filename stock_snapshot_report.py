"""Read-only inventory snapshots for the Telegram control bot."""
import json
from html import escape
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
REGIONS = {'namwon': '남원', 'asan': '아산', 'jeonju': '전주', 'jeju': '제주'}
CHAINS = {'emart24': '이마트24', 'cu': 'CU', 'gs25': 'GS25'}
BARCODE = '8800286275732'
HOLD_UNVERIFIED_CU_CODES = frozenset({'41691', '27756', '40840'})
KST = timezone(timedelta(hours=9))
PAGES_URL = 'https://koyowon.github.io/pokemon-stock-alert/'


def read(relative):
    try:
        value = json.loads((ROOT / relative).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def region_for(address, city=''):
    combined = str(address) + ' ' + str(city)
    return next((rid for rid, name in REGIONS.items() if name in combined), None)


def map_bridge(chain, name, address=''):
    query = (str(address) + ' ' + str(name)).strip() if address else CHAINS[chain] + ' ' + str(name)
    return PAGES_URL + '?q=' + quote(query, safe='')


def checked_at(value):
    if not value:
        return '확인 시각 미기록'
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(KST).strftime('%Y-%m-%d %H:%M KST')
    except (TypeError, ValueError):
        return '확인 시각 미기록'


def collect():
    result = {rid: {chain: [] for chain in CHAINS} for rid in REGIONS}
    stores = read('stores.json').get('stores', {})
    for key, quantity in read('state.json').items():
        if not isinstance(key, str) or type(quantity) is not int or quantity <= 0:
            continue
        parts = key.split('|')
        if len(parts) != 3 or parts[0] not in ('이마트24', 'emart24') or parts[2] != BARCODE:
            continue
        store = stores.get(parts[1], {})
        if not isinstance(store, dict):
            continue
        name, address = store.get('name', ''), store.get('address', '')
        rid = region_for(address)
        if rid and name:
            result[rid]['emart24'].append((name, quantity, address, '확인 시각 미기록'))

    for code, store in read('cu_stock_state.json').get('stores', {}).items():
        if str(code) in HOLD_UNVERIFIED_CU_CODES:
            continue
        if not isinstance(store, dict):
            continue
        quantity = store.get('stock')
        if type(quantity) is not int or quantity <= 0:
            continue
        name, address = store.get('name', ''), store.get('address', '')
        rid = region_for(address, store.get('city', ''))
        if rid and name:
            result[rid]['cu'].append((name, quantity, address, '확인 시각 미기록'))

    gs = read('gs25_independent/gs25_stock_state.json')
    if gs.get('item_code') == BARCODE:
        for rid, block in gs.get('regions', {}).items():
            if rid not in result or not isinstance(block, dict):
                continue
            checked = checked_at(block.get('checked_at_utc') or gs.get('checked_at_utc'))
            for store in block.get('stores', {}).values():
                if not isinstance(store, dict):
                    continue
                quantity, name = store.get('quantity'), store.get('name', '')
                if type(quantity) is int and quantity > 0 and name:
                    result[rid]['gs25'].append((name, quantity, '', checked))
    return result


def messages():
    data = collect()
    output = [
        '📦 현재 재고 현황 (마지막 저장 기록)\n'
        '⚠️ 실시간 조회가 아니며 구매 가능 수량을 보장하지 않습니다.\n'
        '양수 재고가 저장된 매장만 표시합니다.\n'
        '이마트24·CU는 매장별 확인 시각이 기록되지 않습니다.'
    ]
    for chain, label in CHAINS.items():
        lines = ['🏪 ' + label + ' 재고 현황']
        total = 0
        for rid, city in REGIONS.items():
            rows = sorted(data[rid][chain], key=lambda item: (-item[1], item[0]))
            if not rows:
                continue
            total += len(rows)
            lines.append('\n📍 ' + city + ' | ' + str(len(rows)) + '개 매장')
            for name, quantity, address, checked in rows:
                lines.append('• ' + escape(str(name)) + ' — ' + str(quantity) + '개')
                if checked != '확인 시각 미기록':
                    lines.append('  ' + checked)
                lines.append('  <a href="' + escape(map_bridge(chain, name, address), quote=True) + '">🗺 네이버지도에서 보기</a>')
        if not total:
            continue
        chunk = ''
        for line in lines:
            addition = line + '\n'
            if chunk and len(chunk) + len(addition) > 3400:
                output.append(chunk.rstrip())
                chunk = '🏪 ' + label + ' (계속)\n'
            chunk += addition
        if chunk:
            output.append(chunk.rstrip())
    if len(output) == 1:
        output.append('현재 저장된 양수 재고가 없습니다. 품절 여부는 별도 확인이 필요합니다.')
    return output
