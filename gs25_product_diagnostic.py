import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE_URL = "https://mcp.aka.page/api/gs25/products"

KEYWORDS = [
    "포켓몬30주년",
    "포켓몬확장팩",
    "포켓몬카드",
    "30주년",
    "포켓몬",
    "확장팩",
    "30th",
    "CELEBRATION",
    "30th CELEBRATION",
    "셀러브레이션",
    "메가 확장팩",
    "메가확장팩",
    "MEGA",
    "포켓몬 30주년",
    "포켓몬카드30주년",
    "포켓몬카드30th",
        "포켓몬카드)30",
]

LIMIT = 100
TIMEOUT = 25
DELAY = 3


class HTMLTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth and data.strip():
            self.parts.append(data.strip())


def request_products(keyword):
    params = urllib.parse.urlencode({
        "keyword": keyword,
        "limit": LIMIT,
        "format": "html",
    })

    url = BASE_URL + "?" + params

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=TIMEOUT
        ) as response:
            status = response.status
            body = response.read(500000).decode(
                "utf-8", "replace"
            )
            return status, body

    except urllib.error.HTTPError as error:
        body = error.read(500000).decode(
            "utf-8", "replace"
        )
        return error.code, body

    except Exception as error:
        return None, str(error)


def extract_html_tokens(body):
    parser = HTMLTextParser()
    parser.feed(body)
    return parser.parts


def parse_boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
    return None


def extract_json_products(body):
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None

    if not isinstance(data, dict):
        return None

    payload = data.get("data", data)
    if not isinstance(payload, dict):
        return None

    products = payload.get("products")
    if not isinstance(products, list):
        return None

    result = []

    for product in products:
        if not isinstance(product, dict):
            continue

        code = str(product.get("itemCode") or "").strip()
        name = str(product.get("itemName") or "").strip()

        if not code or not name:
            continue

        result.append({
            "itemCode": code,
            "itemName": name,
            "stockCheckEnabled": parse_boolean(
                product.get("stockCheckEnabled")
            ),
        })

    return result


def extract_html_products(body):
    tokens = extract_html_tokens(body)
    products = []
    current = None
    in_products = False

    for index, token in enumerate(tokens):
        if token == "products":
            in_products = True
            continue

        if not in_products:
            continue

        if token in ("meta", "개발자용 JSON 원본"):
            break

        if token == "itemCode":
            if current and current.get("itemCode"):
                if current.get("itemName"):
                    products.append(current)

            current = {
                "itemCode": "",
                "itemName": "",
                "stockCheckEnabled": None,
            }

            if index + 1 < len(tokens):
                value = tokens[index + 1].strip()
                if re.fullmatch(r"\d{8,14}", value):
                    current["itemCode"] = value

        elif current is not None and token == "itemName":
            if index + 1 < len(tokens):
                value = tokens[index + 1].strip()
                if value not in (
                    "shortItemName",
                    "imageUrl",
                    "rating",
                    "stockCheckEnabled",
                    "itemCode",
                ):
                    current["itemName"] = value

        elif (
            current is not None
            and token == "stockCheckEnabled"
        ):
            if index + 1 < len(tokens):
                current["stockCheckEnabled"] = (
                    parse_boolean(tokens[index + 1])
                )

    if current and current.get("itemCode"):
        if current.get("itemName"):
            products.append(current)

    return products


def extract_products(body):
    json_products = extract_json_products(body)

    if json_products is not None:
        return json_products, "JSON"

    return extract_html_products(body), "HTML"


def relevance_score(name):
    normalized = re.sub(
        r"\s+", "", name.lower()
    )

    score = 0

    if "포켓몬" in normalized:
        score += 2

    if "30주년" in normalized or "30th" in normalized:
        score += 4

    if "확장팩" in normalized:
        score += 5

    if "카드" in normalized:
        score += 2

    if "mega" in normalized or "메가" in normalized:
        score += 1

    if "교통카드" in normalized or "ic칩" in normalized:
        score -= 8

    if "이즐)" in normalized or "티머니" in normalized:
        score -= 8

    return score


def main():
    print("=" * 65)
    print("GS25 POKEMON 30TH PRODUCT DIAGNOSTIC")
    print("READ ONLY / NO ALERTS / NO STATE WRITES")
    print("=" * 65)

    unique_products = {}

    for index, keyword in enumerate(KEYWORDS):
        if index:
            time.sleep(DELAY)

        status, body = request_products(keyword)

        print("\n" + "-" * 65)
        print("KEYWORD:", keyword)
        print("HTTP:", status)

        if status != 200:
            print("REQUEST_FAILED")
            print("BODY_PREVIEW:", body[:500])
            continue

        products, response_format = extract_products(body)

        print("FORMAT:", response_format)
        print("EXTRACTED_COUNT:", len(products))

        if not products:
            print("NO_EXTRACTED_PRODUCTS")
            print("BODY_PREVIEW:", body[:1000])
            continue

        for product in products:
            code = product["itemCode"]
            name = product["itemName"]
            enabled = product["stockCheckEnabled"]

            unique_products[code] = product

            print(
                "PRODUCT:",
                code,
                "|",
                name,
                "| STOCK_CHECK:",
                enabled,
            )

    ranked = sorted(
        unique_products.values(),
        key=lambda product: relevance_score(
            product["itemName"]
        ),
        reverse=True,
    )

    print("\n" + "=" * 65)
    print("POKEMON CARD CANDIDATES")
    print("=" * 65)

    candidates = []

    for product in ranked:
        name = product["itemName"]
        score = relevance_score(name)

        if score >= 4:
            candidates.append(product)

            print("ITEM_CODE:", product["itemCode"])
            print("ITEM_NAME:", name)
            print(
                "STOCK_CHECK_ENABLED:",
                product["stockCheckEnabled"],
            )
            print("RELEVANCE_SCORE:", score)
            print("-" * 40)

    print("\nTOTAL UNIQUE PRODUCTS:", len(unique_products))
    print("CANDIDATE COUNT:", len(candidates))
    print("NOTE: Candidates are not confirmed card packs.")
    print("NOTE: HTTP 200 does not confirm store stock.")
    print("DIAGNOSTIC FINISHED")


if __name__ == "__main__":
    main()
