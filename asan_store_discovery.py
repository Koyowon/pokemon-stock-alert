"""Read-only GS25 Asan discovery: compare expanded API keyword results to saved store codes."""
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'gs25_independent'))
from gs25_auto_monitor import api_query, safe, quantity

TERMS = ['아산', 'GS25아산', '배방', '탕정', '온양', '둔포', '음봉', '신창', '도고', '영인', '염치', '선장', '송악', '인주', '모종', '권곡', '용화', '온천']


def main():
    config = json.loads((ROOT / 'gs25_independent/config.json').read_text(encoding='utf-8'))
    code = config['item_code']
    previous = json.loads((ROOT / 'gs25_independent/gs25_stock_state.json').read_text(encoding='utf-8'))
    known = previous.get('regions', {}).get('asan', {}).get('stores', {})
    found = {}
    errors = []
    for term in TERMS:
        try:
            rows = api_query(code, term)
            if len(rows) >= 100:
                errors.append(f'{term}: query reached limit 100; incomplete')
            for row in rows:
                if not isinstance(row, dict):
                    continue
                sid = safe(row.get('storeCode', ''))
                name = safe(row.get('storeName') or row.get('name') or '')
                if not sid or not name:
                    continue
                # Name-only geography cannot conclusively establish Asan; mark for verification.
                entry = found.setdefault(sid, {'store_code': sid, 'store_name': name, 'stock': quantity(row), 'matched_terms': set()})
                entry['matched_terms'].add(term)
            print(f'QUERY_OK term={term} returned={len(rows)}', flush=True)
        except Exception as exc:
            errors.append(f'{term}: {type(exc).__name__}')
            print(f'QUERY_ERROR term={term} error={type(exc).__name__}', flush=True)
        time.sleep(0.2)
    with (ROOT / 'asan_gs25_candidates.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['store_code', 'store_name', 'quantity_at_query', 'already_known_asan', 'matched_keywords', 'verification'])
        for sid, item in sorted(found.items()):
            writer.writerow([sid, item['store_name'], item['stock'], 'yes' if sid in known else 'no', '; '.join(sorted(item['matched_terms'])), 'verify Asan address and store identity before importing'])
    with (ROOT / 'asan_gs25_discovery_summary.json').open('w', encoding='utf-8') as f:
        json.dump({'existing_asan_codes': len(known), 'candidate_codes': len(found), 'not_in_existing_asan': sum(sid not in known for sid in found), 'errors_or_caps': errors, 'note': 'Candidate results may include other municipalities. No stock state or alerts changed.'}, f, ensure_ascii=False, indent=2)
    print(f'FINISHED known={len(known)} candidates={len(found)} unverified_new={sum(sid not in known for sid in found)} errors={len(errors)}', flush=True)

if __name__ == '__main__':
    main()
