"""Offline CU coordinate provenance gate. Never accesses network."""
import math
from datetime import datetime
from urllib.parse import urlsplit

CITY_TOKENS = {'남원': '남원시', '아산': '아산시', '전주': '전주시'}

def valid_source(url):
    if not isinstance(url, str): return False
    try:
        u = urlsplit(url)
        host = (u.hostname or '').lower()
        return (u.scheme == 'https' and bool(host) and not u.username and not u.password
                and u.port in (None, 443) and host not in ('localhost', 'example.org', 'example.com')
                and not host.endswith(('.localhost', '.local', '.test', '.invalid')))
    except ValueError:
        return False

def valid_time(value):
    if not isinstance(value, str): return False
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return d.tzinfo is not None and d.utcoffset() is not None
    except ValueError:
        return False

def valid_evidence(row):
    """Evidence is a manually reviewed snapshot declaration, NOT a live URL check."""
    e = row.get('evidence')
    return (isinstance(e, dict) and e.get('reviewed') is True
            and all(e.get(k) == row.get(k) for k in
                    ('cu_store_code', 'name', 'address', 'lat', 'lng', 'source_url', 'verified_at'))
            and isinstance(e.get('snapshot_sha256'), str)
            and len(e['snapshot_sha256']) == 64
            and all(c in '0123456789abcdef' for c in e['snapshot_sha256']))

def validate_candidates(directory, records, existing_points):
    """Reject candidates without independently reviewed provenance; no geocoding."""
    accepted, held, used_codes = [], [], set()
    used_points = {(city, float(lat), float(lng)) for city, points in existing_points.items()
                   for lat, lng in points}
    for row in records:
        code = str(row.get('cu_store_code', ''))
        official = directory.get(code)
        city = row.get('city')
        lat, lng = row.get('lat'), row.get('lng')
        reason = None
        if not official or code in used_codes:
            reason = 'UNKNOWN_OR_DUPLICATE_CODE'
        elif city not in CITY_TOKENS or CITY_TOKENS[city] not in official.get('address', ''):
            reason = 'CITY_MISMATCH'
        elif row.get('name') != official.get('name') or row.get('address') != official.get('address'):
            reason = 'IDENTITY_MISMATCH'
        elif not valid_source(row.get('source_url')) or not valid_time(row.get('verified_at')):
            reason = 'INVALID_PROVENANCE'
        elif not valid_evidence(row):
            reason = 'UNVERIFIED_SOURCE_EVIDENCE'
        elif (type(lat) not in (int, float) or type(lng) not in (int, float)
              or not math.isfinite(lat) or not math.isfinite(lng)
              or not (33 <= lat <= 39 and 124 <= lng <= 132)):
            reason = 'INVALID_COORDINATES'
        elif (city, float(lat), float(lng)) in used_points:
            reason = 'DUPLICATE_PROBE'
        if reason:
            held.append({'cu_store_code': code, 'reason': reason})
        else:
            used_codes.add(code)
            used_points.add((city, float(lat), float(lng)))
            accepted.append({k: row[k] for k in
                             ('cu_store_code', 'city', 'lat', 'lng', 'source_url', 'verified_at')})
    return accepted, held
