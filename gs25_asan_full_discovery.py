#!/usr/bin/env python3
"""Read-only OSM GS25 candidate discovery. No production state writes.
Nominatim bounding box is only a discovery window, NOT city-boundary proof.
"""
import csv, json, time, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'gs25_asan_full_discovery.csv'
SUMMARY=ROOT/'gs25_asan_full_discovery_summary.json'
HEAD={'User-Agent':'pokemon-stock-alert/1.0 (read-only geographic store research; contact via GitHub repository)'}
SERVERS=['https://overpass.private.coffee/api/interpreter','https://overpass.kumi.systems/api/interpreter','https://overpass-api.de/api/interpreter']

def get_json(url, data=None, timeout=35):
    req=urllib.request.Request(url,data=data,headers=HEAD)
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)

def bounds():
    url='https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':'아산시, 충청남도, 대한민국','format':'json','limit':5,'addressdetails':1})
    items=get_json(url)
    matches=[x for x in items if '아산' in (x.get('display_name') or '') and x.get('boundingbox')]
    if not matches:raise RuntimeError('ASAN_BOUNDARY_NOT_FOUND: Nominatim returned no matching bounding box')
    b=matches[0]['boundingbox']
    return tuple(map(float,(b[0],b[2],b[1],b[3]))),matches[0]['display_name']

def query(b):
    south,west,north,east=b
    bbox=f'({south},{west},{north},{east})'
    # Spatially limited POI query avoids expensive name-based nationwide area scans.
    return f'''[out:json][timeout:35];(node["shop"="convenience"]["name"~"GS25|지에스25",i]{bbox};way["shop"="convenience"]["name"~"GS25|지에스25",i]{bbox};node["brand"~"GS25|지에스25",i]{bbox};way["brand"~"GS25|지에스25",i]{bbox};);out center tags;'''

def main():
    failures=[]
    try:
        bbox,place=bounds()
        print('GEOCODE_OK '+place,flush=True)
    except Exception as exc:
        raise SystemExit('GEOCODE_FAILED '+str(exc))
    q=query(bbox)
    data=None;endpoint=None
    for host in SERVERS:
        try:
            data=get_json(host,data=urllib.parse.urlencode({'data':q}).encode(),timeout=50)
            if 'elements' not in data:raise ValueError('no elements field')
            endpoint=host;break
        except Exception as exc:
            failures.append(f'{host}: {type(exc).__name__}: {exc}')
            print('SOURCE_FAILED '+failures[-1],flush=True)
            time.sleep(1)
    if data is None:raise SystemExit('OVERPASS_UNAVAILABLE: '+' | '.join(failures))
    rows=[];seen=set()
    for e in data['elements']:
        t=e.get('tags') or {};key=(e.get('type'),e.get('id'))
        if key in seen:continue
        seen.add(key)
        name=t.get('name','');brand=t.get('brand','')
        if not any(s in (name+' '+brand).upper() for s in ('GS25','지에스25')):continue
        center=e.get('center',e)
        addr=' '.join(filter(None,[t.get('addr:province'),t.get('addr:city'),t.get('addr:street'),t.get('addr:housenumber')]))
        rows.append({'osm_type':e.get('type',''),'osm_id':e.get('id',''),'store_name':name,'address':addr,'latitude':center.get('lat',''),'longitude':center.get('lon',''),'source_url':f"https://www.openstreetmap.org/{e.get('type')}/{e.get('id')}",'api_store_code':'','code_address_verified':'no','approval':'pending','boundary_verified':'no'})
    rows.sort(key=lambda r:(r['store_name'],str(r['osm_id'])))
    fields=['osm_type','osm_id','store_name','address','latitude','longitude','source_url','api_store_code','code_address_verified','approval','boundary_verified']
    with OUT.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    summary={'source':'OSM Overpass + Nominatim bounding box','endpoint':endpoint,'city':'아산시','stores_found':len(rows),'with_address':sum(bool(r['address']) for r in rows),'with_coordinates':sum(r['latitude']!='' and r['longitude']!='' for r in rows),'api_codes_verified':0,'boundary_verified':False,'completeness':'NOT GUARANTEED; bounding box may include neighboring municipalities; all results pending','production_modified':False,'bbox':bbox}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"FULL_DISCOVERY source=OSM_BBOX city=아산시 stores={len(rows)} with_address={summary['with_address']} with_coordinates={summary['with_coordinates']} verified_codes=0",flush=True)
    print('READ_ONLY: no monitoring code, approval CSV or stock state modified',flush=True)
    if not rows:raise SystemExit('NO_RESULTS: no OSM GS25 candidates; do not treat as no GS25 stores')

if __name__=='__main__':main()
