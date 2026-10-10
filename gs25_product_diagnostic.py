import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://mcp.aka.page/api/gs25/products"
KEYWORDS = [
    "포켓몬30주년",
    "포켓몬확장팩",
    "포켓몬카드",
    "30주년",
    "포켓몬",
]
LIMIT = 100
TIMEOUT = 25
DELAY = 3

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())

def parse_response(raw):
    try:
        return json.loads(raw)
    except ValueError:
        parser = TextParser()
        parser.feed(raw)
        text = "\n".join(parser.parts)
        # HTML 응답은 표시용 텍스트이므로 원문을 보존한다.
        return {"html_text": text}

def search(keyword):
    params = urllib.parse.urlencode({
        "keyword": keyword,
        "limit": LIMIT,
        "format": "html",
    })
    url = BASE + "?" + params
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=TIMEOUT
        ) as response:
            return response.status, parse_response(
                response.read(200000).decode("utf-8", "replace")
            )
    except urllib.error.HTTPError as exc:
        return exc.code, parse_response(
            exc.read(200000).decode("utf-8", "replace")
        )
    except Exception as exc:
        return None, {"error": str(exc)}

def extract_products(data):
    if not isinstance(data, dict):
        return []
    payload = data.get("data", data)
    if isinstance(payload, dict):
        products = payload.get("products", [])
        if isinstance(products, list):
            return products
    return []

def score(name):
    value = re.sub(r"\s+", "", name.lower())
    points = 0
    if "포켓몬" in value:
        points += 2
    if "30주년" in value or "30th" in value:
        points += 4
    if "확장팩" in value:
        points += 4
    if "카드" in value:
        points += 2
    if "mega" in value or "메가" in value:
        points += 1
    return points

def main():
    print("GS25 PRODUCT DIAGNOSTIC", flush=True)
    print("READ ONLY / NO STATE CHANGES", flush=True)

    found = {}

    for index, keyword in enumerate(KEYWORDS):
        if index:
            time.sleep(DELAY)

        status, data = search(keyword)
        print("\n" + "=" * 60, flush=True)
        print("KEYWORD:", keyword, flush=True)
        print("HTTP:", status, flush=True)

        products = extract_products(data)

        if products:
            print("RETURNED:", len(products), flush=True)
            for product in products:
                if not isinstance(product, dict):
                    continue
                name = str(product.get("itemName", ""))
                item_code = str(product.get("itemCode", ""))
                if item_code:
                    found[item_code] = {
                        "name": name,
                        "code": item_code,
                        "stockCheckEnabled": product.get(
                            "stockCheckEnabled"
                        ),
                    }
                print(
                    "PRODUCT:",
                    item_code,
                    "|",
                    name,
                    flush=True,
                )
        else:
            # format=html 결과의 전체 텍스트를 기록해
            # 상품명과 itemCode를 수동으로 확인할 수 있게 한다.
            print(
                "RESPONSE:",
                json.dumps(data, ensure_ascii=False)[:18000],
                flush=True,
            )

    ranked = sorted(
        found.values(),
        key=lambda item: score(item["name"]),
        reverse=True,
    )

    print("\n" + "=" * 60, flush=True)
    print("POSSIBLE MATCHES", flush=True)
    for item in ranked:
        if score(item["name"]) >= 4:
            print(
                "ITEM_CODE:", item["code"],
                "| NAME:", item["name"],
                "| STOCK_CHECK:", item["stockCheckEnabled"],
                flush=True,
            )

    print("TOTAL UNIQUE PRODUCTS:", len(found), flush=True)
    print("DIAGNOSTIC FINISHED", flush=True)

if __name__ == "__main__":
    main()
