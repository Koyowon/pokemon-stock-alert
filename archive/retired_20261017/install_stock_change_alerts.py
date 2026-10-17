"""One-time, idempotent upgrade of stock-change alerts and Naver map links."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent

def replace_once(src, old, new, label):
    if new in src:
        print('ALREADY_PATCHED', label)
        return src
    if src.count(old) != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {src.count(old)}; no file written')
    return src.replace(old, new, 1)

naver_import = 'from urllib.parse import quote\n'
naver_func = '''\ndef naver_map(name, address=''):\n    return 'https://map.naver.com/p/search/' + quote((address or name).strip(), safe='')\n'''

p = ROOT / 'monitor.py'
s = p.read_text(encoding='utf-8')
s = replace_once(s, 'from region_config import load_enabled_regions\n', 'from region_config import load_enabled_regions\n'+naver_import, 'emart-import')
s = replace_once(s, 'def notify(message):\n', naver_func+'\ndef notify(message):\n', 'emart-helper')
s = replace_once(s, 'message += "\\n※ 조회 시점의 수량이며, 방문 전 매장에 확인하세요."', 'message += "\\n🗺 네이버지도: " + naver_map(store["name"], store["address"])\n                message += "\\n※ 조회 시점의 수량이며, 방문 전 매장에 확인하세요."', 'emart-map')
ast.parse(s); p.write_text(s, encoding='utf-8'); print('PATCHED',p.name)

p = ROOT / 'cu_stock_monitor.py'
s = p.read_text(encoding='utf-8')
s = replace_once(s, 'from region_config import load_enabled_regions\n', 'from region_config import load_enabled_regions\n'+naver_import, 'cu-import')
s = replace_once(s, 'def telegram(message):\n', naver_func+'\ndef telegram(message):\n', 'cu-helper')
start = s.index('        should_alert = (\n')
end = s.index('        state["stores"][code] = {\n',start)
old = s[start:end]
new = '''        # An absent old quantity is unknown, not zero. Preserve first-positive alerts.\n        # Previously alerted flag is retained for compatibility with the old state.\n        message = None\n        if previous is None:\n            if quantity > 0:\n                message = "🟢 CU 포켓몬카드 첫 재고 확인!"\n        elif quantity > previous:\n            message = "🟢 CU 포켓몬카드 재고 입고/증가!"\n        elif quantity < previous:\n            message = ("🔴 CU 포켓몬카드 품절 확인!" if quantity == 0\n                       else "🟠 CU 포켓몬카드 재고 감소!")\n        elif quantity > 0 and not previously_alerted:\n            # Migrated old state: retry an unsent first-positive alert.\n            message = "🟢 CU 포켓몬카드 재고 확인!"\n\n        alerted = previously_alerted if quantity > 0 else False\n        if message is not None:\n            if previous is None:\n                detail = f"현재 재고: {quantity}개"\n            else:\n                detail = f"이전 재고: {previous}개 → 현재 재고: {quantity}개"\n            body = (\n                message + "\\n"\n                + "상품: " + PRODUCT + "\\n"\n                + "바코드: " + BARCODE + "\\n"\n                + "지역: " + item["city"] + "\\n"\n                + "매장: " + item["name"] + "\\n"\n                + "주소: " + item["address"] + "\\n"\n                + detail + "\\n"\n                + "🗺 네이버지도: " + naver_map(item["name"], item["address"]) + "\\n"\n                + "※ 조회 시점의 수량이며, 방문 전 매장에 확인하세요."\n            )\n            if telegram(body):\n                alerted = quantity > 0\n                print("ALERT_SENT:", code, previous, quantity, flush=True)\n            else:\n                print("ALERT_PENDING:", code, flush=True)\n                continue\n\n'''
if '🗺 네이버지도:' not in s:
    s = s[:start] + new + s[end:]
else:
    print('ALREADY_PATCHED cu-alert')
ast.parse(s); p.write_text(s, encoding='utf-8'); print('PATCHED',p.name)

p = ROOT / 'gs25_independent' / 'gs25_auto_monitor.py'
s = p.read_text(encoding='utf-8')
s = replace_once(s, 'import urllib.request\n', 'import urllib.request\n'+naver_import, 'gs-import')
s = replace_once(s, 'def telegram(message):\n', naver_func+'\ndef telegram(message):\n', 'gs-helper')
s = replace_once(s, "    new_state = {'version': 1,", "    new_state = {'version': 2,", 'gs-version')
start = s.index('        seen = {}\n')
end = s.index('    if new_state[\'regions\'] != previous.get(\'regions\', {}):\n',start)
old = s[start:end]
new = '''        seen = {}\n        conflicts = set()\n        failed = False\n        for term in KEYWORDS[rid]:\n            try:\n                rows = api_query(code, term)\n            except RuntimeError as exc:\n                print(f'QUERY_ERROR region={rid} term={term} error={exc}', flush=True)\n                failed = True\n                failures += 1\n                continue\n            if len(rows) >= 100:\n                print(f'QUERY_LIMIT region={rid} term={term}; no safe region update', flush=True)\n                failed = True\n                failures += 1\n            for row in rows:\n                if not isinstance(row, dict):\n                    continue\n                sid = safe(row.get('storeCode', ''))\n                name = safe(row.get('storeName') or row.get('name') or '')\n                q = quantity(row)\n                if not sid or not name or q is None or sid in conflicts:\n                    continue\n                if sid in seen and seen[sid]['quantity'] != q:\n                    conflicts.add(sid)\n                    seen.pop(sid, None)\n                    print(f'STOCK_CONFLICT region={rid} store={sid}', flush=True)\n                else:\n                    seen[sid] = {'name': name, 'quantity': q}\n        positives = {sid: item for sid, item in seen.items() if item['quantity'] > 0}\n        print(f'REGION region={rid} scanned={len(seen)} positive={len(positives)} complete={not failed} conflicts={len(conflicts)}', flush=True)\n        if failed:\n            print(f'SKIP_REGION_STATE region={rid} reason=PARTIAL_SCAN', flush=True)\n            continue\n        prior = previous.get('regions', {}).get(rid)\n        if prior is None:\n            print(f'BASELINE region={rid} positive={len(positives)} no_initial_alert', flush=True)\n            # First scan is baseline: do not send a flood of notifications.\n        else:\n            # Version 1 persisted positives only; missing old stores are unknown, not zero.\n            old = prior.get('stores', prior.get('positive', {}))\n            changes = []\n            for sid, item in sorted(seen.items()):\n                q = item['quantity']\n                former = old.get(sid)\n                if former is None:\n                    if q > 0:\n                        changes.append((sid, item, None))\n                    continue\n                prev_q = int(former['quantity'])\n                if q != prev_q:\n                    changes.append((sid, item, prev_q))\n            # Only observed numeric quantities count as zero; absent stores are unknown.\n            for sid, item, prev_q in changes:\n                q = item['quantity']\n                title = ('🟢 GS25 포켓몬카드 입고/증가!' if prev_q is None or q > prev_q\n                         else '🔴 GS25 포켓몬카드 품절 확인!' if q == 0\n                         else '🟠 GS25 포켓몬카드 재고 감소!')\n                detail = f'현재 재고: {q}개' if prev_q is None else f'이전 재고: {prev_q}개 → 현재 재고: {q}개'\n                msg = (f'{title}\\n지역: {region["name"]}\\n매장: GS25 {item["name"]}\\n'\n                       f'조회 코드: {code}\\n{detail}\\n'\n                       f'🗺 네이버지도: {naver_map("GS25 " + item["name"])}\\n'\n                       '※ 제3자 API 기준이며, 방문 전 매장에 실제 재고를 확인하세요.')\n                try:\n                    telegram(msg)\n                except (OSError, ValueError, RuntimeError) as exc:\n                    print(f'ALERT_FAILED region={rid} store={sid} error={type(exc).__name__}', flush=True)\n                    # Avoid advancing this store's baseline if the alert was not sent.\n                    if former is None:\n                        seen.pop(sid, None)\n                    else:\n                        seen[sid] = former\n                    continue\n                alerts += 1\n                print(f'ALERT_SENT region={rid} store={sid} old={prev_q} new={q}', flush=True)\n        # Keep prior observations for stores absent from this scan, but never infer zero.\n        prior_stores = prior.get('stores', prior.get('positive', {})) if prior else {}\n        merged = dict(prior_stores)\n        merged.update(seen)\n        new_state['regions'][rid] = {'stores': merged, 'checked_at_utc': new_state['checked_at_utc']}\n'''
if "conflicts = set()" not in s:
    s=s[:start]+new+s[end:]
else:
    print('ALREADY_PATCHED gs-alert')
ast.parse(s);p.write_text(s,encoding='utf-8');print('PATCHED',p)
print('STOCK_CHANGE_ALERT_PATCH_COMPLETE')
