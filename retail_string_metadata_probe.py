"""Bounded read-only field metadata check; never logs raw response values."""
import json
import urllib.request
import urllib.error
import urllib.parse

BARCODE="8800286275732"
def meta(value):
    if value is None:
        return dict(is_null=True,is_empty=False,length=None,json_parseable=False)
    if not isinstance(value,str):
        return dict(is_null=False,is_empty=False,length=None,json_parseable=False)
    try:
        json.loads(value)
        parseable=True
    except (ValueError,TypeError):
        parseable=False
    return dict(is_null=False,is_empty=len(value)==0,length=len(value),json_parseable=parseable)

def structure(value):
    """Describe parsed JSON shape only, never keys or values."""
    if not isinstance(value, str):
        return {"outer_type": type(value).__name__, "json_type": "not_string", "structurally_valid": False}
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return {"outer_type": "str", "json_type": "invalid_json", "structurally_valid": False}
    if parsed is None:
        kind = "null"
    elif isinstance(parsed, bool):
        kind = "boolean"
    elif isinstance(parsed, dict):
        kind = "object"
    elif isinstance(parsed, list):
        kind = "array"
    elif isinstance(parsed, str):
        kind = "string"
    elif isinstance(parsed, (int, float)):
        kind = "number"
    else:
        kind = "unknown"
    return {"outer_type": "str", "json_type": kind,
            "structurally_valid": isinstance(parsed, (dict, list))}

def diagnose_stock_fields(data):
    """Only safe structural facts; never return response values."""
    if not isinstance(data,dict):
        return {"envelope":"invalid","verified_inventory":False,"reason":"invalid_envelope"}
    info=data.get("storeGoodsInfo")
    qty=data.get("storeGoodsQty")
    a=structure(info)
    b=structure(qty)
    # A JSON-encoded number is not an inventory record, even with HTTP 200.
    valid_info=isinstance(info,dict)
    valid_qty=isinstance(qty,list)
    if isinstance(info,str) and a["json_type"]=="number":
        reason="numeric_scalar_in_goods_field"
    elif isinstance(qty,str) and b["json_type"]=="number":
        reason="numeric_scalar_in_quantity_field"
    elif not (valid_info and valid_qty):
        reason="unexpected_field_types"
    else:
        reason="schema_only_not_inventory_verified"
    return {"envelope":"object","goods":a,"quantity":b,
            "same_string_shape":isinstance(info,str) and isinstance(qty,str) and len(info)==len(qty),
            "verified_inventory":False,"reason":reason}

def compare_diagnoses(items):
    """Classify whether a bounded request comparison changes response shape."""
    if len(items)!=3:
        return "incomplete"
    signatures=[(status, report.get("reason"),report.get("goods",{}).get("json_type","unavailable"),report.get("quantity",{}).get("json_type","unavailable")) for status,report in items]
    return "same_shape" if signatures[0]==signatures[1]==signatures[2] else "different_shape"

def prepare_stock_lookup():
    """Publicly documented UI preparation call; status only, never body."""
    form=urllib.parse.urlencode({"pluCd":BARCODE,"searchPage":"STOCK_SEARCH_SERVICE"}).encode("utf-8")
    req=urllib.request.Request(
        "https://everse.emart24.co.kr/api/stock/v1/search/keyword",
        data=form,
        headers={"Accept":"application/json","X-Requested-With":"XMLHttpRequest",
                 "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8"},
        method="POST")
    try:
        with urllib.request.urlopen(req,timeout=12) as response:
            response.read(65536)
            return response.status
    except urllib.error.HTTPError as e:
        return e.code
    except (OSError,ValueError,TimeoutError) as e:
        return type(e).__name__

def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={"Accept":"application/json","X-Requested-With":"XMLHttpRequest"}),timeout=12) as r:
            return r.status,json.loads(r.read(65536))
    except urllib.error.HTTPError as e:
        return e.code,None
    except (OSError,ValueError,TimeoutError) as e:
        return type(e).__name__,None

