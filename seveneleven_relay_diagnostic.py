import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://mcp.aka.page"
STORE = "신남삼성점"
PRODUCT = "포켓몬확장팩(30주년)"
TIMEOUT = 20

class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())

def check(name, path, params=None):
    params = dict(params or {})
    if path.startswith("/api/"):
        params["format"] = "html"

    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    print("\n" + "=" * 60, flush=True)
    print("TEST:", name, flush=True)
    print("PATH:", path, flush=True)
    print("PARAMS:", json.dumps(params, ensure_ascii=False), flush=True)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html, application/json",
        },
        method="GET",
    )

    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            body = response.read(30000).decode(
                "utf-8", errors="replace"
            )
            error = None
    except urllib.error.HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
        body = exc.read(30000).decode(
            "utf-8", errors="replace"
        )
        error = "HTTP_ERROR"
    except Exception as exc:
        status = None
        content_type = ""
        body = ""
        error = type(exc).__name__ + ": " + str(exc)

    elapsed = round(time.monotonic() - start, 2)

    print("HTTP:", status, flush=True)
    print("SECONDS:", elapsed, flush=True)
    print("CONTENT_TYPE:", content_type, flush=True)
    print("BODY_LENGTH:", len(body), flush=True)
    if error:
        print("ERROR:", error, flush=True)

    try:
        obj = json.loads(body)
        output = json.dumps(obj, ensure_ascii=False, indent=2)
    except (ValueError, TypeError):
        parser = PageText()
        parser.feed(body)
        output = "\n".join(parser.parts)

    print("RESPONSE:", output[:5000], flush=True)

    for field in (
        "CONVENIENCE_RELAY_FAILED",
        "upstreamStatus",
        "retryable",
        "stockAvailable",
        "stockQuantity",
        "totalStoreCount",
    ):
        if field.lower() in output.lower():
            print("FOUND_FIELD:", field, flush=True)

    if status == 502:
        print("CLASSIFICATION: RELAY_OR_UPSTREAM_ERROR", flush=True)
    elif status == 200:
        print("CLASSIFICATION: HTTP_SUCCESS_CHECK_DATA", flush=True)
    else:
        print("CLASSIFICATION: UNVERIFIED", flush=True)

    return status

def main():
    print("SEVEN ELEVEN RELAY DIAGNOSTIC", flush=True)
    print("READ ONLY - NO STATE OR ALERT CHANGES", flush=True)
    print("TARGET: mcp.aka.page only", flush=True)

    tests = [
        ("BASE SERVICE", "/", {}),
        ("PRODUCT MINIMAL", "/api/seveneleven/products",
         {"query": PRODUCT}),
        ("PRODUCT WITH SIZE", "/api/seveneleven/products",
         {"query": PRODUCT, "size": "30"}),
        ("STORE LOOKUP", "/api/seveneleven/stores",
         {"keyword": STORE, "limit": "20"}),
        ("INVENTORY LOOKUP", "/api/seveneleven/inventory",
         {"keyword": PRODUCT, "storeKeyword": STORE,
          "storeLimit": "20"}),
    ]

    results = []
    for index, (name, path, params) in enumerate(tests):
        if index:
            time.sleep(3)
        status = check(name, path, params)
        results.append((name, status))

    print("\n" + "=" * 60, flush=True)
    print("SUMMARY", flush=True)
    for name, status in results:
        print(name + ": HTTP " + str(status), flush=True)
    print("HTTP 200 does not confirm inventory.", flush=True)
    print("HTTP 502 does not mean sold out.", flush=True)
    print("DIAGNOSTIC FINISHED", flush=True)

if __name__ == "__main__":
    main()
