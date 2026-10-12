"""Read-only validation of GS25 Asan discovery candidates; never changes stock state."""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'asan_gs25_candidates.csv'
OUT = ROOT / 'asan_gs25_validation.csv'
SUMMARY = ROOT / 'asan_gs25_validation_summary.json'

# Only explicit geographic evidence can establish location.
def classify(address):
    address = ' '.join(str(address or '').split())
    if not address:
        return 'needs_address', 'API did not supply an address'
    if re.search(r'(?:충청남도|충남)\s+아산시\b|^아산시\b', address):
        return 'asan_address', 'Explicit Asan-si address; independently confirm store is active'
    if re.search(r'(?:특별시|광역시|특별자치시|특별자치도|도)\s+[^\s]+(?:시|군|구)\b|^[^\s]+(?:시|군|구)\b', address):
        return 'outside_or_ambiguous', 'Address is not explicitly Asan-si; review before exclusion'
    return 'needs_address', 'Address is insufficient for reliable municipality verification'


def main():
    if not INPUT.exists():
        raise SystemExit('Missing asan_gs25_candidates.csv; run asan_store_discovery.py first')
    with INPUT.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    known = set()
    state_path = ROOT / 'gs25_independent/gs25_stock_state.json'
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        known = set(state.get('regions', {}).get('asan', {}).get('stores', {}))
    results = []
    for item in rows:
        name = item.get('store_name', '')
        code = item.get('store_code', '')
        address = item.get('address', '')
        status, reason = classify(address)
        if code in known:
            status = 'already_known'
            reason = 'Already present in Asan state; location not independently reverified'
        elif status == 'needs_address' and re.search(r'아산|둔포|탕정|배방|모종|권곡|음봉|신창|도고|온양', name):
            reason += '; store name suggests Asan but is not proof'
        results.append({
            'store_code': code, 'store_name': name, 'address': address,
            'already_known_asan': 'yes' if code in known else 'no',
            'matched_keywords': item.get('matched_keywords', ''),
            'quantity_at_query': item.get('quantity_at_query', ''),
            'validation_status': status, 'reason': reason,
            'manual_verified_address': '', 'manual_verified_active': '',
        })
    fields = list(results[0]) if results else [
        'store_code','store_name','address','already_known_asan','matched_keywords',
        'quantity_at_query','validation_status','reason','manual_verified_address','manual_verified_active']
    with OUT.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    counts = {s: sum(r['validation_status'] == s for r in results) for s in
              ('already_known','asan_address','outside_or_ambiguous','needs_address')}
    SUMMARY.write_text(json.dumps({
        'total_candidates': len(results), 'counts': counts,
        'auto_imported': 0,
        'warning': 'Name/keyword and inventory quantities are not proof of location. No state modified.'
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('VALIDATION_COMPLETE', json.dumps(counts, ensure_ascii=False), flush=True)
    print('AUTO_IMPORTED=0', flush=True)


if __name__ == '__main__':
    main()
