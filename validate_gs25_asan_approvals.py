#!/usr/bin/env python3
"""Read-only approval gate for GS25 Asan candidate codes. No network or state writes."""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANDIDATES = ROOT / 'asan_gs25_candidates.csv'
REVIEW = ROOT / 'gs25_independent' / 'gs25_asan_approval_review.csv'
STATE = ROOT / 'gs25_independent' / 'gs25_stock_state.json'


def load_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def check(candidates, review, existing):
    candidate_codes = {}
    for row in candidates:
        code = (row.get('store_code') or '').strip()
        name = (row.get('store_name') or '').strip()
        if code in candidate_codes and candidate_codes[code] != name:
            raise ValueError('Duplicate candidate code with conflicting names: ' + code)
        candidate_codes[code] = name
    errors = []
    approved = []
    seen = set()
    for row in review:
        code = (row.get('store_code') or '').strip()
        name = (row.get('store_name') or '').strip()
        approval = (row.get('approval') or '').strip().lower()
        verified = (row.get('code_address_verified') or '').strip().lower()
        address = (row.get('external_address') or '').strip()
        evidence = (row.get('verification_evidence_url') or '').strip()
        if not code or code in seen:
            errors.append(f'duplicate_or_empty_code:{code}')
            continue
        seen.add(code)
        if approval not in ('pending', 'rejected', 'approved'):
            errors.append(f'bad_approval:{code}')
        if approval != 'approved':
            continue
        if code not in candidate_codes or candidate_codes[code] != name:
            errors.append(f'code_name_not_in_discovery:{code}')
        if code in existing:
            errors.append(f'already_registered:{code}')
        if verified != 'yes':
            errors.append(f'code_address_not_verified:{code}')
        if not re.search(r'(?:아산시|Asan)', address, flags=re.I):
            errors.append(f'address_not_asan:{code}')
        if not evidence.startswith('https://'):
            errors.append(f'missing_https_code_address_evidence:{code}')
        approved.append(code)
    return errors, approved


def main():
    if not CANDIDATES.exists() or not REVIEW.exists() or not STATE.exists():
        raise SystemExit('MISSING_INPUT: expected discovery CSV, approval CSV, and GS25 stock state')
    state = json.loads(STATE.read_text(encoding='utf-8'))
    existing = set(state.get('regions', {}).get('asan', {}).get('stores', {}))
    errors, approved = check(load_csv(CANDIDATES), load_csv(REVIEW), existing)
    print(f'APPROVAL_AUDIT existing_asan={len(existing)} approved_new={len(approved)} errors={len(errors)}')
    for code in approved:
        print('APPROVED_CANDIDATE ' + code)
    for err in errors:
        print('ERROR ' + err)
    if errors:
        raise SystemExit(1)
    print('APPROVAL_AUDIT_OK: no state or monitoring code changed')


if __name__ == '__main__':
    main()