def main():
    assert meta(None)["is_null"]
    assert meta("")["is_empty"]
    assert meta('{"key":"private"}')["json_parseable"]
    assert not meta("private")["json_parseable"]
    assert structure('null')["json_type"] == "null"
    assert structure('{"private":"never print"}')["json_type"] == "object"
    assert structure('[1]')["json_type"] == "array"
    assert structure('"secret"')["json_type"] == "string"
    assert not structure('null')["structurally_valid"]
    assert structure('{"private":"never print"}')["structurally_valid"]
    assert diagnose_stock_fields({"storeGoodsInfo":"123","storeGoodsQty":"456"})["reason"]=="numeric_scalar_in_goods_field"
    assert not diagnose_stock_fields({"storeGoodsInfo":{"private":"secret"},"storeGoodsQty":[]})["verified_inventory"]
    assert diagnose_stock_fields(None)["reason"]=="invalid_envelope"
    assert diagnose_stock_fields({"storeGoodsInfo":"not json","storeGoodsQty":"0"})["reason"]=="numeric_scalar_in_quantity_field"
    assert diagnose_stock_fields({"storeGoodsInfo":"not json","storeGoodsQty":"not json"})["reason"]=="unexpected_field_types"
    fake={"storeGoodsInfo":"123","storeGoodsQty":"456"}
    sample=(200,diagnose_stock_fields(fake))
    assert compare_diagnoses([sample,sample,sample])=="same_shape"
    assert compare_diagnoses([sample])=="incomplete"
    assert compare_diagnoses([sample,sample,(403,diagnose_stock_fields(None))])=="different_shape"
    print("METADATA_SELF_TEST_PASS",flush=True)
    import sys
    if "--self-test" in sys.argv:return
    # UI traffic reference: POST keyword preparation before per-store GET.
    # This is an unverified behavioral comparison, not a stock confirmation.
    prep_status=prepare_stock_lookup()
    print("EMART24_PREPARE_STATUS",json.dumps({"http":prep_status,"inventory_verified":False}),flush=True)
    comparison=[]
    # Compare the existing single-store request with a bounded two-store
    # candidate. This does not establish that comma separation is supported.
    for label,code in (("single_a","06916"),("single_b","00833"),("combined_candidate","06916,00833")):
        params=urllib.parse.urlencode({"searchPluCode":BARCODE,"bizNoArr":code})
        status,data=get("https://everse.emart24.co.kr/api/stock/v2/stock-search/store?"+params)
        fields={key:{**meta(data.get(key)), **structure(data.get(key))} for key in ("storeGoodsInfo","storeGoodsQty")} if isinstance(data,dict) else {}
        diagnosis=diagnose_stock_fields(data)
        comparison.append((status,diagnosis))
        print("EMART24_FIELD_METADATA",json.dumps({"request_kind":label,"http":status,"fields":fields,"diagnosis":diagnosis}),flush=True)
    print("EMART24_REQUEST_COMPARISON",json.dumps({"result":compare_diagnoses(comparison),"combined_parameter_format_verified":False,"inventory_verified":False}),flush=True)
    # Reference pair from a published March 2026 Emart24 traffic replay guide.
    # Compare response shape only; neither product availability nor stock is assumed.
    reference_query=urllib.parse.urlencode({
        "searchPluCode":"8800244010504",
        "bizNoArr":"28339,05015,23233,29512,24437,29109,26137,29796,30200,28057,27928,29570,30162,28187,22579,00367,28967,00737"})
    reference_http,reference_data=get("https://everse.emart24.co.kr/api/stock/v2/stock-search/store?"+reference_query)
    reference_report=diagnose_stock_fields(reference_data)
    print("EMART24_REFERENCE_SHAPE",json.dumps({
        "http":reference_http,
        "goods_type":reference_report.get("goods",{}).get("outer_type","unavailable"),
        "qty_type":reference_report.get("quantity",{}).get("outer_type","unavailable"),
        "reason":reference_report["reason"],
        "structural_candidate":reference_report["reason"]=="schema_only_not_inventory_verified",
        "inventory_verified":False}),flush=True)
    params=urllib.parse.urlencode({"keyword":BARCODE,"storeKeyword":"아산","size":50,"storeCheck":"true","format":"html"})
    try:
        with urllib.request.urlopen(urllib.request.Request("https://mcp.aka.page/api/cu/inventory?"+params,headers={"Accept":"text/html"}),timeout=12) as r:
            status=r.status
    except urllib.error.HTTPError as e:status=e.code
    except (OSError,TimeoutError) as e:status=type(e).__name__
    print("CU_RELAY_HTTP",status,flush=True)
    print("READ_ONLY no_telegram=true no_state_writes=true",flush=True)
if __name__=="__main__":main()
