"""Bounded Seven-Eleven coverage/health watch; never sends notifications.

Default CLI is offline. Only --live requests the observed third-party API.
"""
import argparse
import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from seveneleven_contract import classify_snapshot, UnverifiedSnapshot
from seveneleven_readiness import NoRedirect

ROOT = Path(__file__).resolve().parent
CITIES = {'namwon': '남원시', 'asan': '아산시', 'jeonju': '전주시'}
MAX_CALLS = 6
MAX_SECONDS = 180
STALE_SECONDS = 900
REQUEST_TIMEOUT = 45


class RelayFailure(Exception):
    def __init__(self, reason, terminal=False):
        super().__init__(reason)
        self.terminal = terminal


def fetch_inventory(keyword):
    params = {'keyword': '포켓몬확장팩(30주년)', 'storeKeyword': keyword,
              'storeLimit': 200 if keyword in CITIES.values() else 5}
    url = 'https://mcp.aka.page/api/seveneleven/inventory?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={
        'Accept': 'application/json', 'User-Agent': 'PokemonStockCoverageWatch/1.0'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read(1_000_001)
    except urllib.error.HTTPError as exc:
        raise RelayFailure('HTTP_' + str(exc.code), exc.code in (400, 401, 403, 404, 429)) from None
    except (TimeoutError, urllib.error.URLError) as exc:
        is_timeout = isinstance(exc, TimeoutError) or isinstance(getattr(exc, 'reason', None), TimeoutError)
        raise RelayFailure('READ_TIMEOUT' if is_timeout else 'NETWORK_ERROR') from None
    except OSError:
        raise RelayFailure('NETWORK_ERROR') from None
    if len(raw) > 1_000_000:
        raise RelayFailure('OVERSIZED_RESPONSE', True)
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise RelayFailure('INVALID_JSON', True) from None


def run_watch(directories, previous, fetch, now, monotonic=time.monotonic, pause=time.sleep):
    """Return state only; I/O injected so regression tests cannot call services."""
    if previous and (previous.get('version') != 1 or previous.get('product') != '8800286275732'):
        raise ValueError('Unsupported watch state')
    state = json.loads(json.dumps(previous or {
        'version': 1, 'product': '8800286275732', 'cursor': 0, 'stores': {}}))
    registered = {}
    for region, directory in directories.items():
        for row in directory['data']['stores']:
            code = row['storeCode']
            if code in registered:
                raise ValueError('Duplicate registry code')
            registered[code] = (region, row)
            record = state['stores'].setdefault(code, {})
            if record and (record.get('name') != row['storeName'] or record.get('address') != row['address']):
                raise ValueError('Registry identity changed')
            record.update(region=region, name=row['storeName'], address=row['address'])
            record.setdefault('status', 'UNKNOWN')
            record.setdefault('quantity', None)
            record.setdefault('reason', 'NOT_YET_CHECKED')
            if now - record.get('checked_at', 0) > STALE_SECONDS:
                record.update(status='UNKNOWN', quantity=None, reason='STALE')
    if set(state['stores']) - set(registered):
        raise ValueError('Registry removal requires review')
    calls = []; failures = 0; start = monotonic(); halted = False

    def mark(code, quantity, reason):
        record = state['stores'][code]
        record.update(status='OK' if quantity is not None else 'UNKNOWN',
                      quantity=quantity, reason=reason, checked_at=now)
        if quantity is not None:
            record.update(last_known_quantity=quantity, last_success_at=now)
            record.update(direct_failures=0, next_direct_at=now + 900)

    def query(region, keyword, target=None):
        nonlocal failures, halted
        if halted or len(calls) >= MAX_CALLS or monotonic() - start >= MAX_SECONDS - REQUEST_TIMEOUT - 5:
            return False
        if calls:
            pause(2)
        codes = [target] if target else [c for c, (r, _) in registered.items() if r == region]
        reason = None; detail = None
        request_started = monotonic()
        try:
            payload = fetch(keyword)
            classified = classify_snapshot(directories[region], payload, region, allow_unavailable=True)
            observed = {r['storeCode'] for r in payload['data']['inventory']['stores']}
            for code in codes:
                result = classified[code]
                mark(code, result['quantity'], 'OBSERVED' if result['quantity'] is not None else
                     ('NO_QUANTITY' if code in observed else 'MISSING_IN_RESPONSE'))
            failures = 0
        except RelayFailure as exc:
            reason = str(exc); failures += 1; halted = exc.terminal
        except UnverifiedSnapshot as exc:
            reason = 'UNVERIFIED_RESPONSE'; detail = str(exc); failures += 1
        except (KeyError, TypeError, ValueError):
            reason = 'UNVERIFIED_RESPONSE'; detail = 'INVALID_SCHEMA'; failures += 1
        if reason:
            for code in codes:
                mark(code, None, reason)
        calls.append({'region': region, 'keyword': keyword, 'target': target,
                      'result': reason or 'VALIDATED', 'validation_reason': detail,
                      'elapsed_seconds': round(monotonic() - request_started, 2), 'at': now})
        if target:
            record = state['stores'][target]
            record['last_direct_at'] = now
            if record['status'] != 'OK':
                n = min(record.get('direct_failures', 0) + 1, 6)
                record.update(direct_failures=n, next_direct_at=now + min(900 * 2**(n-1), 21600))
        if failures >= 2:
            halted = True
        return True

    regions = list(CITIES)
    cursor = state.get('cursor', 0) % len(regions)
    for region in regions[cursor:] + regions[:cursor]:
        if not query(region, CITIES[region]):
            break
        candidates = [c for c, r in state['stores'].items()
                      if r['region'] == region and r['status'] == 'UNKNOWN'
                      and r.get('next_direct_at', 0) <= now]
        candidates.sort(key=lambda c: (state['stores'][c].get('last_direct_at', 0), c))
        if candidates:
            code = candidates[0]
            query(region, registered[code][1]['storeName'], code)
    state.update(cursor=(cursor + 1) % len(regions), updated_at=now, calls=calls,
                 halted=halted, summary={})
    for region in regions:
        rows = [r for r in state['stores'].values() if r['region'] == region]
        state['summary'][region] = {
            'total': len(rows), 'known': sum(r['status'] == 'OK' for r in rows),
            'unknown': sum(r['status'] != 'OK' for r in rows)}
    return state


def save_atomic(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    directories = json.loads((ROOT / 'data/seveneleven_watch_directory.json').read_text())
    if not args.live:
        print(json.dumps({'offline': True, 'max_calls': MAX_CALLS,
                          'stores': {k: len(v['data']['stores']) for k,v in directories.items()}}))
        return
    path = ROOT / 'seveneleven_watch_state.json'
    previous = json.loads(path.read_text()) if path.exists() else None
    state = run_watch(directories, previous, fetch_inventory, int(time.time()))
    save_atomic(path, state)
    print(json.dumps(state['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()

