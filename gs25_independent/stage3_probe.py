#!/usr/bin/env python3
"""Read-only manual GS25 public REST response-shape probe.

No credentials, state changes, alerts, or stock claims. Logs only bounded,
allowlisted metadata; never logs raw responses, store/customer details, or URLs.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/actions/query'
TARGET = '8800286275732'  # Assumed barcode, NOT verified for GS25.
TIMEOUT = 15
MAX_BODY = 131072


def shape(value):
    """Return only structural type/count information, not field names or values."""
    if isinstance(value, dict):
        return f'object fields={min(len(value), 999)}'
    if isinstance(value, list):
        return f'array entries={min(len(value), 999)}'
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, (int, float)):
        return 'number'
    if isinstance(value, str):
        return 'string'
    return 'other'


def probe(label, action, **params):
    query = urllib.parse.urlencode({'action': action, 'format': 'json', **params})
    req = urllib.request.Request(BASE + '?' + query, headers={
        'Accept': 'application/json',
        'User-Agent': 'gs25-independent-manual-json-probe/1.1',
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            status = response.status
            content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
            raw = response.read(MAX_BODY + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get('Content-Type', '').split(';')[0].strip().lower()
        raw = exc.read(MAX_BODY + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f'{label}: NETWORK_ERROR kind={type(exc).__name__}; STOCK_UNKNOWN')
        return 'NETWORK_ERROR'

    if status == 401:
        result = 'AUTH_REQUIRED_401'
    elif status == 403:
        result = 'ACCESS_DENIED_403'
    elif status == 429:
        result = 'RATE_LIMITED_429'
    elif status == 404:
        result = 'ENDPOINT_NOT_FOUND_404'
    elif status >= 500:
        result = 'SERVICE_ERROR'
    elif status != 200:
        result = 'HTTP_UNEXPECTED'
    elif len(raw) > MAX_BODY:
        result = 'BODY_TOO_LARGE'
    elif not raw.strip():
        result = 'EMPTY_RESPONSE'
    else:
        try:
            parsed = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            result = 'NON_JSON_RESPONSE'
        else:
            if isinstance(parsed, dict) and (parsed.get('isError') is True or bool(parsed.get('error'))):
                result = 'API_ERROR_IN_200'
            else:
                result = 'JSON_SCHEMA_REVIEW_REQUIRED'
            print(f'{label}: HTTP_{status} {result}; content_type={content_type or "unspecified"}; root={shape(parsed)}; STOCK_UNKNOWN')
            return result

    print(f'{label}: HTTP_{status} {result}; content_type={content_type or "unspecified"}; STOCK_UNKNOWN')
    return result


def main():
    print('GS25_STAGE3_JSON_PROBE; READ_ONLY; NO_CREDENTIALS; NO_STATE_WRITES; NO_ALERTS')
    print('TARGET_ITEM_CODE_ASSUMED=' + TARGET)
    results = [
        probe('CONTROL_PRODUCT_SEARCH', 'gs25SearchProducts', keyword='코카콜라캔350ML', limit=3),
        probe('TARGET_PRODUCT_SEARCH', 'gs25SearchProducts', keyword='포켓몬', limit=3),
        probe('TARGET_INVENTORY_BY_CODE', 'gs25CheckInventory', itemCode=TARGET, storeKeyword='남원', storeLimit=3),
    ]
    print('GS25_STAGE3_RESULTS=' + ','.join(results))
    print('GS25_STOCK_NOT_VERIFIED; ZERO_STOCK_NOT_INFERRED')
    return 0  # Manual diagnostics report external errors as findings.


if __name__ == '__main__':
    sys.exit(main())
