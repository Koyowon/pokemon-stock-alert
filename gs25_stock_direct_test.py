"""GS25 barcode-direct inventory diagnostic. Read-only; no credentials required."""
import json
import urllib.error
import urllib.parse
import urllib.request

API = "https://b2c-bff.woodongs.com/api/bff/v2/store/stock"
PRODUCTS = {
    "인페르노X (비교용)": "8800286278535",
    "30주년 카드팩 (목표)": "8800286275732",
}
# City-center coordinates for testing, not the user's personal location.
LOCATIONS = {
    "남원 중심": (35.4164, 127.3904),
    "아산 중심": (36.7898, 127.0018),
}

def test(label, barcode, place, lat, lng):
    params = {
        "serviceCode": "01",
        "itemCode": barcode,
        "myPositionXCoordination": lng,
        "myPositionYCoordination": lat,
        "centerPositionXCoordination": lng,
        "centerPositionYCoordination": lat,
        "radiusCondition": 500,
        "pickupStoreYn": "N",
        "realTimeStockYn": "Y",
        "pageNumber": 0,
        "pageCount": 100,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    print(f"\n=== {label} | {place} | {barcode} ===", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            status = response.status
            raw = response.read(200_000)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}; endpoint rejected request (not evidence of zero stock)")
        return
    except Exception as exc:
        print(f"REQUEST_ERROR {type(exc).__name__}: {exc}")
        return
    print(f"HTTP {status}")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        print("NON_JSON_RESPONSE (not evidence of zero stock)")
        print(raw[:350].decode("utf-8", errors="replace"))
        return
    if isinstance(obj, dict):
        print("TOP_LEVEL_KEYS:", list(obj)[:15])
        stores = obj.get("stores")
        if not isinstance(stores, list):
            # Shape may have changed or response may contain an error.
            print("NO_STORES_ARRAY:", json.dumps(obj, ensure_ascii=False)[:900])
            return
        print("STORE_COUNT:", len(stores))
        for store in stores[:15]:
            if not isinstance(store, dict):
                continue
            print(json.dumps({
                "storeCode": store.get("storeCode"),
                "storeName": store.get("storeName"),
                "realStockQuantity": store.get("realStockQuantity"),
            }, ensure_ascii=False))
        if not stores:
            print("EMPTY_RESULT: no stores returned; NOT proof of sold-out or unregistered product")
    else:
        print("UNEXPECTED_JSON:", json.dumps(obj, ensure_ascii=False)[:900])

if __name__ == "__main__":
    for label, barcode in PRODUCTS.items():
        for place, (lat, lng) in LOCATIONS.items():
            test(label, barcode, place, lat, lng)
