"""GS25 public-endpoint read-only diagnostic; no authentication or state changes.

This diagnostic is intentionally limited to three GET requests. It never
prints response bodies, tokens, cookies, or credentials. HTTP errors are not
interpreted as zero stock. No repository file is modified.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://b2c-bff.woodongs.com"
LATITUDE, LONGITUDE = 35.4164, 127.3904  # Namwon city-center reference
PRODUCTS = (
    ("COMPARISON_PRODUCT", "8800286278535"),
    ("POKEMON_30TH", "8800286275732"),
)
TIMEOUT_SECONDS = 12
MAX_BODY_BYTES = 32768


def request(label, path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "GS25-readonly-rediagnostic/1.0",
    }, method="GET")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "").split(";")[0]
            body = response.read(MAX_BODY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        print(f"CHECK={label} HTTP={exc.code} RESULT=HTTP_ERROR "
              f"ELAPSED={time.monotonic()-start:.1f}s", flush=True)
        return
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"CHECK={label} RESULT=NETWORK_ERROR TYPE={type(exc).__name__} "
              f"ELAPSED={time.monotonic()-start:.1f}s", flush=True)
        return

    prefix = (f"CHECK={label} HTTP={status} CONTENT_TYPE={content_type} "
              f"ELAPSED={time.monotonic()-start:.1f}s")
    if len(body) > MAX_BODY_BYTES:
        print(prefix + " RESULT=BODY_TOO_LARGE", flush=True)
        return
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        print(prefix + " RESULT=NON_JSON", flush=True)
        return
    if isinstance(data, dict):
        # Report only types and top-level key names; never print values.
        keys = sorted(k for k in data if isinstance(k, str))[:12]
        print(prefix + " RESULT=JSON_OBJECT KEYS=" + ",".join(keys), flush=True)
        for key in ("stores", "items", "products", "data"):
            value = data.get(key)
            if isinstance(value, list):
                print(f"CHECK={label} FIELD={key} TYPE=list COUNT={len(value)}", flush=True)
            elif isinstance(value, dict):
                print(f"CHECK={label} FIELD={key} TYPE=dict", flush=True)
    elif isinstance(data, list):
        print(prefix + f" RESULT=JSON_LIST COUNT={len(data)}", flush=True)
    else:
        print(prefix + " RESULT=JSON_SCALAR", flush=True)


def main():
    print("GS25_READ_ONLY_REDIAGNOSTIC_START REQUESTS_MAX=3", flush=True)
    request("HEALTH", "/api/alive")
    for label, barcode in PRODUCTS:
        time.sleep(2)
        request(label, "/api/bff/v2/store/stock", {
            "serviceCode": "01", "itemCode": barcode,
            "myPositionXCoordination": LONGITUDE,
            "myPositionYCoordination": LATITUDE,
            "centerPositionXCoordination": LONGITUDE,
            "centerPositionYCoordination": LATITUDE,
            "radiusCondition": 500, "pickupStoreYn": "N",
            "realTimeStockYn": "Y", "pageNumber": 0, "pageCount": 100,
        })
    print("GS25_READ_ONLY_REDIAGNOSTIC_FINISHED", flush=True)


if __name__ == "__main__":
    main()
