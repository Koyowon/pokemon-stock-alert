"""Offline preapproval gate; no external requests or operational writes."""
from collections import Counter
from datetime import date
from urllib.parse import urlparse
import re

BARCODE = '8800286275732'


def inspect(rows, registry, cu_codes, emart_codes):
    ids = {r['registry_id']: r for r in registry if not r.get('cu_store_code')}
    used = {'cu': set(map(str, cu_codes)), 'emart24': set(map(str, emart_codes))}
    counts = Counter((r.get('chain'), str(r.get('store_code') or '').strip()) for r in rows if r.get('store_code'))
    candidate_counts = Counter(r.get('registry_id') for r in rows if r.get('chain') == 'cu' and r.get('registry_id'))
    out = []
    for r in rows:
        chain, code = r.get('chain'), str(r.get('store_code') or '').strip()
        status = 'MANUAL_REVIEW_REQUIRED'
        if chain not in used:
            status = 'REJECT_CHAIN'
        elif not code:
            status = 'BLOCKED_NO_CODE'
        elif not re.fullmatch(r'\d+', code):
            status = 'REJECT_CODE_FORMAT'
        elif code in used[chain] or counts[(chain, code)] > 1:
            status = 'REJECT_DUPLICATE_CODE'
        elif chain == 'cu' and candidate_counts[r.get('registry_id')] > 1:
            status = 'REJECT_DUPLICATE_CANDIDATE'
        elif r.get('barcode') != BARCODE:
            status = 'REJECT_BARCODE'
        elif chain == 'cu' and r.get('registry_id') not in ids:
            status = 'REJECT_UNKNOWN_CANDIDATE'
        elif chain == 'cu' and (r.get('name') != ids[r['registry_id']].get('name') or r.get('address') != ids[r['registry_id']].get('address')):
            status = 'REVIEW_IDENTITY_MISMATCH'
        elif chain == 'emart24' and not str(r.get('address') or '').strip().startswith(('제주시 ', '제주특별자치도 제주시 ', '제주도 제주시 ')):
            status = 'REJECT_NOT_JEJU'
        elif not str(r.get('name') or '').strip() or not str(r.get('address') or '').strip():
            status = 'REJECT_MISSING_IDENTITY'
        else:
            url = urlparse(str(r.get('source_url') or ''))
            try:
                observed = date.fromisoformat(str(r.get('observed_at') or ''))
                valid_date = observed <= date.today()
            except ValueError:
                valid_date = False
            if url.scheme != 'https' or not url.hostname or url.username or url.password or not valid_date:
                status = 'REJECT_PROVENANCE'
        out.append({'chain': chain, 'registry_id': r.get('registry_id'), 'store_code': code, 'status': status, 'approved': False})
    return out
