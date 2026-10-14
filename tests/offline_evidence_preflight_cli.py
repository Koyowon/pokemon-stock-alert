"""Read-only evidence preflight. Does not approve, register, or call networks."""
import argparse
import csv
import json
from pathlib import Path
from offline_manual_approval_gate import inspect

REQUIRED = {'chain','registry_id','store_code','name','address','source_url','observed_at','barcode'}

def check(root, evidence):
    root, evidence = Path(root), Path(evidence)
    with evidence.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or REQUIRED - set(reader.fieldnames):
            raise ValueError('Missing required evidence columns')
        rows = list(reader)
    registry = json.loads((root/'asan_cu_watch_registry.json').read_text(encoding='utf-8'))['stores']
    cu_state = json.loads((root/'cu_stock_state.json').read_text(encoding='utf-8'))['stores']
    emart = json.loads((root/'stores.json').read_text(encoding='utf-8'))['stores']
    cu_codes = set(cu_state)
    cu_codes.update(str(r['cu_store_code']) for r in registry if r.get('cu_store_code'))
    results = inspect(rows, registry, cu_codes, emart)
    return {'rows':len(rows),'manual_review':sum(r['status']=='MANUAL_REVIEW_REQUIRED' for r in results),
            'blocked':sum(r['status']!='MANUAL_REVIEW_REQUIRED' for r in results),
            'approved':0,'results':results}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence_csv')
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    print(json.dumps(check(args.root,args.evidence_csv),ensure_ascii=False,indent=2))
