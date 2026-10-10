"""CU city stock diagnostic. READ ONLY. Standard library only."""
import json
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://mcp.aka.page"
BARCODE = "8800286275732"
PRODUCT = "포켓몬)30주년기념카드"

# Approximate city-center coordinates, NOT individual store coordinates.
CENTERS = {
    "남원": (35.416, 127.390),
    "아산": (36.790, 127.000),
}

PREFIXES = {
    "남원": ("전라북도 남원시", "전북특별자치도 남원시",
             "전북 남원시"),
    "아산": ("충청남도 아산시", "충남 아산시"),
}

# Search keywords are probes, not assertions of store existence.
STORE_SEARCHES = {
    "남원": ["남원", "남원시", "도통", "향교"],
    "아산": ["아산", "아산시", "온양", "배방", "탕정", "모종"],
}

class Tokens(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []

    def handle_data(self, data):
        value = data.strip()
        if value:
            self.values.append(value)

def get(path, params):
    params = dict(params)
    params["format"] = "html"
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"User-Agent": "CUCityStockDiagnostic/1.0"}
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        if response.status != 200:
            raise RuntimeError("HTTP " + str(response.status))
        html = response.read(1500000).decode("utf-8", "replace")

    parser = Tokens()
    parser.feed(html)
    tokens = parser.values

    if "success" not in tokens:
        raise RuntimeError("Missing API success field")
    index = tokens.index("success")
    if index + 1 >= len(tokens) or tokens[index + 1] != "true":
        raise RuntimeError("API success is not true")
    return tokens

def first(tokens, field):
    try:
        i = tokens.index(field)
        return tokens[i + 1] if i + 1 < len(tokens) else None
    except ValueError:
        return None

def normalize_stock(value):
    """Return int for nonnegative whole quantities; otherwise None."""
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str):
        clean = value.strip()
        if re.fullmatch(r"[0-9]+", clean):
            return int(clean)
    return None

def city_match(address, city):
    address = re.sub(r"\\s+", " ", str(address or "")).strip()
    return any(address.startswith(prefix) for prefix in PREFIXES[city])

def rows(tokens, kind):
    start_key = "storeCode"
    result = []
    for i, token in enumerate(tokens):
        if token != start_key or i + 1 >= len(tokens):
            continue
        row = {"storeCode": tokens[i + 1]}
        end = min(i + 35, len(tokens))
        for j in range(i + 2, end - 1):
            if tokens[j] == start_key:
                break
            if tokens[j] in ("storeName", "address", "stock",
                             "distanceM", "latitude", "longitude"):
                row[tokens[j]] = tokens[j + 1]
        if row.get("storeName") or row.get("address"):
            result.append(row)
    return result

def show_stores(city, label, stores, selected=None):
    valid = []
    excluded = []
    for row in stores:
        entry = {
            "code": row.get("storeCode"),
            "name": row.get("storeName"),
            "address": row.get("address"),
            "raw_stock": row.get("stock"),
            "stock": normalize_stock(row.get("stock")),
        }
        if city_match(entry["address"], city):
            valid.append(entry)
        else:
            excluded.append(entry)

    print("VALID_CITY_STORES:", len(valid), flush=True)
    print("EXCLUDED_STORES:", len(excluded), flush=True)

    for entry in valid:
        print("VALID_STORE:",
              json.dumps(entry, ensure_ascii=False), flush=True)
    for entry in excluded:
        print("EXCLUDED_STORE:",
              json.dumps(entry, ensure_ascii=False), flush=True)

    if selected is not None:
        if selected != BARCODE:
            print("TARGET_STOCK_STATUS: WRONG_PRODUCT", flush=True)
        else:
            numeric = [s for s in valid if s["stock"] is not None]
            print("TARGET_NUMERIC_STORES:", len(numeric), flush=True)
            print("TARGET_POSITIVE_STORES:",
                  sum(s["stock"] > 0 for s in numeric), flush=True)
            if numeric:
                print("TARGET_STOCK_STATUS: VERIFIED_NUMERIC", flush=True)
            else:
                print("TARGET_STOCK_STATUS: UNKNOWN", flush=True)
    return valid

