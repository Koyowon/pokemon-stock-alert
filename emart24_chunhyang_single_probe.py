"""One-shot, read-only Emart24 inventory schema diagnostic for one fixed store."""
import json
import urllib.error
import urllib.parse
import urllib.request

URL = "https://mcp.aka.page/api/emart24/inventory"
STORE = "26757"
PLU = "8800286275732"


def describe(payload):
    if not isinstance(payload, dict):
        return {"payload_type": type(payload).__name__}
    data = payload.get("data")
    result = {"success_type": type(payload.get("success")).__name__,
              "success": payload.get("success") if type(payload.get("success")) is bool else "NON_BOOLEAN",
              "data_type": type(data).__name__}
    if not isinstance(data, dict):
        return result
    rows = data.get("stores")
    result["stores_type"] = type(rows).__name__
    if not isinstance(rows, list):
        return result
    result["stores_count"] = len(rows)
    matching = [r for r in rows if isinstance(r, dict) and str(r.get("bizNo", "")).strip() == STORE]
    result["matching_store_count"] = len(matching)
    result["quantities"] = []
    for row in matching:
        present = "bizQty" in row
        qty = row.get("bizQty")
        safe = qty if (qty is None or type(qty) in (int, float, bool) or (type(qty) is str and len(qty) <= 20 and all(c in "0123456789.-+ " for c in qty))) else "REDACTED"
        result["quantities"].append({"field_present": present, "type": type(qty).__name__ if present else "missing", "value": safe if present else "MISSING"})
    return result


def main():
    params = urllib.parse.urlencode({"pluCd": PLU, "bizNoArr": STORE})
    request = urllib.request.Request(URL + "?" + params, headers={"User-Agent": "PokemonStockMonitor/1.1", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            payload = json.load(response)
        print("HTTP_STATUS:", status)
        print("SCHEMA:", json.dumps(describe(payload), ensure_ascii=False, sort_keys=True))
    except urllib.error.HTTPError as exc:
        print("HTTP_STATUS:", exc.code)
        raise SystemExit(1)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError) as exc:
        print("REQUEST_OR_SCHEMA_ERROR:", type(exc).__name__)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
