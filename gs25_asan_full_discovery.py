#!/usr/bin/env python3
"""Read-only OpenStreetMap discovery; no stock-state or approval modifications."""
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'gs25_asan_full_discovery.csv'
SUMMARY = ROOT / 'gs25_asan_full_discovery_summary.json'
ENDPOINTS = [
    'https://overpass.private.coffee/api/interpreter',
    'https://overpass-api.de/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
]
# Limit to Asan administrative boundary. Do not replace this with a city-sized
# bounding box: that would include neighboring cities and invalidate coverage.
QUERY = '''[out:json][timeout:60];
area["name"="아산시"]["boundary"="administrative"]["admin_level"="4"]->.asan;
(
 nwr(area.asan)["brand"~"GS25|지에스25",i];
 nwr(area.asan)["name"~"^(GS25|지에스25)",i];
);
out center tags;'''

def fetch():
    failures = []
    payload = urllib.parse.urlencode({'data': QUERY}).encode('utf-8')
    for endpoint in ENDPOINTS:
        for attempt in range(2):
            try:
                request = urllib.request.Request(endpoint, data=payload, headers={
                    'User-Agent': 'pokemon-stock-alert/1.1 (read-only geographic coverage audit)',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json',
                })
                with urllib.request.urlopen(request, timeout=90) as response:
                    data = json.load(response)
                if not isinstance(data.get('elements'), list):
                    raise ValueError('Response missing elements array')
                return data, endpoint
            except Exception as exc:
                failures.append(f'{endpoint} attempt={attempt+1}: {type(exc).__name__}: {exc}')
                time.sleep(2 + attempt * 3)
    raise RuntimeError('OVERPASS_UNAVAILABLE: ' + ' | '.join(failures))

def main():
    data, endpoint = fetch()
    rows = []
    for item in data['elements']:
        tags = item.get('tags') or {}
        name = tags.get('name', '')
        brand = tags.get('brand', '')
        if not ('GS25' in name.upper() or '지에스25' in name or 'GS25' in brand.upper() or '지에스25' in brand):
            continue
        center = item.get('center') or item
        address = ' '.join(filter(None, [tags.get('addr:province', ''), tags.get('addr:city', ''), tags.get('addr:street', ''), tags.get('addr:housenumber', '')])).strip()
        rows.append({'osm_type': item.get('type',''), 'osm_id': item.get('id',''),
            'store_name': name, 'address': address, 'latitude': center.get('lat',''),
            'longitude': center.get('lon',''),
            'source_url': f"https://www.openstreetmap.org/{item.get('type')}/{item.get('id')}",
            'api_store_code': '', 'code_address_verified': 'no', 'approval': 'pending'})
    rows.sort(key=lambda r: (r['store_name'], str(r['osm_id'])))
    fields = ['osm_type','osm_id','store_name','address','latitude','longitude','source_url','api_store_code','code_address_verified','approval']
    with OUT.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {'source': 'OpenStreetMap Overpass', 'endpoint': endpoint,
        'city': '아산시', 'stores_found': len(rows),
        'with_address': sum(bool(r['address']) for r in rows),
        'with_coordinates': sum(r['latitude'] != '' and r['longitude'] != '' for r in rows),
        'api_codes_verified': 0, 'completeness': 'NOT GUARANTEED; OSM may omit stores',
        'production_modified': False}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"FULL_DISCOVERY source=OSM city=아산시 stores={len(rows)} with_address={summary['with_address']} with_coordinates={summary['with_coordinates']} verified_codes=0", flush=True)
    print('READ_ONLY: no monitoring code, approval CSV or stock state modified', flush=True)
    if not rows:
        raise SystemExit('NO_RESULTS: OSM may have no GS25 coverage; do not treat as zero real stores')

if __name__ == '__main__':
    main()
