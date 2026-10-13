"""Read-only, standard-library-only quality audit of the Asan CU registry."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

BARCODE = '8800286275732'

def normalized_address(value):
    value = str(value or '').strip().lower()
    value = re.sub(r'^(?:충남|충청남도)\s+', '', value)
    return re.sub(r'\s+', '', value)

def audit(data):
    stores = data.get('stores', [])
    if not isinstance(stores, list):
        raise ValueError('stores must be a list')
    ids = [str(s.get('registry_id', '')).strip() for s in stores]
    codes = [str(s.get('cu_store_code') or '').strip() for s in stores]
    by_address = defaultdict(list)
    coords = []
    missing = []
    invalid = []
    for s in stores:
        ident = s.get('registry_id')
        key = normalized_address(s.get('address'))
        if key:
            by_address[key].append(ident)
        lat, lon = s.get('latitude'), s.get('longitude')
        if lat in ('', None) and lon in ('', None):
            missing.append(ident)
        elif lat in ('', None) or lon in ('', None):
            invalid.append(ident)
        else:
            try:
                x, y = float(lat), float(lon)
                if not (-90 <= x <= 90 and -180 <= y <= 180):
                    raise ValueError('out of range')
                coords.append(ident)
            except (ValueError, TypeError):
                invalid.append(ident)
    duplicates = {k: v for k, v in by_address.items() if len(v) > 1}
    unknown_area = [s.get('registry_id') for s in stores if not str(s.get('area') or '').strip() or s.get('area') == '주소 미확인']
    return {
        'total': len(stores), 'unique_ids': len(set(ids)),
        'duplicate_ids': sorted(k for k, v in Counter(ids).items() if v > 1),
        'coded': sum(bool(c) for c in codes),
        'uncoded': sum(not c for c in codes),
        'duplicate_codes': sorted(k for k, v in Counter(c for c in codes if c).items() if v > 1),
        'coordinates_present': len(coords), 'coordinates_missing': len(missing),
        'coordinates_invalid': invalid,
        'duplicate_addresses': duplicates,
        'unknown_area': len(unknown_area),
        'unknown_area_ids': unknown_area,
        'barcode_valid': data.get('product_barcode') == BARCODE and all(s.get('product_barcode') == BARCODE for s in stores),
        'area_counts': dict(sorted(Counter(str(s.get('area') or '(공란)') for s in stores).items())),
    }

def baseline_ok(report):
    return (report['total'] == 123 and report['unique_ids'] == 123
            and not report['duplicate_ids'] and report['coded'] == 34
            and report['uncoded'] == 89 and not report['duplicate_codes']
            and report['coordinates_present'] == 3
            and report['coordinates_missing'] == 120
            and not report['coordinates_invalid']
            and len(report['duplicate_addresses']) == 2
            and report['unknown_area'] == 23 and report['barcode_valid'])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registry', type=Path)
    args = parser.parse_args()
    report = audit(json.loads(args.registry.read_text(encoding='utf-8')))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if baseline_ok(report) else 1)

if __name__ == '__main__':
    main()