def store_search(city, keyword, coordinates):
    params = {"keyword": keyword, "limit": 100}
    if coordinates:
        params["lat"], params["lng"] = CENTERS[city]

    label = "COORDINATES" if coordinates else "KEYWORD_ONLY"
    print("\nSTORE_SEARCH:", city, keyword, label, flush=True)
    tokens = get("/api/cu/stores", params)
    print("STORE_TOTAL:", first(tokens, "total"), flush=True)
    show_stores(city, label, rows(tokens, "stores"))

def inventory_search(city, label, store_keyword, coordinates):
    params = {
        "keyword": PRODUCT,
        "size": 100,
        "offset": 0,
        "storeCheck": "true",
    }
    if store_keyword is not None:
        params["storeKeyword"] = store_keyword
    if coordinates:
        params["lat"], params["lng"] = CENTERS[city]

    print("\nINVENTORY_TEST:", city, label, flush=True)
    print("PARAMS:", json.dumps(params, ensure_ascii=False), flush=True)
    tokens = get("/api/cu/inventory", params)

    selected = first(tokens, "stockItemCode")
    selected_name = first(tokens, "stockItemName")
    reason = first(tokens, "selectionReason")
    print("SELECTED_CODE:", selected, flush=True)
    print("SELECTED_NAME:", selected_name, flush=True)
    print("SELECTION_REASON:", reason, flush=True)
    print("TARGET_SELECTED:", selected == BARCODE, flush=True)
    print("INVENTORY_AVAILABLE:", first(tokens, "available"),
          flush=True)
    print("NEARBY_TOTAL:", first(tokens, "totalCount"), flush=True)

    return show_stores(city, label, rows(tokens, "inventory"),
                       selected=selected)

def safe_run(func, *args):
    try:
        func(*args)
        return True
    except Exception as exc:
        print("REQUEST_ERROR:", type(exc).__name__,
              str(exc)[:300], flush=True)
        return False

def main():
    print("CU CITY STOCK DIAGNOSTIC", flush=True)
    print("TARGET:", PRODUCT, BARCODE, flush=True)
    print("READ ONLY: NO TELEGRAM, NO FILE WRITES", flush=True)
    print("Coordinates are approximate city centers.", flush=True)

    passed = 0
    failed = 0

    for city in CENTERS:
        print("\n" + "=" * 65, flush=True)
        print("CITY:", city, flush=True)

        for keyword in STORE_SEARCHES[city]:
            ok = safe_run(store_search, city, keyword, False)
            passed += int(ok)
            failed += int(not ok)
            time.sleep(2)

        ok = safe_run(store_search, city, city, True)
        passed += int(ok)
        failed += int(not ok)
        time.sleep(2)

        cases = [
            ("CITY_KEYWORD_ONLY", city, False),
            ("CITY_COORDINATES_ONLY", None, True),
            ("CITY_KEYWORD_AND_COORDINATES", city, True),
        ]
        for label, keyword, use_coords in cases:
            ok = safe_run(inventory_search, city, label,
                          keyword, use_coords)
            passed += int(ok)
            failed += int(not ok)
            time.sleep(2)

        # Neighborhood probes: determine whether the relay returns
        # stores located in the requested city.
        neighborhoods = (["도통", "향교"] if city == "남원"
                         else ["온양", "배방", "탕정", "모종"])
        for neighborhood in neighborhoods:
            ok = safe_run(inventory_search, city,
                          "NEIGHBORHOOD_" + neighborhood,
                          neighborhood, True)
            passed += int(ok)
            failed += int(not ok)
            time.sleep(2)

    print("\nSUCCESSFUL_REQUESTS:", passed, flush=True)
    print("FAILED_REQUESTS:", failed, flush=True)
    print("CU CITY STOCK DIAGNOSTIC FINISHED", flush=True)

    if passed == 0:
        raise RuntimeError("All CU requests failed")

if __name__ == "__main__":
    main()
