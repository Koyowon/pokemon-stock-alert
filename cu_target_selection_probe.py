"""CU target stock-selection diagnostic. Read-only, no notifications."""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://mcp.aka.page/api/cu/inventory"
TARGET = "8800286275732"

QUERIES = [
    "포켓몬)30주년기념카드",
    "포켓몬30주년기념카드",
    "포켓몬 30주년 기념카드",
    "30주년기념카드",
    "30주년기념",
    "포켓몬카드30주년",
    "포켓몬카드",
    "셀러브레이션",
    TARGET,
]

REGIONS = {
    "남원": ("전북특별자치도 남원시", "전라북도 남원시"),
    "아산": ("충청남도 아산시", "충남 아산시"),
}

class TokenParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens = []
        self.in_pre = False
        self.pre_parts = []
        self.json_blocks = []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.in_pre = True
            self.pre_parts = []

    def handle_endtag(self, tag):
        if tag == "pre" and self.in_pre:
            self.json_blocks.append("".join(self.pre_parts))
            self.in_pre = False

    def handle_data(self, data):
        value = data.strip()
        if value:
            self.tokens.append(value)
        if self.in_pre:
            self.pre_parts.append(data)

def value_after(tokens, field):
    for i, token in enumerate(tokens[:-1]):
        if token == field:
            return tokens[i + 1]
    return None

def parse_tokens(tokens):
    success = value_after(tokens, "success")
    if success != "true":
        raise RuntimeError("API success is not true")

    selected = value_after(tokens, "stockItemCode")
    selected_name = value_after(tokens, "stockItemName")
    reason = value_after(tokens, "selectionReason")
    total = value_after(tokens, "total")
    available = value_after(tokens, "available")

    products = []
    stores = []
    for i, token in enumerate(tokens):
        if token == "itemCode" and i + 1 < len(tokens):
            code = tokens[i + 1]
            name = ""
            for j in range(i + 2, min(i + 12, len(tokens) - 1)):
                if tokens[j] == "itemCode":
                    break
                if tokens[j] == "itemName":
                    name = tokens[j + 1]
                    break
            if re.fullmatch(r"\\d{8,14}", code):
                products.append({"itemCode": code, "itemName": name})

        if token == "storeCode" and i + 1 < len(tokens):
            row = {"storeCode": tokens[i + 1]}
            for j in range(i + 2, min(i + 28, len(tokens) - 1)):
                if tokens[j] == "storeCode":
                    break
                if tokens[j] in ("storeName", "address", "stock"):
                    row[tokens[j]] = tokens[j + 1]
            stores.append(row)

    return {
        "success": True,
        "total": total,
        "stockItemCode": selected,
        "stockItemName": selected_name,
        "selectionReason": reason,
        "available": available,
        "products": products,
        "stores": stores,
    }

def fetch(keyword, region, store_check):
    params = {
        "keyword": keyword,
        "storeKeyword": region,
        "size": 100,
        "offset": 0,
        "storeCheck": str(store_check).lower(),
        "format": "html",
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"User-Agent": "CU-Target-Selection-Probe/1.0"}
    )

    with urllib.request.urlopen(request, timeout=40) as response:
        status = response.status
        html = response.read(1500000).decode("utf-8", "replace")

    if status != 200:
        raise RuntimeError("HTTP " + str(status))

    parser = TokenParser()
    parser.feed(html)

    for block in parser.json_blocks:
        try:
            obj = json.loads(block)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and "success" in obj:
            if obj.get("success") is not True:
                raise RuntimeError("API success=false")
            data = obj.get("data")
            if isinstance(data, dict):
                return data

    return parse_tokens(parser.tokens)

def valid_city(address, region):
    address = re.sub(r"\\s+", " ", str(address)).strip()
    return any(address.startswith(prefix) for prefix in REGIONS[region])

