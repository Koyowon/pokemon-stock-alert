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
    assert diagnose_stock_fields({"storeGoodsInfo":"not json","storeGoodsQty":"0"})["reason"]=="unexpected_field_types"
    print("METADATA_SELF_TEST_PASS",flush=True)
    import sys
    if "--self-test" in sys.argv:return
    for code in ("06916","00833"):
        params=urllib.parse.urlencode({"searchPluCode":BARCODE,"bizNoArr":code})
        status,data=get("https://everse.emart24.co.kr/api/stock/v2/stock-search/store?"+params)
        fields={key:{**meta(data.get(key)), **structure(data.get(key))} for key in ("storeGoodsInfo","storeGoodsQty")} if isinstance(data,dict) else {}
        print("EMART24_FIELD_METADATA",json.dumps({"code":code,"http":status,"fields":fields,"diagnosis":diagnose_stock_fields(data)}),flush=True)
    params=urllib.parse.urlencode({"keyword":BARCODE,"storeKeyword":"아산","size":50,"storeCheck":"true","format":"html"})
    try:
        with urllib.request.urlopen(urllib.request.Request("https://mcp.aka.page/api/cu/inventory?"+params,headers={"Accept":"text/html"}),timeout=12) as r:
            status=r.status
    except urllib.error.HTTPError as e:status=e.code
    except (OSError,TimeoutError) as e:status=type(e).__name__
    print("CU_RELAY_HTTP",status,flush=True)
    print("READ_ONLY no_telegram=true no_state_writes=true",flush=True)
if __name__=="__main__":main()
