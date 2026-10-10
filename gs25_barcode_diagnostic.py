import json
import urllib.parse
import urllib.request
import urllib.error
from html.parser import HTMLParser

BARCODE = "8800286275732"
BASE = "https://mcp.aka.page/api/gs25/products"

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        if data.strip():
            self.parts.append(data.strip())

def inspect(label, params):
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    print("\n=== " + label + " ===")
    print("PARAMS:", params)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read(500000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read(2000).decode("utf-8", "replace")
    except Exception as e:
        print("ERROR:", type(e).__name__, str(e))
        return
    print("HTTP:", status)
    parser = TextParser()
    parser.feed(body)
    parts = parser.parts
    matches = []
    for i, part in enumerate(parts):
        if BARCODE in part:
            matches.append(" | ".join(parts[max(0, i-3):i+8]))
    print("BARCODE_MATCHES:", len(matches))
    for match in matches[:8]:
        print("MATCH:", match[:500])
    if not matches:
        print("RESPONSE_PREVIEW:", " | ".join(parts[:35])[:1000])
    try:
        obj = json.loads(body)
        print("JSON_SUCCESS:", obj.get("success"))
        print("JSON_DATA_KEYS:", list(obj.get("data", {}).keys()) if isinstance(obj.get("data"), dict) else None)
    except (ValueError, TypeError):
        pass

def main():
    print("GS25 BARCODE READ-ONLY DIAGNOSTIC")
    print("BARCODE:", BARCODE)
    tests = [
        ("keyword barcode", {"keyword": BARCODE, "limit": 100, "format": "html"}),
        ("itemCode parameter", {"itemCode": BARCODE, "limit": 100, "format": "html"}),
        ("barcode parameter", {"barcode": BARCODE, "limit": 100, "format": "html"}),
        ("productCode parameter", {"productCode": BARCODE, "limit": 100, "format": "html"}),
        ("keyword card reference", {"keyword": "포켓몬카드", "limit": 100, "format": "html"}),
    ]
    for label, params in tests:
        inspect(label, params)
    print("\nBARCODE DIAGNOSTIC FINISHED")
    print("NOTE: A product match is not proof of store inventory.")

if __name__ == "__main__":
    main()
