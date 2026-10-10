
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://mcp.aka.page"
TIMEOUT = 20
DELAY = 3

# OpenAPI 명세에 확인된 경로와 파라미터
TESTS = [
    (
        "CU",
        "/api/cu/inventory",
        {"keyword": "포켓몬", "storeCheck": "false", "size": 5},
    ),
    (
        "GS25",
        "/api/gs25/products",
        {"keyword": "포켓몬", "limit": 5},
    ),
    (
        "SEVEN_ELEVEN",
        "/api/seveneleven/products",
        {"query": "포켓몬", "size": 5},
    ),
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
    status = None
    body = ""
    network_error = None

    try:
        with urllib.request.urlopen(
            request, timeout=TIMEOUT
        ) as response:
            status = response.status
            body = response.read(30000).decode(
                "utf-8", "replace"
            )

    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read(30000).decode(
            "utf-8", "replace"
        )

    except Exception as exc:
        network_error = (
            type(exc).__name__ + ": " + str(exc)
        )

    elapsed = round(time.monotonic() - started, 2)

    try:
        data = json.loads(body)
        output = json.dumps(
            data, ensure_ascii=False, indent=2
        )
    except (ValueError, TypeError):
        parser = VisibleText()
        parser.feed(body)
        output = "\n".join(parser.parts)

    relay_failed = "CONVENIENCE_RELAY_FAILED" in output

    if relay_failed:
        result = "RELAY_FAILURE"
    elif status == 200 and "조회 실패" not in output:
        result = "HTTP_SUCCESS_CHECK_BODY"
    elif status == 400:
        result = "BAD_REQUEST"
    elif status == 404:
        result = "NOT_FOUND"
    elif status == 502:
        result = "UPSTREAM_FAILURE"
    else:
        result = "OTHER_OR_UNKNOWN"

    print("\n" + "=" * 60, flush=True)
    print("CHAIN:", name, flush=True)
    print("PATH:", path, flush=True)
    print("PARAMS:", params, flush=True)
    print("HTTP:", status, flush=True)
    print("SECONDS:", elapsed, flush=True)

    if network_error:
        print("NETWORK_ERROR:", network_error, flush=True)

    print("RELAY_ERROR:", relay_failed, flush=True)
    print("CLASSIFICATION:", result, flush=True)
    print("RESPONSE:", output[:3500], flush=True)

    return name, status, result


def main():
    print("CONVENIENCE RELAY COMPARISON V2")
    print("READ ONLY / NO ALERTS / NO STATE WRITES")

    results = []

    for index, (name, path, params) in enumerate(TESTS):
        if index:
            time.sleep(DELAY)

        results.append(run_test(name, path, params))

    print("\n" + "=" * 60)
    print("COMPARISON SUMMARY")

    for name, status, result in results:
        print(
            f"{name}: HTTP {status} / {result}",
            flush=True,
        )

    print("HTTP 200 does not confirm stock.")
    print("HTTP 502 does not mean sold out.")
    print("DIAGNOSTIC FINISHED")


if __name__ == "__main__":
    main()
