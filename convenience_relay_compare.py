import json
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://mcp.aka.page"
TIMEOUT = 20
DELAY = 3

TESTS = [
    ("CU", "/api/cu/products", {"query": "포켓몬"}),
    ("GS25", "/api/gs25/products", {"query": "포켓몬"}),
    ("SEVEN_ELEVEN", "/api/seveneleven/products", {"query": "포켓몬"}),
]

class VisibleText(HTMLParser):
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

def run_test(name, path, params):
    params = dict(params)
    params["format"] = "html"
    url = BASE + path + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html, application/json",
        },
        method="GET",
    )

    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            status = response.status
            body = response.read(30000).decode("utf-8", "replace")
            error = None
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read(30000).decode("utf-8", "replace")
        error = "HTTP_ERROR"
    except Exception as exc:
        status = None
        body = ""
        error = type(exc).__name__ + ": " + str(exc)

    elapsed = round(time.monotonic() - started, 2)

    try:
        obj = json.loads(body)
        output = json.dumps(obj, ensure_ascii=False, indent=2)
    except (ValueError, TypeError):
        parser = VisibleText()
        parser.feed(body)
        output = "\n".join(parser.parts)

    print("\n" + "=" * 60, flush=True)
    print("CHAIN:", name, flush=True)
    print("PATH:", path, flush=True)
    print("HTTP:", status, flush=True)
    print("SECONDS:", elapsed, flush=True)
    if error:
        print("ERROR:", error, flush=True)
    print("RESPONSE:", output[:3500], flush=True)

    if "CONVENIENCE_RELAY_FAILED" in output:
        print("RELAY_ERROR: YES", flush=True)
    else:
        print("RELAY_ERROR: NOT_DETECTED", flush=True)

    if status == 200:
        result = "HTTP_SUCCESS"
    elif status == 502:
        result = "RELAY_OR_UPSTREAM_FAILURE"
    else:
        result = "OTHER_OR_UNKNOWN"

    print("CLASSIFICATION:", result, flush=True)
    return status, result

def main():
    print("CONVENIENCE RELAY COMPARISON", flush=True)
    print("READ ONLY - NO STATE CHANGES", flush=True)
    print("NO ALERTS - NO PURCHASES", flush=True)

    results = []
    for index, (name, path, params) in enumerate(TESTS):
        if index:
            time.sleep(DELAY)
        status, result = run_test(name, path, params)
        results.append((name, status, result))

    print("\n" + "=" * 60, flush=True)
    print("COMPARISON SUMMARY", flush=True)
    for name, status, result in results:
        print(name + ": HTTP " + str(status) + " / " + result, flush=True)

    print("HTTP 200 means request succeeded, not stock confirmed.")
    print("HTTP 502 does not mean sold out.")
    print("DIAGNOSTIC FINISHED")

if __name__ == "__main__":
    main()
