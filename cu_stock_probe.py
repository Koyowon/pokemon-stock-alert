"""Read-only CU stock probe. No state files or Telegram writes."""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://mcp.aka.page"
BARCODE = "8800286275732"
NAME = "포켓몬)30주년기념카드"
REGIONS = ("남원", "아산")

class Reader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens = []
        self.in_pre = False
        self.pre_text = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.in_pre = True
            self.pre_text = []

    def handle_endtag(self, tag):
        if tag == "pre" and self.in_pre:
            self.blocks.append("".join(self.pre_text))
            self.in_pre = False

    def handle_data(self, data):
        value = data.strip()
        if value:
            self.tokens.append(value)
        if self.in_pre:
            self.pre_text.append(data)

def fetch(path, params):
    params = dict(params, format="html")
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"User-Agent": "CUStockProbe/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            status = response.status
            body = response.read(1500000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read(1500000).decode("utf-8", "replace")

    print("HTTP:", status, flush=True)
    parser = Reader()
    parser.feed(body)

    data = None
    for block in parser.blocks:
        try:
            obj = json.loads(block)
            if isinstance(obj, dict) and "success" in obj:
                data = obj
                break
        except (ValueError, TypeError):
            pass

    if data is not None:
        print("API_SUCCESS:", data.get("success"), flush=True)
        if data.get("success") is not True:
            print("API_ERROR:", str(data)[:1500], flush=True)
        payload = data.get("data")
        if isinstance(payload, dict):
            for key in ("total", "page", "pageSize", "inventory"):
                if key in payload:
                    print("DATA_FIELD:", key,
                          json.dumps(payload[key], ensure_ascii=False)[:1500],
                          flush=True)
            for key in ("products", "stores"):
                rows = payload.get(key)
                if isinstance(rows, list):
                    print("DATA_COUNT:", key, len(rows), flush=True)
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        if key == "products":
                            code = str(row.get("itemCode", ""))
                            name = str(row.get("itemName", ""))
                            if code != BARCODE and "30주년" not in name:
                                continue
                            print("TARGET_PRODUCT:",
                                  json.dumps(row, ensure_ascii=False)[:4000],
                                  flush=True)
                        else:
                            print("STORE_ROW:",
                                  json.dumps(row, ensure_ascii=False)[:3000],
                                  flush=True)
        return status == 200 and data.get("success") is True

    tokens = parser.tokens
    print("HTML_TOKENS:", len(tokens), flush=True)
    for field in ("success", "total", "inventory", "available",
                  "unavailableReason", "storeCode", "storeName",
                  "itemCode", "itemName", "stock"):
        matches = [
            " | ".join(tokens[i:i + 12])
            for i, token in enumerate(tokens) if token == field
        ]
        print("FIELD:", field, "COUNT:", len(matches), flush=True)
        for item in matches[:12]:
            print("VALUE:", item[:750], flush=True)

    for needle in (BARCODE, NAME, "30주년"):
        matches = [
            " | ".join(tokens[max(0, i - 12):i + 35])
            for i, token in enumerate(tokens) if needle in token
        ]
        print("TARGET_TEXT:", needle, "COUNT:", len(matches), flush=True)
        for item in matches[:8]:
            print("CONTEXT:", item[:1800], flush=True)

    print("TAIL:", " | ".join(tokens[-65:])[:3000], flush=True)
    if status != 200:
        return False
    if "success" not in tokens:
        return False
    i = tokens.index("success")
    return i + 1 < len(tokens) and tokens[i + 1] == "true"

def run(label, path, params):
    print("\n" + "=" * 65, flush=True)
    print("TEST:", label, flush=True)
    print("PATH:", path, flush=True)
    print("PARAMS:", params, flush=True)
    try:
        ok = fetch(path, params)
        print("REQUEST_SUCCESS:", ok, flush=True)
        return ok
    except Exception as exc:
        print("REQUEST_ERROR:", type(exc).__name__,
              str(exc)[:500], flush=True)
        return False

def main():
    print("CU STOCK READ-ONLY PROBE", flush=True)
    print("TARGET:", NAME, BARCODE, flush=True)
    print("NO STATE WRITES. NO TELEGRAM.", flush=True)
    results = {}

    for region in REGIONS:
        results[region] = {}
        tests = [
            ("stores", "/api/cu/stores",
             {"keyword": region, "limit": 100}),
            ("exact_name", "/api/cu/inventory",
             {"keyword": "30주년기념카드",
              "storeKeyword": region, "size": 100,
              "offset": 0, "storeCheck": "true"}),
            ("pokemon_cards_page1", "/api/cu/inventory",
             {"keyword": "포켓몬카드",
              "storeKeyword": region, "size": 100,
              "offset": 0, "storeCheck": "true"}),
            ("barcode", "/api/cu/inventory",
             {"keyword": BARCODE,
              "storeKeyword": region, "size": 100,
              "offset": 0, "storeCheck": "true"}),
        ]
        for label, path, params in tests:
            results[region][label] = run(
                region + " / " + label, path, params
            )
            time.sleep(2)

    print("\nFINAL_REQUEST_STATUS:",
          json.dumps(results, ensure_ascii=False), flush=True)
    print("IMPORTANT: stock=null is UNKNOWN, not zero.", flush=True)
    print("IMPORTANT: unrelated product stock is not target stock.",
          flush=True)
    print("IMPORTANT: store list may be incomplete.", flush=True)
    print("CU STOCK PROBE FINISHED", flush=True)

if __name__ == "__main__":
    main()
