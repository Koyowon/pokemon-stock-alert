#!/usr/bin/env python3
"""GS25 four-region third-party inventory watcher. Baseline first; Telegram on new positives."""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'config.json'
STATE = ROOT / 'gs25_stock_state.json'
API = 'https://mcp.aka.page/api/actions/query'
KEYWORDS = {
    'namwon': ['남원', 'GS25남원', '남원시'],
    'asan': ['아산', 'GS25아산', '배방', '탕정', '온양'],
    'jeonju': ['전주', 'GS25전주', '효자', '송천', '서신'],
    'jeju': ['GS25제주', '제주봉성점', '제주', '제주시', '애월', '연동', '노형', '서귀포'],
}


def api_query(code, term):
    url = API + '?' + urllib.parse.urlencode({'action': 'gs25CheckInventory', 'format': 'json', 'itemCode': code, 'storeKeyword': term, 'storeLimit': 100})
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'gs25-stock-monitor/1.0'})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=18) as response:
                raw = response.read(800001)
                if response.status != 200 or len(raw) > 800000:
                    raise ValueError('HTTP_OR_SIZE')
            data = json.loads(raw.decode('utf-8'))
            if not isinstance(data, dict) or data.get('success') is not True or data.get('error') or data.get('isError'):
                raise ValueError('API_FAILURE')
            inv = data.get('data', {}).get('inventory')
            rows = inv.get('stores') if isinstance(inv, dict) else None
            if not isinstance(rows, list):
                raise ValueError('MISSING_STORES')
            return rows
        except (OSError, ValueError, UnicodeError, TimeoutError) as exc:
            if attempt:
                raise RuntimeError(type(exc).__name__) from exc
            time.sleep(1)


def quantity(row):
    value = row.get('realStockQuantity')
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r'\d+', value):
        return int(value)
    return None


def safe(value):
    return re.sub(r'\s+', ' ', ''.join(c for c in str(value) if c.isprintable()))[:80]


def telegram(message):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        raise RuntimeError('TELEGRAM_SECRETS_MISSING')
    body = urllib.parse.urlencode({'chat_id': chat_id, 'text': message, 'disable_web_page_preview': 'true'}).encode()
    req = urllib.request.Request('https://api.telegram.org/bot' + token + '/sendMessage', data=body, method='POST')
    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.loads(response.read(100000))
    if result.get('ok') is not True:
        raise RuntimeError('TELEGRAM_SEND_FAILED')


def main():
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    assert config['provider'] == 'GS25'
    code = config['item_code']
    assert re.fullmatch(r'\d{8,14}', code)
    enabled = [r for r in config['regions'] if r.get('enabled')]
    assert enabled and all(r['id'] in KEYWORDS for r in enabled)
    if STATE.exists():
        previous = json.loads(STATE.read_text(encoding='utf-8'))
        if previous.get('item_code') != code:
            raise RuntimeError('STATE_ITEM_CODE_MISMATCH')
    else:
        previous = {'version': 1, 'item_code': code, 'regions': {}}
    new_state = {'version': 1, 'item_code': code, 'regions': dict(previous.get('regions', {})), 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    failures = 0
    alerts = 0
    for region in enabled:
        rid = region['id']
        seen = {}
        failed = False
        for term in KEYWORDS[rid]:
            try:
                rows = api_query(code, term)
            except RuntimeError as exc:
                print(f'QUERY_ERROR region={rid} term={term} error={exc}', flush=True)
                failed = True
                failures += 1
                continue
            if len(rows) >= 100:
                print(f'QUERY_LIMIT region={rid} term={term}; no safe region update', flush=True)
                failed = True
                failures += 1
            for row in rows:
                if not isinstance(row, dict):
                    continue
                sid = safe(row.get('storeCode', ''))
                name = safe(row.get('storeName') or row.get('name') or '')
                q = quantity(row)
                if not sid or not name or q is None:
                    continue
                if sid not in seen or q > seen[sid]['quantity']:
                    seen[sid] = {'name': name, 'quantity': q}
        positives = {sid: item for sid, item in seen.items() if item['quantity'] > 0}
        print(f'REGION region={rid} scanned={len(seen)} positive={len(positives)} complete={not failed}', flush=True)
        for sid, item in sorted(positives.items()):
            print(f'POSITIVE region={rid} store={item["name"]} code={sid} qty={item["quantity"]}', flush=True)
        if failed:
            print(f'SKIP_REGION_STATE region={rid} reason=PARTIAL_SCAN', flush=True)
            continue
        prior = previous.get('regions', {}).get(rid)
        if prior is None:
            print(f'BASELINE region={rid} positive={len(positives)} no_initial_alert', flush=True)
        else:
            old = prior.get('positive', {})
            changes = [(sid, item) for sid, item in positives.items() if sid not in old or int(old[sid]['quantity']) == 0]
            if changes:
                lines = [f'🚨 GS25 포켓몬 30주년 후보 재고 감지 | {region["name"]}', f'조회 코드: {code}']
                lines += [f'{item["name"]}: {item["quantity"]}개 (매장 {sid})' for sid, item in sorted(changes)[:25]]
                if len(changes) > 25:
                    lines.append(f'그 외 {len(changes)-25}곳은 GitHub 로그 확인')
                lines.append('제3자 API 기준 / 실제 판매재고 확인 필요')
                telegram('\n'.join(lines))
                alerts += 1
                print(f'ALERT_SENT region={rid} new_positive={len(changes)}', flush=True)
        new_state['regions'][rid] = {'positive': positives, 'checked_at_utc': new_state['checked_at_utc']}
    if new_state['regions'] != previous.get('regions', {}):
        STATE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print('STATE_WRITTEN', flush=True)
    print(f'FINAL errors={failures} alerts={alerts} state={STATE.name}', flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
