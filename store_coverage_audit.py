"""Read-only coverage report from existing saved stock states; does not query live stores."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CITIES = {'namwon':'남원','asan':'아산','jeonju':'전주','jeju':'제주'}

def load(path):
    try:
        return json.loads((ROOT/path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}

def city_of(address):
    address = str(address or '')
    for key, name in CITIES.items():
        if name+'시' in address:
            return key
    return None

def main():
    rows=[]
    emart=load('stores.json').get('stores',{})
    for code, store in emart.items():
        city=city_of(store.get('address',''))
        if city:
            rows.append(('emart24',city,str(code),store.get('name',''),store.get('address',''),'cached_directory'))
    cu=load('cu_stock_state.json').get('stores',{})
    for code, store in cu.items():
        city=city_of(store.get('address',''))
        if city:
            rows.append(('cu',city,str(code),store.get('name',''),store.get('address',''),'observed_inventory'))
    gs=load('gs25_independent/gs25_stock_state.json').get('regions',{})
    for city, block in gs.items():
        if city not in CITIES: continue
        for code, store in block.get('stores',{}).items():
            rows.append(('gs25',city,str(code),store.get('name',''),'', 'observed_inventory'))
    with (ROOT/'store_coverage_inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['chain','region','store_code','store_name','address','source'])
        writer.writerows(sorted(set(rows)))
    counts={}
    for chain,city,*_ in rows:
        counts[(chain,city)]=counts.get((chain,city),0)+1
    with (ROOT/'store_coverage_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['chain','region','known_stores','official_total','coverage_rate','status'])
        for chain in ('emart24','cu','gs25'):
            for city in CITIES:
                if chain=='emart24' and city=='jeju':
                    writer.writerow([chain,city,0,'','','not_applicable'])
                else:
                    writer.writerow([chain,city,counts.get((chain,city),0),'','','official_directory_comparison_needed'])
    print('Coverage audit complete: {} saved store records'.format(len(rows)))
    print('Official totals unknown; these files do not establish full coverage.')

if __name__=='__main__':
    main()
