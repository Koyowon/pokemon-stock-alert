#!/usr/bin/env python3
"""Read-only geospatial review of OSM GS25 candidates using geoBoundaries ADM2.
Never auto-approves inventory store codes. Requires network access on GitHub Actions.
"""
import csv, io, json, os, sys, urllib.request
from pathlib import Path
from shapely.geometry import shape, Point

BASE=Path(__file__).resolve().parent
SOURCE=Path(os.environ.get('SOURCE_CSV', str(BASE/'gs25_asan_full_discovery.csv')))
OUT=Path(os.environ.get('OUTPUT_CSV',str(BASE/'gs25_asan_boundary_review.csv')))
META=Path(os.environ.get('OUTPUT_JSON',str(BASE/'gs25_asan_boundary_summary.json')))
API='https://www.geoboundaries.org/api/current/gbOpen/KOR/ADM2/'
def get_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'pokemon-stock-alert-boundary-review/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=70) as r:return json.load(r)
def main():
    with SOURCE.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if len(rows)!=26:print(f'NOTICE: input row count {len(rows)} (original 26)')
    meta=get_json(API)
    url=meta.get('simplifiedGeometryGeoJSON') or meta.get('gjDownloadURL')
    if not url:raise RuntimeError('geoBoundaries ADM2 response missing GeoJSON download URL')
    geo=get_json(url)
    features=geo.get('features',[])
    # Fail closed: only accept an unambiguous Asan polygon by administrative name.
    matched=[]
    for f in features:
        props=f.get('properties') or {}
        names=[str(v) for k,v in props.items() if k.lower() in ('shapeName'.lower(),'name','adm_nm','name_en','name_ko')]
        if any('아산' in n or 'asan' in n.lower() for n in names):matched.append(f)
    if len(matched)!=1:
        samples=[str(f.get('properties',{}))[:160] for f in features[:5]]
        raise RuntimeError(f'ASAN_BOUNDARY_UNRESOLVED: found {len(matched)} named polygons; sample={samples}')
    polygon=shape(matched[0]['geometry'])
    counts={'inside':0,'outside':0,'on_boundary':0,'unknown':0}
    for row in rows:
        try:
            point=Point(float(row['longitude']),float(row['latitude']))
            result='on_boundary' if polygon.touches(point) else ('inside' if polygon.contains(point) else 'outside')
        except (ValueError,KeyError,TypeError):result='unknown'
        row['boundary_result']=result
        row['boundary_dataset']='geoBoundaries gbOpen KOR ADM2'
        row['boundary_source_url']=url
        row['api_store_code']='' # Never auto-associate an OSM point with a stock API code
        row['code_address_verified']='no'
        row['approval']='pending'
        counts[result]+=1
    fields=list(dict.fromkeys([*rows[0].keys(),'boundary_result','boundary_dataset','boundary_source_url'])) if rows else []
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    META.write_text(json.dumps({'input_rows':len(rows),'counts':counts,'dataset':url,'auto_approved':0,'production_modified':False,'warning':'Geo-boundary only; store identity and active status still unverified'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('BOUNDARY_REVIEW',json.dumps(counts,ensure_ascii=False))
    print('READ_ONLY: no stock monitoring, approvals, or state changed')
if __name__=='__main__':main()
