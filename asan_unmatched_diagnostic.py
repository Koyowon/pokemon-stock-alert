"""Read-only Asan API-vs-registry audit. No fuzzy matches or persistence."""
from collections import defaultdict
from cu_asan_registry import load_registry, normalize_name, normalize_address


def audit_unmatched(observed_by_code, candidates, *, stores=None, conflicts=()):
    stores = load_registry() if stores is None else stores
    if len(stores) != 119 or len(candidates) != 119:
        raise ValueError('Expected 119 registry entries and classified candidates')
    registry_ids = {s['registry_id'] for s in stores}
    candidate_ids = [r['registry_id'] for r in candidates]
    if len(set(candidate_ids)) != 119 or set(candidate_ids) != registry_ids:
        raise ValueError('Registry and candidate identities differ')
    by_id = {r['registry_id']: r for r in candidates}
    used_codes = {str(r.get('observed_store_code') or '').strip() for r in candidates if r.get('observed_store_code')}
    by_name = defaultdict(list)
    by_address = defaultdict(list)
    for store in stores:
        by_name[normalize_name(store.get('name'))].append(store['registry_id'])
        by_address[normalize_address(store.get('address'))].append(store['registry_id'])
    unmatched = []
    for code, item in sorted(observed_by_code.items(), key=lambda x: str(x[0])):
        code = str(code).strip()
        if not code or code in used_codes:
            continue
        name = str(item.get('name') or '')
        address = str(item.get('address') or '')
        name_ids = by_name.get(normalize_name(name), []) if name else []
        address_ids = by_address.get(normalize_address(address), []) if address else []
        # Hints are manual review only; NEVER modify classifier.
        unmatched.append({'code': code, 'name': name, 'address': address,
                          'stock': item.get('stock'),
                          'name_only_candidate_ids': sorted(name_ids),
                          'address_only_candidate_ids': sorted(address_ids),
                          'diagnostic_only': True})
    by_area = defaultdict(lambda: {'total': 0, 'observed': 0, 'not_observed': 0, 'not_queried': 0, 'other': 0})
    for store in stores:
        area = (store.get('area') or '').strip()
        if area in ('', '주소 미확인'):
            area = '미분류'
        entry = by_area[area]
        entry['total'] += 1
        status = by_id[store['registry_id']]['status']
        if status in ('IN_STOCK', 'ZERO_STOCK', 'NO_VALID_STOCK_VALUE'):
            entry['observed'] += 1
        elif status == 'NOT_OBSERVED':
            entry['not_observed'] += 1
        elif status == 'NOT_QUERIED':
            entry['not_queried'] += 1
        else:
            entry['other'] += 1
    priority = sorted(({'area': area, **counts} for area, counts in by_area.items()),
                      key=lambda x: (-x['not_observed'], x['area']))
    return {'unmatched_api_store_count': len(unmatched),
            'unmatched_api_stores': unmatched,
            'area_priorities': priority,
            'matched_registry_count': len(used_codes),
            'conflicting_codes': sorted(str(x) for x in conflicts),
            'matching_policy': 'EXACT_UNIQUE_NAME_AND_ADDRESS_OR_RESERVED_OFFICIAL_CODE_ONLY'}
