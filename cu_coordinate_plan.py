"""Offline CU coordinate provenance gate. Never accesses network."""
import math
import hashlib
import re
import ipaddress
from datetime import timezone
from datetime import datetime
from urllib.parse import urlsplit

TRUSTED_HOSTS = frozenset({'cu.bgfretail.com', 'map.naver.com', 'm.map.naver.com', 'place.map.kakao.com'})
CITY_TOKENS = {'남원': '남원시', '아산': '아산시', '전주': '전주시'}

def valid_source(url):
    """Strict offline source URL syntax and allowlisted hostname check."""
    if not isinstance(url, str) or not url or url != url.strip():
        return False
    if any(ord(ch) < 33 or ord(ch) == 127 or ch == '\\' for ch in url):
        return False
    try:
        u = urlsplit(url)
        host = u.hostname
        if (u.scheme != 'https' or not host or u.username is not None
                or u.password is not None or u.port not in (None, 443)
                or u.fragment or host.endswith('.')):
            return False
        if host not in TRUSTED_HOSTS or not re.fullmatch(r'[a-z0-9.-]+', host):
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        return bool(u.path or u.query)
    except (ValueError, TypeError):
        return False

def valid_time(value):
    if not isinstance(value, str): return False
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return d.tzinfo is not None and d.utcoffset() is not None and d <= datetime.now(timezone.utc)
    except ValueError:
        return False

def valid_evidence(row):
    """Rehash archived UTF-8 source text and match extracted fields offline.

    A matching hash proves internal integrity, not external authenticity.
    """
    evidence = row.get('evidence')
    if not isinstance(evidence, dict) or evidence.get('reviewed') is not True:
        return False
    snapshot = evidence.get('source_snapshot')
    if not isinstance(snapshot, str) or not snapshot.strip() or len(snapshot) > 1000000:
        return False
    try:
        raw = snapshot.encode('utf-8')
    except UnicodeError:
        return False
    keys = ('cu_store_code', 'name', 'address', 'lat', 'lng', 'source_url', 'verified_at')
    if any(type(evidence.get(k)) is not type(row.get(k)) or evidence.get(k) != row.get(k) for k in keys):
        return False
    digest = evidence.get('snapshot_sha256')
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        return False
    if hashlib.sha256(raw).hexdigest() != digest:
        return False
    return all(str(row[k]) in snapshot for k in ('cu_store_code', 'name', 'address', 'lat', 'lng'))

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
