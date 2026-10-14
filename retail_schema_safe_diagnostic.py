"""Read-only schema diagnostics. No response values, credentials or raw bodies in logs."""
import json
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BARCODE = "8800286275732"
MAX_BODY = 65536
TIMEOUT = 12
ALLOWED_KEYS = {"data","result","results","success","code","message","storeGoodsInfo","storeGoodsQty","pluCd","PLU_CD","BIZNO","BIZQTY","bizNo","bizQty","stores","products","itemCode","storeCode","stock","quantity","stockQty","total","count","status","error"}
def fetch(url, headers):
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as r:
            return r.status, r.headers.get("Content-Type", "").split(";")[0], r.read(MAX_BODY).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "").split(";")[0], e.read(MAX_BODY).decode("utf-8", "replace")
    except (OSError, TimeoutError) as e:
        return type(e).__name__, "none", ""
class Pre(HTMLParser):
    def __init__(self):
        super().__init__(); self.active=False; self.parts=[]; self.blocks=[]
    def handle_starttag(self, tag, attrs):
        if tag=="pre": self.active=True; self.parts=[]
    def handle_endtag(self, tag):
        if tag=="pre" and self.active: self.blocks.append("".join(self.parts)); self.active=False
    def handle_data(self, value):
        if self.active: self.parts.append(value)
def decode(body):
    try: return json.loads(body), "json"
    except (ValueError, TypeError): pass
    p=Pre(); p.feed(body)
    for block in p.blocks[:2]:
        try: return json.loads(block), "html_pre_json"
        except ValueError: pass
    return None, "not_json"
def shape(obj, depth=0):
    if depth>=3: return "max_depth"
    if isinstance(obj, dict):
        # Only approved schema keys; unknown keys are counted, never printed.
        keys=sorted(k for k in obj if k in ALLOWED_KEYS)
        return {"type":"object","known_keys":keys,"other_key_count":len(obj)-len(keys),"fields":{k:shape(obj[k],depth+1) for k in keys if k not in ("message","error")}}
    if isinstance(obj, list):
        return {"type":"array","length":len(obj),"first":shape(obj[0],depth+1) if obj else "empty"}
    return type(obj).__name__
def run():
    seed=json.loads(Path("emart24_jeonju_seed.json").read_text(encoding="utf-8"))
    assert seed["region_id"]=="jeonju" and len(seed["stores"])==63
    for code in ("06916","00833"):
        assert code in seed["stores"]
        query=urllib.parse.urlencode({"searchPluCode":BARCODE,"bizNoArr":code})
        status,content_type,body=fetch("https://everse.emart24.co.kr/api/stock/v2/stock-search/store?"+query,{"Accept":"application/json","X-Requested-With":"XMLHttpRequest"})
        obj,fmt=decode(body)
        print("EMART24_SCHEMA",json.dumps({"store_code":code,"http":status,"content_type":content_type,"format":fmt,"shape":shape(obj)},ensure_ascii=False),flush=True)
    query=urllib.parse.urlencode({"keyword":BARCODE,"storeKeyword":"아산","size":50,"offset":0,"storeCheck":"true","format":"html"})
    status,content_type,body=fetch("https://mcp.aka.page/api/cu/inventory?"+query,{"Accept":"text/html"})
    obj,fmt=decode(body)
    print("CU_RELAY_SCHEMA",json.dumps({"http":status,"content_type":content_type,"format":fmt,"shape":shape(obj)},ensure_ascii=False),flush=True)
    registry=json.loads(Path("asan_cu_watch_registry.json").read_text(encoding="utf-8"))
    assert registry["product_barcode"]==BARCODE and len(registry["stores"])==119
    rows=registry["stores"]; codes=[str(r.get("cu_store_code","")).strip() for r in rows if str(r.get("cu_store_code","")).strip()]
    print("CU_REGISTRY_AUDIT",json.dumps({"candidates":len(rows),"coded":len(codes),"uncoded":len(rows)-len(codes),"unique_codes":len(set(codes)),"duplicate_codes":len(codes)-len(set(codes)),"currently_verified_live_stock":0,"note":"registry codes are historical and unverified; zero means no validated observations, not zero inventory"},ensure_ascii=False),flush=True)
    print("READ_ONLY_DONE no_secrets_logged=true no_response_values_logged=true no_telegram=true no_state_writes=true")
def test():
    assert shape({"storeGoodsInfo":{"pluCd":"secret"},"privateKey":"hidden"})["known_keys"]==["storeGoodsInfo"]
    assert shape({"storeGoodsInfo":{"pluCd":"secret"},"privateKey":"hidden"})["other_key_count"]==1
    assert decode('<pre>{"success":true}</pre>')[1]=="html_pre_json"
    assert shape([{"BIZQTY":7}])["first"]["fields"]["BIZQTY"]=="int"
    print("SCHEMA_SELF_TEST_PASS")
if __name__=="__main__":
    import sys
    test()
    if "--self-test" not in sys.argv: run()
