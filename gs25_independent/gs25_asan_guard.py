"""Conservative GS25 Asan store-code guard. No network calls or state writes."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / 'gs25_asan_approval_review.csv'


def approved_codes():
    """Only explicit yes/verified rows may be added; never trust names alone."""
    if not REVIEW.exists():
        return set()
    with REVIEW.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    return {r['store_code'].strip() for r in rows
            if r.get('approval', '').strip().lower() == 'approved'
            and r.get('code_address_verified', '').strip().lower() == 'yes'}


def filter_asan_seen(seen, prior):
    """Preserve all existing Asan codes and allow explicitly verified additions."""
    old = prior.get('stores', prior.get('positive', {})) if isinstance(prior, dict) else {}
    allowed = set(old) | approved_codes()
    return {sid: item for sid, item in seen.items() if sid in allowed}
