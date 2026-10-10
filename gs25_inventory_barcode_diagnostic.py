import json
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://mcp.aka.page"
BARCODE = "8800286275732"
TIMEOUT = 35

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        value = data.strip()
        if value:
            self.parts.append(value)

def request(label, path, params):
    params = dict(params)
    params["format"] = "html"
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    print("\n" + "=" * 65, flush=True)
    print("TEST:", label, flush=True)
    print("PATH:", path, flush=True)
    print("PARAMS:", params, flush=True)

    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"},
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            body = resp.read(700000).decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        status = err.code
        body = err.read(700000).decode("utf-8", "replace")
    except Exception as err:
        print("NETWORK_ERROR:", type(err).__name__, str(err), flush=True)
        return

    print("HTTP:", status, flush=True)
    try:
        obj = json.loads(body)
        print("JSON_RESULT:", json.dumps(obj, ensure_ascii=False)[:7000], flush=True)
        return
    except (ValueError, TypeError):
        pass

    parser = TextParser()
    parser.feed(body)
    tokens = parser.parts

    for field in ("success", "code", "message", "itemCode",
                  "itemName", "stockCheckEnabled", "total",
                  "count", "stock", "quantity", "storeName"):
        matches = []
        for i, token in enumerate(tokens):
            if token == field:
                matches.append(" | ".join(tokens[i:i+5]))
        if matches:
            print("FIELD", field, ":", matches[:12], flush=True)

    barcode_hits = [
        " | ".join(tokens[max(0, i-5):i+10])
        for i, token in enumerate(tokens)
        if token == BARCODE
    ]
    print("EXACT_BARCODE_HITS:", len(barcode_hits), flush=True)
    for hit in barcode_hits[:10]:
        print("BARCODE_CONTEXT:", hit[:600], flush=True)

    print("RESPONSE_TAIL:", " | ".join(tokens[-100:])[:4000], flush=True)

def main():
    print("GS25 INVENTORY BARCODE DIAGNOSTIC", flush=True)
    print("READ ONLY / NO STATE / NO TELEGRAM", flush=True)
    tests = [
        ("product search by barcode", "/api/gs25/products",
         {"keyword": BARCODE, "limit": 100}),
        ("inventory by itemCode - Namwon", "/api/gs25/inventory",
         {"itemCode": BARCODE, "storeKeyword": "남원", "storeLimit": 20}),
        ("inventory by itemCode - Asan", "/api/gs25/inventory",
         {"itemCode": BARCODE, "storeKeyword": "아산", "storeLimit": 20}),
        ("inventory by barcode as keyword - Namwon", "/api/gs25/inventory",
         {"keyword": BARCODE, "storeKeyword": "남원", "storeLimit": 20}),
        ("inventory by card keyword - Namwon", "/api/gs25/inventory",
         {"keyword": "포켓몬카드", "storeKeyword": "남원", "storeLimit": 20}),
    ]
    for i, (label, path, params) in enumerate(tests):
        if i:
            time.sleep(3)
        request(label, path, params)
    print("\nDIAGNOSTIC FINISHED", flush=True)
    print("HTTP 200 alone does not confirm stock.", flush=True)
    print("Missing products do not prove zero stock.", flush=True)

if __name__ == "__main__":
    main()
