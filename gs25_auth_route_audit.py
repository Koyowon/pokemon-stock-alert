#!/usr/bin/env python3
"""GS25 phase-2 read-only audit. No credentials, cookies, stock calls or file writes."""
import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

BARCODE = '8800286275732'  # Assumption, NOT verified GS25 internal code
STORE = 'GS25 대천교차로점'  # Reported selling store; no unverified coordinates
BASE = 'https://b2c-bff.woodongs.com'
FILES = ['gs25_auth_diagnostic.py', 'gs25_readonly_rediagnostic.py']


def audit_source(path):
    p = Path(path)
    if not p.is_file():
        print(f'SOURCE={path} STATUS=NOT_FOUND')
        return
    s = p.read_text(encoding='utf-8')
    markers = {
        'PUBLIC_STOCK_ENDPOINT': '/api/bff/v2/store/stock' in s,
        'AUTHORIZATION_HEADER_LITERAL': 'Authorization' in s,
        'COOKIE_HEADER_LITERAL': 'Cookie' in s,
        'BARCODE_PRESENT': BARCODE in s,
    }
    print(f'SOURCE={path} STATUS=FOUND FLAGS={json.dumps(markers, ensure_ascii=False, separators=(",", ":"))}')
    print('NOTE=Literal source inspection only; absence of a marker does not prove authentication is unsupported.')


def health():
    req = urllib.request.Request(BASE + '/api/alive', headers={
        'Accept': 'application/json', 'User-Agent': 'GS25-phase2-readonly-audit/1.0'
    }, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=12) as res:
            print(f'HEALTH_HTTP={res.status} CONTENT_TYPE={res.headers.get("Content-Type", "").split(";")[0]}')
            # Intentionally do not read or print response bodies.
    except urllib.error.HTTPError as e:
        print(f'HEALTH_HTTP={e.code} RESULT=HTTP_ERROR')
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f'HEALTH_RESULT=NETWORK_ERROR TYPE={type(e).__name__}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-health', action='store_true', help='Fully offline source audit')
    args = parser.parse_args()
    print('GS25_PHASE2_AUDIT_START')
    print(f'TARGET_STORE={STORE} STORE_CODE=UNVERIFIED STORE_LOCATION=UNVERIFIED')
    print(f'TARGET_BARCODE={BARCODE} GS25_INTERNAL_ITEM_CODE=UNVERIFIED')
    print('LAST_VERIFIED_STOCK_API=HTTP_403_FOR_BOTH_PRODUCTS')
    print('AUTH_PATH=OFFICIAL_APP_SUPPORTED; EXTERNAL_AUTOMATION_AUTH=NOT_VERIFIED')
    for path in FILES:
        audit_source(path)
    if not args.skip_health:
        health()
    print('STOCK_REQUESTS=0 LOGIN_REQUESTS=0 SECRET_READS=0 FILE_WRITES=0')
    print('NEXT=Verify GS25 product code and an authorized external inventory interface before automated stock checks')
    print('GS25_PHASE2_AUDIT_FINISHED')


if __name__ == '__main__':
    main()
