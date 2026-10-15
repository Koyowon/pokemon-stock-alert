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
from urllib.parse import quote
from pathlib import Path

ROOT = Path(__file__).resolve().parent
from gs25_asan_guard import filter_asan_seen
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



def naver_map(name, address=''):
    return 'https://map.naver.com/p/search/' + quote((address or name).strip(), safe='')

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
    sys.path.insert(0, str(ROOT.parent))
    from unified_settings import enabled as unified_enabled
    active = unified_enabled('gs25', {r['id'] for r in config['regions'] if r.get('enabled')})
    enabled = [r for r in config['regions'] if r['id'] in active]
    assert all(r['id'] in KEYWORDS for r in enabled)
    if not enabled:
        print('GS25_ALL_REGIONS_OFF'); return 0
    if STATE.exists():
        previous = json.loads(STATE.read_text(encoding='utf-8'))
        if previous.get('item_code') != code:
            raise RuntimeError('STATE_ITEM_CODE_MISMATCH')
    else:
        previous = {'version': 1, 'item_code': code, 'regions': {}}
    new_state = {'version': 2, 'item_code': code, 'regions': dict(previous.get('regions', {})), 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    failures = 0
    alerts = 0
    for region in enabled:
        rid = region['id']
        seen = {}
        conflicts = set()
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
                if not sid or not name or q is None or sid in conflicts:
                    continue
                if sid in seen and seen[sid]['quantity'] != q:
                    conflicts.add(sid)
                    seen.pop(sid, None)
                    print(f'STOCK_CONFLICT region={rid} store={sid}', flush=True)
                else:
                    seen[sid] = {'name': name, 'quantity': q}
        if rid == 'asan' and not failed:
            prior_asan = previous.get('regions', {}).get('asan')
            before_guard = len(seen)
            seen = filter_asan_seen(seen, prior_asan)
            print(f'ASAN_GUARD kept={len(seen)} excluded={before_guard - len(seen)}', flush=True)
        positives = {sid: item for sid, item in seen.items() if item['quantity'] > 0}
        print(f'REGION region={rid} scanned={len(seen)} positive={len(positives)} complete={not failed} conflicts={len(conflicts)}', flush=True)
        if failed:
            print(f'SKIP_REGION_STATE region={rid} reason=PARTIAL_SCAN', flush=True)
            continue
        prior = previous.get('regions', {}).get(rid)
        if prior is None:
            print(f'BASELINE region={rid} positive={len(positives)} no_initial_alert', flush=True)
            # First scan is baseline: do not send a flood of notifications.
        else:
            # Version 1 persisted positives only; missing old stores are unknown, not zero.
            old = prior.get('stores', prior.get('positive', {}))
            changes = []
            for sid, item in sorted(seen.items()):
                q = item['quantity']
                former = old.get(sid)
                if former is None:
                    if q > 0:
                        changes.append((sid, item, None))
                    continue
                prev_q = int(former['quantity'])
                if q != prev_q:
                    changes.append((sid, item, prev_q))
            # Only observed numeric quantities count as zero; absent stores are unknown.
            for sid, item, prev_q in changes:
                q = item['quantity']
                title = ('🟢 GS25 포켓몬카드 입고/증가!' if prev_q is None or q > prev_q
                         else '🔴 GS25 포켓몬카드 품절 확인!' if q == 0
                         else '🟠 GS25 포켓몬카드 재고 감소!')
                detail = f'현재 재고: {q}개' if prev_q is None else f'이전 재고: {prev_q}개 → 현재 재고: {q}개'
                msg = (f'{title}\n지역: {region["name"]}\n매장: GS25 {item["name"]}\n'
                       f'조회 코드: {code}\n{detail}\n'
                       f'🗺 네이버지도: {naver_map("GS25 " + item["name"])}\n'
                       '※ 제3자 API 기준이며, 방문 전 매장에 실제 재고를 확인하세요.')
                try:
                    telegram(msg)
                except (OSError, ValueError, RuntimeError) as exc:
                    print(f'ALERT_FAILED region={rid} store={sid} error={type(exc).__name__}', flush=True)
                    # Avoid advancing this store's baseline if the alert was not sent.
                    former = old.get(sid)
                    if former is None:
                        seen.pop(sid, None)
                    else:
                        seen[sid] = former
                    continue
                alerts += 1
                print(f'ALERT_SENT region={rid} store={sid} old={prev_q} new={q}', flush=True)
        # Keep prior observations for stores absent from this scan, but never infer zero.
        prior_stores = prior.get('stores', prior.get('positive', {})) if prior else {}
        merged = dict(prior_stores)
        merged.update(seen)
        new_state['regions'][rid] = {'stores': merged, 'checked_at_utc': new_state['checked_at_utc']}
    changed = new_state['regions'] != previous.get('regions', {})
    if changed:
        # Publish valid complete regions even when other regions failed.
        # This advances baselines for successfully sent alerts, reducing repeats.
        tmp = STATE.with_suffix('.tmp')
        tmp.write_text(json.dumps(new_state, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        tmp.replace(STATE)
        print('STATE_WRITTEN', flush=True)
    print(f'FINAL errors={failures} alerts={alerts} state={STATE.name}', flush=True)
    if failures and changed:
        print('GS25_PARTIAL_SUCCESS: completed regions saved; failed regions preserved', flush=True)
        return 0
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
