import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://mcp.aka.page"
BARCODE = "8800286275732"
TIMEOUT = 40

class HTMLTokens(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens = []

    def handle_data(self, data):
        value = data.strip()
        if value:
            self.tokens.append(value)

def inspect(label, path, params):
    params = dict(params)
    params["format"] = "html"
    url = BASE + path + "?" + urllib.parse.urlencode(params)

    print("\n" + "=" * 65, flush=True)
    print("TEST:", label, flush=True)
    print("PATH:", path, flush=True)
    print("PARAMS:", params, flush=True)

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            status = response.status
            body = response.read(900000).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read(900000).decode("utf-8", "replace")
    except Exception as error:
        print("NETWORK_ERROR:", type(error).__name__, str(error), flush=True)
        return

    print("HTTP:", status, flush=True)

    try:
        obj = json.loads(body)
        print("JSON:", json.dumps(obj, ensure_ascii=False)[:11000], flush=True)
        return
    except (ValueError, TypeError):
        pass

    parser = HTMLTokens()
    parser.feed(body)
    tokens = parser.tokens

    for key in (
        "success", "code", "message", "keyword", "count",
        "total", "products", "stores", "storeName",
        "itemCode", "itemName", "productName", "stock",
        "stockQty", "quantity", "inventory",
    ):
        values = [
            " | ".join(tokens[i:i+7])
            for i, token in enumerate(tokens)
            if token == key
        ]
        if values:
            print("FIELD", key, ":", values[:15], flush=True)

    for needle in (BARCODE, "포켓몬", "30주년", "남원", "아산"):
        hits = [
            " | ".join(tokens[max(0, i-4):i+12])
            for i, token in enumerate(tokens)
            if needle in token
        ]
        print("TEXT_HITS", needle, ":", len(hits), flush=True)
        for hit in hits[:12]:
            print("HIT:", hit[:600], flush=True)

    error_codes = sorted(set(
        re.findall(r"[A-Z][A-Z0-9_]{5,}", " ".join(tokens))
    ))
    print("ERROR_CODE_CANDIDATES:", error_codes[:20], flush=True)
    print("RESPONSE_PREVIEW:", " | ".join(tokens[:100])[:4500], flush=True)
    print("RESPONSE_TAIL:", " | ".join(tokens[-80:])[:3000], flush=True)

def main():
    print("CU BARCODE / NAMWON / ASAN DIAGNOSTIC", flush=True)
    print("READ ONLY: NO TELEGRAM, NO STATE WRITES", flush=True)
    print("BARCODE:", BARCODE, flush=True)

    tests = [
        (
            "CU stores - Namwon",
            "/api/cu/stores",
            {"keyword": "남원", "limit": 100},
        ),
        (
            "CU stores - Asan",
            "/api/cu/stores",
            {"keyword": "아산", "limit": 100},
        ),
        (
            "CU barcode product search only",
            "/api/cu/inventory",
            {"keyword": BARCODE, "size": 100, "offset": 0,
             "storeCheck": "false"},
        ),
        (
            "CU Pokemon card product search only",
            "/api/cu/inventory",
            {"keyword": "포켓몬카드", "size": 100,
             "storeCheck": "false"},
        ),
        (
            "CU 30th product search only",
            "/api/cu/inventory",
            {"keyword": "포켓몬30주년", "size": 100,
             "storeCheck": "false"},
        ),
        (
            "CU barcode inventory - Namwon",
            "/api/cu/inventory",
            {"keyword": BARCODE, "storeKeyword": "남원",
             "size": 50, "storeCheck": "true"},
        ),
        (
            "CU barcode inventory - Asan",
            "/api/cu/inventory",
            {"keyword": BARCODE, "storeKeyword": "아산",
             "size": 50, "storeCheck": "true"},
        ),
        (
            "CU Pokemon card inventory - Namwon",
            "/api/cu/inventory",
            {"keyword": "포켓몬카드", "storeKeyword": "남원",
             "size": 50, "storeCheck": "true"},
        ),
        (
            "CU Pokemon card inventory - Asan",
            "/api/cu/inventory",
            {"keyword": "포켓몬카드", "storeKeyword": "아산",
             "size": 50, "storeCheck": "true"},
        ),
    ]

    for index, (label, path, params) in enumerate(tests):
        if index:
            time.sleep(3)
        inspect(label, path, params)

    print("\nCU DIAGNOSTIC FINISHED", flush=True)
    print("HTTP 200 is not proof of stock.", flush=True)
    print("An empty search is not proof of zero store inventory.", flush=True)
    print("A barcode in the request echo is not a product match.", flush=True)

if __name__ == "__main__":
    main()
