"""Telegram inline keyboard polling; only this workflow consumes getUpdates."""
import json, os, urllib.parse, urllib.request, urllib.error
from pathlib import Path
from unified_settings import CONTROL, IDS, CHAINS, load
from stock_snapshot_report import messages as stock_messages

ROOT = Path(__file__).resolve().parent
CURSOR = ROOT / 'telegram_control_cursor.json'
LABEL = {'emart24': '이마트24', 'cu': 'CU', 'gs25': 'GS25'}
CITY = {'namwon': '남원', 'asan': '아산', 'jeonju': '전주', 'jeju': '제주'}
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
CHAT = os.getenv('TELEGRAM_CHAT_ID', '')


def api(method, **kwargs):
    req = urllib.request.Request('https://api.telegram.org/bot' + TOKEN + '/' + method,
                                 data=urllib.parse.urlencode(kwargs).encode())
    with urllib.request.urlopen(req, timeout=25) as response:
        result = json.load(response)
    if result.get('ok') is not True:
        raise RuntimeError('Telegram ' + method + ' failed')
    return result['result']


def best_effort(method, **kwargs):
    try:
        return api(method, **kwargs)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        print('TELEGRAM_OPTIONAL_FAILED', method, type(exc).__name__, flush=True)
        return None


def save_progress(data, cursor):
    CONTROL.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    CURSOR.write_text(json.dumps(cursor, indent=2) + '\n', encoding='utf-8')


def initial():
    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))
    shared = {r['id']: r['enabled'] for r in read(ROOT / 'region_settings.json')['regions']}
    gs = {r['id']: r['enabled'] for r in read(ROOT / 'gs25_independent/config.json')['regions']}
    return {'version': 1, 'chains': {'emart24': dict(shared), 'cu': dict(shared), 'gs25': dict(gs)}}


def panel(data):
    lines = ['🏪 포켓몬카드 통합 감시 설정', '버튼을 누르면 해당 편의점·지역 감시를 변경합니다.']
    buttons = []
    for chain in CHAINS:
        lines.append('\n' + LABEL[chain])
        buttons.append([{'text': ('🟢 ' if data['chains'][chain][rid] else '⚪ ') + CITY[rid],
                         'callback_data': 'set:' + chain + ':' + rid} for rid in IDS])
    buttons.append([{'text': '📦 현재 재고 현황', 'callback_data': 'stock:all'}])
    lines.append('\n📦 현재 재고 현황: 마지막 저장 수량 조회 (실시간 아님)')
    lines.append('5분 주기 예약 실행은 GitHub 상황에 따라 지연될 수 있습니다.')
    return '\n'.join(lines), json.dumps({'inline_keyboard': buttons}, ensure_ascii=False)


def send_stock():
    for text in stock_messages():
        api('sendMessage', chat_id=CHAT, text=text, parse_mode='HTML', disable_web_page_preview='true')


def main():
    if not TOKEN or not CHAT:
        raise RuntimeError('Telegram secrets missing')
    data = load() or initial()
    cursor = json.loads(CURSOR.read_text(encoding='utf-8')) if CURSOR.exists() else {'offset': 0}
    updates = api('getUpdates', offset=cursor['offset'], timeout=0, limit=100,
                  allowed_updates=json.dumps(['message', 'callback_query']))
    changed = False
    for update in updates:
        uid = update['update_id']
        cursor['offset'] = max(cursor['offset'], uid + 1)
        msg = update.get('message') or {}
        cb = update.get('callback_query') or {}
        if cb:
            cbchat = str((cb.get('message') or {}).get('chat', {}).get('id', ''))
            if cbchat != CHAT:
                best_effort('answerCallbackQuery', callback_query_id=cb['id'], text='권한이 없습니다', show_alert='true')
                continue
            parts = cb.get('data', '').split(':')
            if parts == ['stock', 'all']:
                best_effort('answerCallbackQuery', callback_query_id=cb['id'], text='저장된 재고를 조회합니다')
                send_stock()
            elif len(parts) == 3 and parts[0] == 'set' and parts[1] in CHAINS and parts[2] in IDS:
                chain, rid = parts[1:]
                data['chains'][chain][rid] = not data['chains'][chain][rid]
                changed = True
                best_effort('answerCallbackQuery', callback_query_id=cb['id'],
                            text=LABEL[chain] + ' ' + CITY[rid] + ' ' + ('ON' if data['chains'][chain][rid] else 'OFF'))
                text, markup = panel(data)
                best_effort('sendMessage', chat_id=CHAT, text=text, reply_markup=markup)
            else:
                best_effort('answerCallbackQuery', callback_query_id=cb['id'], text='알 수 없는 명령')
        elif str(msg.get('chat', {}).get('id', '')) == CHAT:
            command = msg.get('text', '').split('@')[0].split(' ')[0]
            if command in ('/regions', '/status', '/start'):
                text, markup = panel(data)
                api('sendMessage', chat_id=CHAT, text=text, reply_markup=markup)
            elif command == '/stock':
                send_stock()
    save_progress(data, cursor)
    if changed:
        print('CONTROL_SAVED', flush=True)
    print('TELEGRAM_UPDATES', len(updates), 'OFFSET', cursor['offset'])


if __name__ == '__main__':
    main()
