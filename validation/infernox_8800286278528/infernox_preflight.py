"""Offline preflight only: no network, Telegram, stock writes or activation."""
import json
import re
from pathlib import Path

BARCODE = '8800286278528'
BRANDS = ('cu', 'gs25', 'emart24', 'seven')
FIELDS = {'cu':('itemCode','stockItemCode'), 'gs25':('itemCode',),
          'emart24':('pluCd',), 'seven':('itemCode','smCd','stokMngCd')}

def valid_ean13(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{13}',value):return False
    return sum(int(n)*(1 if i%2==0 else 3) for i,n in enumerate(value))%10==0

def product_key(barcode,brand,store):
    if not valid_ean13(barcode) or brand not in BRANDS or not re.fullmatch(r'[0-9]+',store):
        raise ValueError('INVALID_IDENTITY')
    return f'{barcode}|{brand}|{store}'

def state_paths(work,barcode,brand):
    product_key(barcode,brand,'0')
    base=Path(work)/'products'/barcode/brand
    return {'stock':base/'stock.json','alerts':base/'alerts.json',
            # Budget/holds are deliberately outside the product namespace.
            'shared_budget':Path(work)/'response_budget_v1.sqlite',
            'brand_hold':Path(work)/(brand+'_relay_hold.json')}

def identity_check(brand,evidence):
    """Supplied observations are checked, never used to enable a live monitor."""
    if brand not in BRANDS:raise ValueError('UNKNOWN_BRAND')
    if not isinstance(evidence,dict):return 'MISSING_RESPONSE_EVIDENCE'
    if evidence.get('fixture') is not False:return 'FIXTURE_OR_UNKNOWN_PROVENANCE'
    if evidence.get('brand')!=brand:return 'BRAND_MISMATCH'
    if evidence.get('source_kind') not in ('official_app_response','relay_response'):
        return 'NOT_A_PROVIDER_RESPONSE'
    if evidence.get('response_barcode')!=BARCODE:return 'BARCODE_MISMATCH'
    if not isinstance(evidence.get('captured_at'),str) or not evidence['captured_at'].strip():return 'MISSING_CAPTURE_TIME'
    name=evidence.get('response_name')
    if not isinstance(name,str):return 'MISSING_PRODUCT_NAME'
    name=re.sub(r'\s+','',name).lower()
    if '인페르노x' not in name or any(w in name for w in ('일본','영문','키트','박스','box','セット','세트')):
        return 'PRODUCT_NAME_OR_VARIANT_MISMATCH'
    if evidence.get('sale_unit')!='pack':return 'SALE_UNIT_UNCONFIRMED'
    codes=evidence.get('codes')
    if not isinstance(codes,dict) or any(not isinstance(codes.get(k),str) or not codes[k].strip() for k in FIELDS[brand]):
        return 'MISSING_BRAND_IDENTIFIERS'
    if brand=='cu' and codes['stockItemCode']!=BARCODE:return 'CU_SELECTED_PRODUCT_MISMATCH'
    return 'IDENTITY_CONSISTENT_STOCK_UNTESTED'

def inventory_check(brand,evidence):
    reason=identity_check(brand,evidence)
    if reason!='IDENTITY_CONSISTENT_STOCK_UNTESTED':return reason
    rows=evidence.get('inventory')
    if not isinstance(rows,list) or not rows:return 'MISSING_INVENTORY_EVIDENCE'
    for row in rows:
        if not isinstance(row,dict) or row.get('product_barcode')!=BARCODE:return 'STOCK_PRODUCT_MISMATCH'
        if not all(isinstance(row.get(k),str) and row[k].strip() for k in ('store_code','name','address')):
            return 'MISSING_STORE_IDENTITY'
        if row.get('store_identity_verified') is not True:return 'STORE_IDENTITY_UNCONFIRMED'
        qty=row.get('quantity')
        if type(qty) is not int or qty<0:return 'UNKNOWN_OR_INVALID_QUANTITY'
    return 'SUPPLIED_SAMPLE_CONSISTENT_APPROVAL_REQUIRED'

def daily_requests(products):
    total=0
    for item in products:
        calls=item['cu_calls']+item['gs25_calls'];interval=item['interval_seconds']
        if type(interval) is not int or interval<=0 or type(calls) is not int or calls<0:raise ValueError('INVALID_BUDGET_INPUT')
        total+=calls*((86400+interval-1)//interval)
    return total

def report():
    return {'barcode':BARCODE,'ean13_valid':valid_ean13(BARCODE),'operationally_enabled':False,
            'brands':{brand:identity_check(brand,None) for brand in BRANDS},
            'cu_gs_daily_budget':2400,
            'existing_20min_estimate':daily_requests([{'cu_calls':19,'gs25_calls':13,'interval_seconds':1200}]),
            'two_products_20min_estimate':daily_requests([{'cu_calls':19,'gs25_calls':13,'interval_seconds':1200}]*2),
            'two_products_40min_estimate':daily_requests([{'cu_calls':19,'gs25_calls':13,'interval_seconds':2400}]*2),
            'estimates_are_not_live_measurements':True}

if __name__=='__main__':print(json.dumps(report(),ensure_ascii=False,indent=2))
