"""Bounded read-only diagnostics. No alerts, state writes, or automatic failover."""
import json
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BARCODE = "8800286275732"
RELAY = "https://mcp.aka.page"
ORIGIN = "https://everse.emart24.co.kr"
TIMEOUT = 12
MAX_BYTES = 120000

class PreJson(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_pre = False
        self.parts = []
        self.blocks = []
    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.in_pre = True
            self.parts = []
    def handle_endtag(self, tag):
        if tag == "pre" and self.in_pre:
            self.blocks.append("".join(self.parts))
            self.in_pre = False
    def handle_data(self, data):
        if self.in_pre:
            self.parts.append(data)

def request(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return response.status, response.read(MAX_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read(MAX_BYTES).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return "NETWORK_" + type(error).__name__, ""

def parse(body):
    try:
        return json.loads(body)
    except ValueError:
        p = PreJson()
        p.feed(body)
        for block in p.blocks:
            try:
                obj = json.loads(block)
                if isinstance(obj, dict):
                    return obj
            except ValueError:
                pass
    return None

def qty(value):
    return value if type(value) is int and value >= 0 else None

def emart24():
    doc = json.loads(Path("emart24_jeonju_seed.json").read_text(encoding="utf-8"))
    assert doc["region_id"] == "jeonju" and len(doc["stores"]) == 63
    # Existing seed IDs only, one store per district, no broad scan.
    samples = [("완산구", "06916"), ("덕진구", "00833")]
    for district, code in samples:
        assert district in doc["stores"][code]["address"]
        query = urllib.parse.urlencode({"pluCd": BARCODE, "bizNoArr": code, "format": "html"})
        status, body = request(RELAY + "/api/emart24/inventory?" + query)
        data = parse(body)
        matched = []
        if isinstance(data, dict) and data.get("success") is True:
            rows = data.get("data", {}).get("stores", [])
            if isinstance(rows, list):
                matched = [r for r in rows if isinstance(r, dict) and str(r.get("bizNo", "")) == code]
        relay_qty = qty(matched[0].get("bizQty")) if len(matched) == 1 else None
        print(f"EMART24_RELAY district={district} code={code} http={status} valid_qty={relay_qty is not None} qty={relay_qty if relay_qty is not None else 'UNKNOWN'}", flush=True)
        # Direct official-origin endpoint documented from observed app traffic.
        origin_query = urllib.parse.urlencode({"searchPluCode": BARCODE, "bizNoArr": code})
        status, body = request(ORIGIN + "/api/stock/v2/stock-search/store?" + origin_query,
                               {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
        obj = parse(body)
        goods = obj.get("storeGoodsInfo") if isinstance(obj, dict) else None
        rows = obj.get("storeGoodsQty") if isinstance(obj, dict) else None
        product_ok = isinstance(goods, dict) and str(goods.get("pluCd", goods.get("PLU_CD", ""))) == BARCODE
        matched = [r for r in rows if isinstance(r, dict) and str(r.get("BIZNO", "")) == code] if isinstance(rows, list) else []
        origin_qty = qty(matched[0].get("BIZQTY")) if product_ok and len(matched) == 1 else None
        print(f"EMART24_ORIGIN district={district} code={code} http={status} product_verified={product_ok} valid_qty={origin_qty is not None} qty={origin_qty if origin_qty is not None else 'UNKNOWN'}", flush=True)

def cu():
    doc = json.loads(Path("asan_cu_watch_registry.json").read_text(encoding="utf-8"))
    assert doc["product_barcode"] == BARCODE and len(doc["stores"]) == 119
    known = {str(s["cu_store_code"]): s for s in doc["stores"] if str(s.get("cu_store_code", "")).strip()}
    assert len(known) <= 119
    query = urllib.parse.urlencode({"keyword": BARCODE, "storeKeyword": "아산",
                                    "size": 50, "offset": 0, "storeCheck": "true", "format": "html"})
    status, body = request(RELAY + "/api/cu/inventory?" + query)
    obj = parse(body)
    verified = 0
    # Never infer inventory from an echoed request, store search, or unrelated product.
    payload = obj.get("data") if isinstance(obj, dict) and obj.get("success") is True else None
    if isinstance(payload, dict):
        products = payload.get("products", [])
        if isinstance(products, list):
            for product in products:
                if not isinstance(product, dict) or str(product.get("itemCode", "")) != BARCODE:
                    continue
                rows = product.get("stores", [])
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    code = str(row.get("storeCode", ""))
                    n = qty(row.get("stock"))
                    if code in known and n is not None:
                        verified += 1
                        print(f"CU_ASAN_VERIFIED code={code} qty={n}", flush=True)
    print(f"CU_ASAN http={status} registry_candidates=119 existing_codes={len(known)} verified_product_store_qty={verified} unverified_are_not_zero=true", flush=True)

def self_test():
    assert qty(0) == 0 and qty(2) == 2
    assert qty(None) is None and qty(-1) is None and qty("0") is None and qty(True) is None
    assert parse('<pre>{"success":true}</pre>') == {"success": True}
    print("SELF_TEST_PASS")

if __name__ == "__main__":
    import sys
    self_test()
    if "--self-test" not in sys.argv:
        emart24()
        cu()
        print("DIAGNOSTIC_DONE no_state_writes=true no_telegram=true")
