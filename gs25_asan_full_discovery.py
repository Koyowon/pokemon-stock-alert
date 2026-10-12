#!/usr/bin/env python3
"""Read-only Asan GS25 geographic discovery via OpenStreetMap Overpass.
This is an independent inventory candidate source, NOT a completeness guarantee.
"""
import csv
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'gs25_asan_full_discovery.csv'
SUMMARY = ROOT / 'gs25_asan_full_discovery_summary.json'
ENDPOINTS = ['https://overpass.kumi.systems/api/interpreter', 'https://overpass-api.de/api/interpreter']
QUERY = '''[out:json][timeout:90];
area["name"="아산시"]["boundary"="administrative"]->.asan;
(
 nwr(area.asan)["brand"~"GS25|지에스25",i];
 nwr(area.asan)["brand:wikidata"="Q1234505"];
 nwr(area.asan)["name"~"^(GS25|지에스25)",i];
);
out center tags;'''

def fetch():
    body = urllib.parse.urlencode({'data': QUERY}).encode()
    failures = []
    for endpoint in ENDPOINTS:
        try:
            req = urllib.request.Request(endpoint, data=body, headers={'User-Agent': 'pokemon-stock-alert/1.0 (noncommercial store coverage audit)', 'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req, timeout=115) as resp:
                data = json.load(resp)
            return data, endpoint
        except Exception as exc:
            failures.append(f'{endpoint}: {type(exc).__name__}: {exc}')
            time.sleep(2)
    raise RuntimeError('Overpass request failed: ' + ' | '.join(failures))

def main():
    data, endpoint = fetch()
    elements = data.get('elements', [])
    rows = []
    for item in elements:
        tags = item.get('tags') or {}
        name = tags.get('name', '')
        brand = tags.get('brand', '')
        if not ('GS25' in name.upper() or '지에스25' in name or 'GS25' in brand.upper() or '지에스25' in brand):
            continue
        center = item.get('center', item)
        address = ' '.join(filter(None, [tags.get('addr:province',''), tags.get('addr:city',''), tags.get('addr:street',''), tags.get('addr:housenumber','')])).strip()
        rows.append({'osm_type':item.get('type',''), 'osm_id':item.get('id',''), 'store_name':name, 'address':address, 'latitude':center.get('lat',''), 'longitude':center.get('lon',''), 'source_url':f"https://www.openstreetmap.org/{item.get('type')}/{item.get('id')}", 'api_store_code':'', 'code_address_verified':'no', 'approval':'pending'})
    rows.sort(key=lambda x:(x['store_name'],str(x['osm_id'])))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields=['osm_type','osm_id','store_name','address','latitude','longitude','source_url','api_store_code','code_address_verified','approval']
    with OUT.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader();writer.writerows(rows)
    summary={'source':'OpenStreetMap Overpass', 'endpoint':endpoint, 'city':'아산시', 'stores_found':len(rows), 'with_address':sum(bool(r['address']) for r in rows), 'with_coordinates':sum(r['latitude'] != '' and r['longitude'] != '' for r in rows), 'api_codes_verified':0, 'completeness':'NOT GUARANTEED; OSM may omit stores', 'production_modified':False}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"FULL_DISCOVERY source=OSM city=아산시 stores={summary['stores_found']} with_address={summary['with_address']} with_coordinates={summary['with_coordinates']} verified_codes=0")
    print('READ_ONLY: no monitoring code, approval CSV or stock state modified')
    if not rows:
        raise SystemExit('NO_RESULTS: OSM query returned no GS25 stores; check Overpass response and area mapping')

if __name__=='__main__':
    import urllib.parse
    main()
