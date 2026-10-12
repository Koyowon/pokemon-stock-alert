#!/usr/bin/env python3
"""Read-only GS25 Asan OSM code probe. No approvals, stock state writes or alerts."""
import csv, json, re, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'gs25_asan_full_discovery.csv'
OUT = ROOT / 'gs25_asan_code_probe.csv'
API = 'https://mcp.aka.page/api/actions/query'
ITEM = '8800286275732'
# Independently identified names remain hypotheses until a matching API code and address are verified.
NAMES = {
 '10656066635':'아산용화점', '10657129644':'아산주공점',
 '11343477159':'용화미래도점','12768234057':'신창역점',
 '1167114395':'아산온천점','10992203166':'아산온주점',
}
IDS = {'10656066635','10657129644','11343361325','11343477159',
 '11685009324','12392896238','12392906729','12768234057',
 '4631358167','601189985','1167114395','10992203166'}
TERMS = list(dict.fromkeys(list(NAMES.values()) + ['아산','온양','신창','배방','탕정']))
def norm(s):
 s = re.sub(r'\s+','',str(s)).replace('GS25','')
 return s

def query(term):
 params = urllib.parse.urlencode({'action':'gs25CheckInventory','format':'json',
                                  'itemCode':ITEM,'storeKeyword':term,'storeLimit':100})
 req=urllib.request.Request(API+'?'+params,headers={'Accept':'application/json','User-Agent':'gs25-asan-code-probe/1.0'})
 with urllib.request.urlopen(req,timeout=25) as resp:
  data=json.load(resp)
 if not isinstance(data,dict) or data.get('success') is not True or data.get('error') or data.get('isError'):
  raise ValueError('API_FAILURE')
 inv=data.get('data',{}).get('inventory',{})
 stores=inv.get('stores') if isinstance(inv,dict) else None
 if not isinstance(stores,list):raise ValueError('MISSING_STORES')
 return stores

def main():
 with SOURCE.open(encoding='utf-8-sig',newline='') as f:
  candidates={r['osm_id']:r for r in csv.DictReader(f) if r['osm_id'] in IDS}
 if len(candidates)!=12:raise RuntimeError(f'EXPECTED_12_OSM_CANDIDATES_GOT_{len(candidates)}')
 seen={}; errors=[]; incomplete=[]
 for term in TERMS:
  try:
   found=query(term)
   if len(found)>=100:incomplete.append(term)
   for store in found:
    if not isinstance(store,dict):continue
    code=str(store.get('storeCode') or '').strip()
    name=str(store.get('storeName') or store.get('name') or '').strip()
    if code and name:seen[(code,name)]=1
   print(f'PROBE term={term} returned={len(found)}')
  except Exception as e:
   errors.append(term)
   print(f'PROBE_ERROR term={term} type={type(e).__name__}')
  time.sleep(.35)
 rows=[]
 for oid,r in candidates.items():
  target=NAMES.get(oid,'')
  matches=[(code,name) for code,name in seen if target and norm(name)==norm(target)]
  # The API does not provide an address; matching a name alone is insufficient for approval.
  rows.append({'osm_id':oid,'osm_name':r.get('store_name',''),
    'candidate_external_name':target,'osm_address':r.get('address',''),
    'latitude':r.get('latitude',''),'longitude':r.get('longitude',''),
    'api_exact_name_match_count':len(matches),
    'api_matching_codes':';'.join(code for code,name in matches),
    'api_matching_names':';'.join(name for code,name in matches),
    'code_address_verified':'no','approval':'pending',
    'result':('API_NAME_MATCH_ONLY_ADDRESS_UNVERIFIED' if matches else
              'API_QUERY_INCOMPLETE' if errors or incomplete else
              'NO_EXACT_API_NAME_MATCH' if target else 'OSM_STORE_NAME_UNRESOLVED'),
    'source_url':r.get('source_url','')})
 fields=list(rows[0]);
 with OUT.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 print('PROBE_SUMMARY',json.dumps({'candidates':len(rows),'name_matched':sum(bool(x['api_matching_codes']) for x in rows),'errors':errors,'truncated_terms':incomplete,'auto_approved':0,'production_modified':False},ensure_ascii=False))
 print('READ_ONLY: no approvals, state writes, or Telegram alerts')

if __name__=='__main__':main()
