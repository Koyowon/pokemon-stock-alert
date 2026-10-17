"""Reviewable Seven-Eleven integration probe. Default mode performs no HTTP.

Historical third-party paths are candidates, not a verified provider contract.
No stock state, Telegram, credentials, or workflow dispatch is used here.
"""
import argparse
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page'
TIMEOUT = 10
MAX_BODY = 65536


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request, timeout):
    return urllib.request.build_opener(NoRedirect).open(request, timeout=timeout)


def request_plan():
    # Same paths/parameter names as the repository's archived diagnostics.
    # Namwon is the first bounded sample; this is not regional full coverage.
    return [
        {'name': 'product_contract', 'path': '/api/seveneleven/products',
         'params': {'query': '포켓몬확장팩(30주년)', 'size': 5, 'format': 'html'}},
        {'name': 'store_contract', 'path': '/api/seveneleven/stores',
         'params': {'keyword': '남원', 'limit': 5, 'format': 'html'}},
        {'name': 'inventory_contract', 'path': '/api/seveneleven/inventory',
         'params': {'keyword': '포켓몬확장팩(30주년)', 'storeKeyword': '남원',
                    'storeLimit': 5, 'format': 'html'}},
    ]


def probe(plan=None):
    plan = request_plan() if plan is None else plan
    if plan != request_plan():
        raise ValueError('Only the reviewed three-request plan is allowed')
    results = []
    for step in plan:
        url = BASE + step['path'] + '?' + urllib.parse.urlencode(step['params'])
        req = urllib.request.Request(url, headers={
            'User-Agent': 'PokemonStockIntegrationReadiness/1.0',
            'Accept': 'text/html, application/json',
        })
        status, raw, error = None, b'', None
        try:
            with open_request(req, timeout=TIMEOUT) as response:
                status = response.status
                raw = response.read(MAX_BODY + 1)
        except urllib.error.HTTPError as exc:
            status, error = exc.code, 'HTTP_ERROR'
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            error = type(exc).__name__
        if len(raw) > MAX_BODY:
            error, raw = 'BODY_TOO_LARGE', b''
        if status != 200 and error is None:
            error = 'HTTP_ERROR'
        body = raw.decode('utf-8', 'replace')
        fields = None
        try:
            value = json.loads(body)
            if isinstance(value, dict):
                fields = sorted(value)
        except ValueError:
            pass
        results.append({
            'step': step['name'], 'http_status': status, 'error': error,
            'top_level_fields': fields, 'body_preview': body[:4000],
            'inventory_status': 'UNVERIFIED',
        })
        # A failed route is not zero stock. No alternate route or retry loop.
        if error is not None:
            break
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true',
                        help='Explicitly perform the reviewed HTTP diagnostic; otherwise print plan only')
    args = parser.parse_args(argv)
    output = {'mode': 'LIVE_DIAGNOSTIC' if args.live else 'OFFLINE_PLAN',
              'maximum_requests': 3, 'retries': 0,
              'inventory_activation': False, 'telegram_calls': 0,
              'state_writes': 0,
              'requests': probe() if args.live else request_plan()}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
