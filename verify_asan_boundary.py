#!/usr/bin/env python3
"""Read-only GS25 Asan OSM point review against geoBoundaries ADM2."""
import csv
import json
import os
import urllib.request
from pathlib import Path
from shapely.geometry import Point, shape
from shapely.ops import unary_union

BASE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('SOURCE_CSV', str(BASE / 'gs25_asan_full_discovery.csv')))
OUT = Path(os.environ.get('OUTPUT_CSV', str(BASE / 'gs25_asan_boundary_review.csv')))
META = Path(os.environ.get('OUTPUT_JSON', str(BASE / 'gs25_asan_boundary_summary.json')))
API = 'https://www.geoboundaries.org/api/current/gbOpen/KOR/ADM2/'

def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'pokemon-stock-alert-boundary-review/1.1', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=70) as response:
        return json.load(response)

def main():
    with SOURCE.open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise RuntimeError('EMPTY_DISCOVERY_CSV')
    if len(rows) != 26:
        print(f'NOTICE: input row count {len(rows)} (original 26)')
    metadata = get_json(API)
    url = metadata.get('simplifiedGeometryGeoJSON') or metadata.get('gjDownloadURL')
    if not url:
        raise RuntimeError('BOUNDARY_DOWNLOAD_URL_MISSING')
    features = get_json(url).get('features', [])
    candidates = []
    for feature in features:
        props = feature.get('properties') or {}
        names = [str(value) for key, value in props.items() if key.lower() in ('shapename', 'name', 'adm_nm', 'name_en', 'name_ko')]
        if not any('아산' in name or 'asan' in name.lower() for name in names):
            continue
        geom = shape(feature['geometry'])
        if geom.is_empty or not geom.is_valid:
            raise RuntimeError('ASAN_BOUNDARY_INVALID_GEOMETRY')
        center = geom.centroid
        print(f"ASAN_POLYGON shapeID={props.get('shapeID', '')} bounds={geom.bounds} centroid=({center.y:.6f},{center.x:.6f})")
        # A name collision exists in the dataset: the other Asan-si shape is near Busan.
        # Select only geographically plausible Asan polygons; do not merge distant shapes.
        if 36.5 <= center.y <= 37.2 and 126.7 <= center.x <= 127.5:
            candidates.append(geom)
        else:
            print(f"ASAN_POLYGON_SKIPPED_OUT_OF_REGION shapeID={props.get('shapeID', '')}")
    if not candidates:
        raise RuntimeError('ASAN_BOUNDARY_UNRESOLVED: no Asan-region polygon')
    polygon = unary_union(candidates)
    if polygon.is_empty or not polygon.is_valid:
        raise RuntimeError('ASAN_BOUNDARY_MERGE_INVALID')
    print(f'ASAN_BOUNDARY_OK selected_features={len(candidates)} merged_geometry={polygon.geom_type}')
    counts = {'inside': 0, 'outside': 0, 'on_boundary': 0, 'unknown': 0}
    for row in rows:
        try:
            point = Point(float(row['longitude']), float(row['latitude']))
            result = 'on_boundary' if polygon.touches(point) else ('inside' if polygon.contains(point) else 'outside')
        except (ValueError, KeyError, TypeError):
            result = 'unknown'
        row['boundary_result'] = result
        row['boundary_dataset'] = 'geoBoundaries gbOpen KOR ADM2'
        row['boundary_source_url'] = url
        row['api_store_code'] = ''
        row['code_address_verified'] = 'no'
        row['approval'] = 'pending'
        counts[result] += 1
    fields = list(dict.fromkeys(key for row in rows for key in row))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    META.write_text(json.dumps({'input_rows': len(rows), 'counts': counts, 'dataset': url, 'auto_approved': 0, 'production_modified': False, 'warning': 'Geographic review only; store identity and status unverified'}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('BOUNDARY_REVIEW', json.dumps(counts, ensure_ascii=False))
    print('READ_ONLY: no stock monitoring, approvals, or state changed')

if __name__ == '__main__':
    main()