def analyze(keyword, region):
    data = fetch(keyword, region, True)
    selected = data.get("stockItemCode")
    selected_name = data.get("stockItemName")
    reason = data.get("selectionReason")

    print("\n" + "=" * 65, flush=True)
    print("REGION:", region, flush=True)
    print("KEYWORD:", keyword, flush=True)
    print("SELECTED_CODE:", selected, flush=True)
    print("SELECTED_NAME:", selected_name, flush=True)
    print("SELECTION_REASON:", reason, flush=True)
    print("TARGET_SELECTED:", str(selected) == TARGET, flush=True)

    products = data.get("products") or []
    if isinstance(products, list):
        matches = [
            p for p in products
            if isinstance(p, dict)
            and str(p.get("itemCode")) == TARGET
        ]
        print("TARGET_IN_PRODUCTS:", bool(matches), flush=True)
        for product in matches:
            print("TARGET_PRODUCT:",
                  json.dumps(product, ensure_ascii=False)[:1500],
                  flush=True)

    nearby = data.get("nearbyStores")
    stores = []
    if isinstance(nearby, dict):
        stores = nearby.get("stores") or []
    if not stores:
        stores = data.get("stores") or []

    accepted = []
    rejected = []
    for store in stores:
        if not isinstance(store, dict):
            continue
        item = {
            "code": store.get("storeCode"),
            "name": store.get("storeName"),
            "address": store.get("address"),
            "stock": store.get("stock"),
        }
        if valid_city(item["address"], region):
            accepted.append(item)
        else:
            rejected.append(item)

    print("CITY_MATCHED_STORES:", len(accepted), flush=True)
    print("OUTSIDE_CITY_STORES:", len(rejected), flush=True)
    for item in accepted:
        print("MATCHED_STORE:",
              json.dumps(item, ensure_ascii=False), flush=True)
    for item in rejected:
        print("EXCLUDED_STORE:",
              json.dumps(item, ensure_ascii=False), flush=True)

    numeric = [
        s for s in accepted
        if type(s["stock"]) is int and s["stock"] >= 0
    ]
    verified = str(selected) == TARGET and bool(numeric)
    print("TARGET_NUMERIC_STOCK_VERIFIED:", verified, flush=True)

    if str(selected) != TARGET:
        print("WARNING: Store stock is NOT for the target product.",
              flush=True)
    elif not numeric:
        print("WARNING: Target selected, but no numeric city stock.",
              flush=True)

    return {
        "region": region,
        "keyword": keyword,
        "selected": selected,
        "target_selected": str(selected) == TARGET,
        "city_stores": len(accepted),
        "numeric_target_stores": len(numeric) if verified else 0,
    }

def main():
    print("CU TARGET SELECTION DIAGNOSTIC", flush=True)
    print("TARGET BARCODE:", TARGET, flush=True)
    print("READ ONLY / NO TELEGRAM / NO STATE WRITES", flush=True)

    results = []
    failures = 0
    for region in REGIONS:
        for keyword in QUERIES:
            try:
                results.append(analyze(keyword, region))
            except Exception as exc:
                failures += 1
                print("QUERY_ERROR:", region, keyword,
                      type(exc).__name__, str(exc)[:250],
                      flush=True)
            time.sleep(2)

    print("\n" + "=" * 65, flush=True)
    print("FINAL SUMMARY", flush=True)
    for item in results:
        print("SUMMARY:", json.dumps(item, ensure_ascii=False),
              flush=True)
    print("SUCCESSFUL_TESTS:", len(results), flush=True)
    print("FAILED_TESTS:", failures, flush=True)
    print("TARGET_SELECTION_FOUND:",
          any(x["target_selected"] for x in results), flush=True)
    print("NUMERIC_TARGET_STOCK_FOUND:",
          any(x["numeric_target_stores"] > 0 for x in results),
          flush=True)
    print("CU TARGET SELECTION DIAGNOSTIC FINISHED", flush=True)

    if not results:
        raise RuntimeError("All CU queries failed")

if __name__ == "__main__":
    main()
