"""Read-only Emart24 product-search verification. Never log API response values."""
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BARCODE="8800286275732"
BASE="https://everse.emart24.co.kr"
MAX_BYTES=65536
TIMEOUT=12
def request(path,form=None):
    headers={"Accept":"application/json","X-Requested-With":"XMLHttpRequest"}
    body=None
    if form is not None:
        body=urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"]="application/x-www-form-urlencoded; charset=UTF-8"
    req=urllib.request.Request(BASE+path,data=body,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=TIMEOUT) as r:
            return r.status,decode(r.read(MAX_BYTES))
    except urllib.error.HTTPError as e:
        return e.code,None
    except (OSError,ValueError,TimeoutError) as e:
        return type(e).__name__,None
def decode(raw):
    try:return json.loads(raw)
    except (ValueError,TypeError):return None
# Approved candidate fields only; do not log unknown keys or values.
CODE_FIELDS=("pluCd","pluCode","barcode","barCode","ean")
def code_audit(rows):
    counts={field:{"present":0,"exact_match":0} for field in CODE_FIELDS}
    if isinstance(rows,list):
        for row in rows:
            if isinstance(row,dict):
                for field in CODE_FIELDS:
                    if field in row:
                        counts[field]["present"]+=1
                        value=row[field]
                        if isinstance(value,(str,int)) and not isinstance(value,bool) and str(value)==BARCODE:
                            counts[field]["exact_match"]+=1
    return counts
def matches(rows):
    if not isinstance(rows,list):return False
    return any(item["exact_match"]>0 for item in code_audit(rows).values())
def search_summary(status,obj):
    if not isinstance(obj,dict):
        return {"http":status,"envelope":"invalid","barcode_verified":False,"product_list_type":"unknown"}
    rows=obj.get("productList")
    return {"http":status,"envelope":"object","product_list_type":type(rows).__name__,"barcode_verified":matches(rows),"returned_count":len(rows) if isinstance(rows,list) else None,"code_fields":code_audit(rows)}
def stock_summary(status,obj):
    if not isinstance(obj,dict):return {"http":status,"valid_stock_schema":False,"goods_type":"unknown","qty_type":"unknown"}
    goods=obj.get("storeGoodsInfo")
    rows=obj.get("storeGoodsQty")
    return {"http":status,"goods_type":type(goods).__name__,"qty_type":type(rows).__name__,"valid_stock_schema":isinstance(goods,dict) and isinstance(rows,list) and str(goods.get("pluCd",""))==BARCODE}
def main():
    assert matches([{"pluCd":BARCODE}])
    assert matches([{"barcode":BARCODE}])
    assert matches([{"ean":int(BARCODE)}])
    assert not matches([{"barcode":True}])
    assert not matches([{"other":BARCODE}])
    assert code_audit([{"pluCd":"private","barcode":BARCODE}])["barcode"]["exact_match"] == 1
    assert not matches([{"pluCd":"other"}])
    assert not stock_summary(200,{"storeGoodsInfo":"123","storeGoodsQty":"123"})["valid_stock_schema"]
    assert not search_summary(200,{"productList":[{"pluCd":"other"}]})["barcode_verified"]
    assert search_summary(200,{"productList":[{"pluCd":BARCODE}]})["barcode_verified"]
    assert search_summary(200,{"productList":[]})["returned_count"] == 0
    print("PRODUCT_SEARCH_SELF_TEST_PASS",flush=True)
    import sys
    if "--self-test" in sys.argv:return
    # Official UI searches by product name; barcode lookup may not be indexed.
    # Fixed, bounded terms only. No dynamic expansion, no response contents logged.
    for label, term in (("barcode", BARCODE), ("pokemon_card", "포켓몬카드"), ("pokemon", "포켓몬")):
        pages = (1,) if label == "barcode" else (1, 2, 3)
        for page in pages:
            status,obj=request("/stock/stock/search",{"currentPage":str(page),"pageCnt":"10","sortType":"SALE","saleProductYn":"N","searchWord":term})
            summary=search_summary(status,obj)
            print("EMART24_PRODUCT_SEARCH",json.dumps({"query_kind":label,"page":page,**summary}),flush=True)
            if summary["barcode_verified"] or summary.get("returned_count") != 10:
                break
    # Read-only comparison only, no stock quantity extraction.
    for code in ("06916","00833"):
        query=urllib.parse.urlencode({"searchPluCode":BARCODE,"bizNoArr":code})
        stock_status,stock_obj=request("/api/stock/v2/stock-search/store?"+query)
        print("EMART24_STOCK_STRUCTURE",json.dumps({"store_code":code,**stock_summary(stock_status,stock_obj)}),flush=True)
    # CU relay remains unverified; only status, never body or error text.
    cu_query=urllib.parse.urlencode({"keyword":BARCODE,"storeKeyword":"아산","size":50,"storeCheck":"true","format":"html"})
    cu_req=urllib.request.Request("https://mcp.aka.page/api/cu/inventory?"+cu_query,headers={"Accept":"text/html"})
    try:
        with urllib.request.urlopen(cu_req,timeout=TIMEOUT) as response:
            cu_status=response.status
    except urllib.error.HTTPError as e:
        cu_status=e.code
    except (OSError,TimeoutError) as e:
        cu_status=type(e).__name__
    print("CU_RELAY_STATUS",json.dumps({"http":cu_status,"inventory_verified":False}),flush=True)
    # Static check only: never execute Telegram workflow or access secrets.
    tg=Path(".github/workflows/test-telegram.yml")
    telegram_test_only=tg.is_file() and "[TEST ONLY]" in tg.read_text(encoding="utf-8")
    print("TELEGRAM_SAFETY",json.dumps({"test_only_label_present":telegram_test_only,"sent":False}),flush=True)
    print("DIAGNOSTIC_DONE no_stock_alerts=true no_telegram=true no_state_writes=true",flush=True)
if __name__=="__main__":main()
