#!/usr/bin/env python3
"""Manual, read-only Daiso MCP GS25 REST smoke test. No secrets or stock writes."""
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/actions/query'
TARGET = '8800286275732'  # assumed, not independently verified
TIMEOUT = 15


def request(label, action, **params):
    query = urllib.parse.urlencode({'action': action, 'format': 'html', **params})
    req = urllib.request.Request(BASE + '?' + query, headers={
        'Accept': 'text/html, application/json',
        'User-Agent': 'gs25-independent-manual-probe/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            status = response.status
            content_type = response.headers.get('Content-Type', '')
            body = response.read(65536).decode('utf-8', errors='replace')
    except urllib.error.HTTPError as error:
        status = error.code
        content_type = error.headers.get('Content-Type', '')
        body = error.read(8192).decode('utf-8', errors='replace')
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f'{label}: NETWORK_ERROR ({type(error).__name__}); STOCK_UNKNOWN')
        return 'NETWORK_ERROR'

    if status == 403:
        result = 'ACCESS_DENIED_403'
    elif status == 429:
        result = 'RATE_LIMITED_429'
    elif status in (401,):
        result = 'AUTH_REQUIRED_401'
    elif status >= 500:
        result = 'SERVICE_ERROR'
    elif status == 404:
        result = 'ENDPOINT_NOT_FOUND_404'
    elif status != 200:
        result = 'HTTP_UNEXPECTED'
    else:
        # Never convert absent or empty results to zero inventory.
        lowered = html.unescape(re.sub(r'<[^>]+>', ' ', body)).lower()
        if any(x in lowered for x in ('rate limit', 'quota exceeded', 'too many requests')):
            result = 'POSSIBLE_QUOTA_ERROR'
        elif any(x in lowered for x in ('unauthorized', 'forbidden', 'access denied')):
            result = 'POSSIBLE_ACCESS_ERROR'
        elif any(x in lowered for x in ('not found', '상품이 없습니다', '검색 결과가 없습니다', 'no results')):
            result = 'NO_PRODUCT_OR_RESULTS_UNVERIFIED'
        elif not body.strip():
            result = 'EMPTY_RESPONSE'
        elif 'json' in content_type.lower():
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict) and (parsed.get('isError') is True or parsed.get('error')):
                    result = 'API_ERROR_IN_200'
                else:
                    result = 'JSON_RESPONSE_REQUIRES_SCHEMA_REVIEW'
            except ValueError:
                result = 'INVALID_JSON'
        else:
            result = 'HTML_RESPONSE_REQUIRES_SCHEMA_REVIEW'
    print(f'{label}: HTTP_{status} {result}; STOCK_UNKNOWN; type={content_type.split(";")[0] or "unspecified"}; bytes={len(body.encode("utf-8"))}')
    return result


def main():
    print('GS25_STAGE3_MANUAL_PROBE; NO_CREDENTIALS; NO_STATE_WRITES; NO_ALERTS')
    print('TARGET_CODE_ASSUMED=' + TARGET)
    results = [
        request('CONTROL_PRODUCT_SEARCH', 'gs25SearchProducts', keyword='코카콜라캔350ML', limit=3),
        request('TARGET_PRODUCT_SEARCH', 'gs25SearchProducts', keyword='포켓몬', limit=3),
        request('TARGET_INVENTORY_BY_CODE', 'gs25CheckInventory', itemCode=TARGET, storeKeyword='남원', storeLimit=3),
    ]
    print('GS25_STAGE3_RESULTS=' + ','.join(results))
    print('GS25_STOCK_NOT_VERIFIED; ZERO_STOCK_NOT_INFERRED')
    # A diagnostic workflow should finish successfully even when external service denies access.
    return 0


if __name__ == '__main__':
    sys.exit(main())
