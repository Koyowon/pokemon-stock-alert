"""Offline-only CU coordinate provenance gate; never geocodes or queries stock."""
import math

CITY_TOKENS = {'남원': '남원시', '아산': '아산시', '전주': '전주시'}


def validate_candidates(directory, records, existing_points):
    """Return (accepted, held). Never infer coordinates from an address."""
    accepted, held = [], []
    used_codes = set()
    existing = {(city, float(lat), float(lng)) for city, points in existing_points.items()
                for lat, lng in points}
    used_points = set(existing)
    for record in records:
        code = str(record.get('cu_store_code', ''))
        official = directory.get(code)
        city = record.get('city')
        reason = None
        if not official or code in used_codes:
            reason = 'UNKNOWN_OR_DUPLICATE_CODE'
        elif city not in CITY_TOKENS or CITY_TOKENS[city] not in official.get('address', ''):
            reason = 'CITY_MISMATCH'
        elif record.get('name') != official.get('name') or record.get('address') != official.get('address'):
            reason = 'IDENTITY_MISMATCH'
        elif not record.get('source_url') or not record.get('verified_at'):
            reason = 'MISSING_PROVENANCE'
        lat, lng = record.get('lat'), record.get('lng')
        if reason is None and (type(lat) not in (int, float) or type(lng) not in (int, float)
                               or not math.isfinite(lat) or not math.isfinite(lng)
                               or not (33 <= lat <= 39 and 124 <= lng <= 132)):
            reason = 'INVALID_COORDINATES'
        if reason is None and (city, float(lat), float(lng)) in used_points:
            reason = 'DUPLICATE_PROBE'
        if reason:
            held.append({'cu_store_code': code, 'reason': reason})
        else:
            used_codes.add(code)
            used_points.add((city, float(lat), float(lng)))
            accepted.append({'cu_store_code': code, 'city': city, 'lat': lat, 'lng': lng,
                             'source_url': record['source_url'], 'verified_at': record['verified_at']})
    return accepted, held
