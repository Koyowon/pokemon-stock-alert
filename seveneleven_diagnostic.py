import json
import re
import time
import html
import urllib.request
import urllib.parse
import urllib.error
from html.parser import HTMLParser

BASE = "https://mcp.aka.page/api/seveneleven"
STORE = "신남삼성점"
EXPECTED_ADDRESS = "강원도 인제군 남면"
KEYWORDS = [
    "포켓몬확장팩(30주년)",
    "비전)포켓몬확장팩(30주년)_H",
    "30주년",
]
TIMEOUT = 20

class HTMLData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        value = data.strip()
        if value:
            self.parts.append(value)

def fetch(path, params):
    params = dict(params)
    params["format"] = "html"
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0",
                 "Accept": "text/html, application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return res.status, res.read(100000).decode(
                "utf-8", errors="replace"
            ), None
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4000).decode(
            "utf-8", errors="replace"
        ), "HTTP_ERROR"
    except Exception as exc:
        return None, "", str(exc)

def inspect(title, path, params):
    print("\n" + "=" * 65, flush=True)
    print("TEST:", title, flush=True)
    print("PARAMS:", json.dumps(params, ensure_ascii=False), flush=True)
    status, body, error = fetch(path, params)
    print("HTTP:", status, flush=True)
    if error:
        print("ERROR:", error, flush=True)
    print("BODY_LENGTH:", len(body), flush=True)

    try:
        data = json.loads(body)
        print("JSON:", json.dumps(
            data, ensure_ascii=False, indent=2
        )[:12000], flush=True)
    except (ValueError, TypeError):
        parser = HTMLData()
        parser.feed(body)
        text = "\n".join(parser.parts)
        print("HTML_TEXT:", text[:12000], flush=True)

        for label in (
            "product", "products", "id", "itemCode",
            "storeCode", "storeName", "stockAvailable",
            "stockQuantity", "stockError", "note",
            "totalStoreCount", "count",
        ):
            matches = [
                line for line in text.splitlines()
                if label.lower() in line.lower()
            ]
            if matches:
                print("FIELD", label, ":",
                      matches[:15], flush=True)

    if status != 200:
        print("WARNING: HTTP error is NOT zero stock.", flush=True)
    return status

def main():
    print("SEVEN ELEVEN 30TH REFERENCE STORE DIAGNOSTIC")
    print("STORE:", STORE)
    print("EXPECTED AREA:", EXPECTED_ADDRESS)
    print("READ ONLY: no state changes or alerts")
    print("REFERENCE ONLY: third-party site showed 20 units")
    print("20 is NOT an API-confirmed quantity")

    inspect(
        "REFERENCE STORE SEARCH",
        "/stores",
        {"keyword": STORE, "limit": "20"},
    )
    time.sleep(2)

    for keyword in KEYWORDS:
        inspect(
            "PRODUCT SEARCH: " + keyword,
            "/products",
            {"query": keyword, "size": "30"},
        )
        time.sleep(2)

        inspect(
            "INVENTORY: " + keyword,
            "/inventory",
            {
                "keyword": keyword,
                "storeKeyword": STORE,
                "storeLimit": "20",
            },
        )
        time.sleep(2)

    print("\n" + "=" * 65)
    print("DIAGNOSTIC FINISHED")
    print("Unknown stock must never be treated as zero.")
    print("Verify store name AND address before using quantity.")

if __name__ == "__main__":
    main()
