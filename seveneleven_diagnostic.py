import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://mcp.aka.page/api/seveneleven"
PRODUCT = "비전)포켓몬확장팩(30주년)_H"
REGIONS = ["남원", "아산"]
TIMEOUT = 20

def request_api(path, params):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(100000).decode("utf-8", errors="replace")
        return status, content_type, raw, None
    except urllib.error.HTTPError as exc:
        raw = exc.read(4000).decode("utf-8", errors="replace")
        return exc.code, "", raw, "HTTP_ERROR"
    except Exception as exc:
        return None, "", "", f"{type(exc).__name__}: {exc}"

def inspect(name, path, params):
    print("\n" + "=" * 65, flush=True)
    print("TEST:", name, flush=True)
    print("PARAMS:", json.dumps(params, ensure_ascii=False), flush=True)
    status, content_type, raw, error = request_api(path, params)
    print("HTTP:", status, flush=True)
    print("CONTENT_TYPE:", content_type, flush=True)
    if error:
        print("ERROR:", error, flush=True)
    print("BODY_LENGTH:", len(raw), flush=True)
    try:
        data = json.loads(raw)
        print("JSON:", json.dumps(data, ensure_ascii=False, indent=2)[:6000], flush=True)
        analyze(data)
    except (ValueError, TypeError):
        print("BODY_PREVIEW:", raw[:4000], flush=True)
        print("NOTE: Non-JSON response; quantity not verified.", flush=True)
    if status != 200:
        print("WARNING: Request failed. This does NOT mean zero stock.", flush=True)
    return status

def analyze(data):
    if not isinstance(data, dict):
        print("ANALYSIS: Unexpected JSON structure.", flush=True)
        return

    print("TOP_LEVEL_KEYS:", list(data.keys()), flush=True)
    found = []

    def walk(obj, path="root", depth=0):
        if depth > 8 or len(found) >= 40:
            return
        if isinstance(obj, dict):
            quantity_keys = [
                key for key in obj
                if any(word in key.lower() for word in
                       ("qty", "quantity", "stock", "remain", "inventory"))
            ]
            if quantity_keys:
                found.append((path, {
                    key: obj[key] for key in quantity_keys
                }))
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    walk(value, path + "." + str(key), depth + 1)
        elif isinstance(obj, list):
            for index, value in enumerate(obj[:100]):
                walk(value, path + "[" + str(index) + "]", depth + 1)

    walk(data)
    if not found:
        print("QUANTITY_FIELDS: None found; inventory NOT confirmed.", flush=True)
    else:
        for path, values in found:
            print("QUANTITY_FIELD:", path,
                  json.dumps(values, ensure_ascii=False), flush=True)
        print("NOTE: Field meanings must be verified before alerts.", flush=True)

def main():
    print("Seven-Eleven 30th Anniversary Inventory Diagnostic", flush=True)
    print("PRODUCT:", PRODUCT, flush=True)
    print("READ-ONLY: no purchases, no state updates, no alerts", flush=True)

    inspect(
        "30th PRODUCT SEARCH",
        "/products",
        {"query": PRODUCT, "format": "html"},
    )
    time.sleep(2)

    for region in REGIONS:
        inspect(
            "30th INVENTORY - " + region,
            "/inventory",
            {
                "keyword": PRODUCT,
                "storeKeyword": region,
                "storeLimit": "10",
                "format": "html",
            },
        )
        time.sleep(2)

    print("\n" + "=" * 65, flush=True)
    print("DIAGNOSTIC FINISHED", flush=True)
    print("HTTP 502, null, or missing quantity is NOT zero stock.", flush=True)

if __name__ == "__main__":
    main()
