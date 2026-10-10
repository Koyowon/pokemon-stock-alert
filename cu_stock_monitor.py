"""CU Pokemon 30th stock monitor, independent from other monitors."""
import json
import os
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://mcp.aka.page/api/cu/inventory"
BARCODE = "8800286275732"
PRODUCT = "포켓몬)30주년기념카드"
STATE_FILE = Path(__file__).with_name("cu_stock_state.json")

# Approximate search points, not exact store coordinates.
POINTS = {
    "남원": [
        (35.416, 127.390),
        (35.405, 127.380),
        (35.428, 127.402),
        (35.352, 127.370),
    ],
    "아산": [
        (36.790, 127.000),
        (36.775, 127.050),
        (36.795, 127.065),
        (36.805, 127.095),
        (36.798, 127.115),
        (36.830, 127.070),
        (36.920, 127.065),
    ],
}

PREFIXES = {
    "남원": ("전라북도 남원시", "전북특별자치도 남원시",
             "전북 남원시"),
    "아산": ("충청남도 아산시", "충남 아산시"),
}

class HTMLTokens(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens = []

    def handle_data(self, data):
        value = data.strip()
        if value:
            self.tokens.append(value)

def field(tokens, key):
    try:
        i = tokens.index(key)
        return tokens[i + 1] if i + 1 < len(tokens) else None
    except ValueError:
        return None

def stock_number(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        return int(value.strip())
    return None

def valid_address(address, city):
    address = re.sub(r"\s+", " ", str(address or "")).strip()
    return any(address.startswith(x) for x in PREFIXES[city])

def extract_stores(tokens):
    starts = [i for i, x in enumerate(tokens) if x == "storeCode"]
    result = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(tokens)
        block = tokens[start:end]
        if len(block) < 2:
            continue
        code = block[1].strip()
        if not re.fullmatch(r"[0-9]+", code):
            continue
        item = {"code": code}
        for key in ("storeName", "address", "stock"):
            item[key] = field(block, key)
        if item["storeName"] and item["address"]:
            result.append(item)
    return result

def query(city, lat, lng):
    params = {
        "keyword": PRODUCT,
        "size": 100,
        "offset": 0,
        "storeCheck": "true",
        "lat": lat,
        "lng": lng,
        "format": "html",
    }
    url = URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"User-Agent": "CU30thStockMonitor/1.0"}
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        if response.status != 200:
            raise RuntimeError("HTTP " + str(response.status))
        body = response.read(1500000).decode("utf-8", "replace")

    parser = HTMLTokens()
    parser.feed(body)
    tokens = parser.tokens

    if field(tokens, "success") != "true":
        raise RuntimeError("CU API success not true")

    selected = field(tokens, "stockItemCode")
    if selected != BARCODE:
        raise RuntimeError("Wrong selected item: " + str(selected))

    valid = []
    for item in extract_stores(tokens):
        if not valid_address(item["address"], city):
            continue
        quantity = stock_number(item["stock"])
        if quantity is None:
            continue
        item["stock"] = quantity
        item["city"] = city
        valid.append(item)

    return valid

def load_state():
    if not STATE_FILE.exists():
        return {"stores": {}}
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("stores"), dict):
        raise RuntimeError("Invalid CU stock state")
    return data

def save_state(state):
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    temp.replace(STATE_FILE)

def telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        print("TELEGRAM_SECRETS_MISSING", flush=True)
        return False

    url = "https://api.telegram.org/bot" + token + "/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat,
        "text": message,
    }).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            answer = json.load(response)
        return answer.get("ok") is True
    except Exception as exc:
        print("TELEGRAM_ERROR:", type(exc).__name__, flush=True)
        return False

def main():
    print("CU STOCK MONITOR START", flush=True)
    state = load_state()
    observed = {}
    successful_queries = 0
    failed_queries = 0

    for city, points in POINTS.items():
        for lat, lng in points:
            try:
                stores = query(city, lat, lng)
                successful_queries += 1
                print("QUERY_OK:", city, lat, lng,
                      "VALID_STORES:", len(stores), flush=True)

                for item in stores:
                    code = item["code"]
                    previous = observed.get(code)
                    if previous is None:
                        observed[code] = item
                    elif previous["stock"] != item["stock"]:
                        print("STOCK_CONFLICT:", code,
                              previous["stock"], item["stock"], flush=True)
                        observed[code] = dict(item, stock=None)
            except Exception as exc:
                failed_queries += 1
                print("QUERY_ERROR:", city, lat, lng,
                      type(exc).__name__, str(exc)[:200], flush=True)

    print("SUCCESSFUL_QUERIES:", successful_queries, flush=True)
    print("FAILED_QUERIES:", failed_queries, flush=True)
    print("UNIQUE_STORES:", len(observed), flush=True)

    if successful_queries == 0:
        raise RuntimeError("All CU queries failed; state unchanged")

    for code, item in sorted(observed.items()):
        quantity = item["stock"]
        if quantity is None:
            print("SKIP_CONFLICT:", code, flush=True)
            continue

        old = state["stores"].get(code, {})
        previous = stock_number(old.get("stock"))
        old_alerted = bool(old.get("alerted", False))

        should_alert = quantity > 0 and (
            previous == 0 or not old_alerted
        )

        alerted = old_alerted
        if quantity == 0:
            alerted = False

        if should_alert:
            message = (
                "🚨 CU 포켓몬 30주년 카드 재고 발견!\n"
                "상품: " + PRODUCT + "\n"
                "바코드: " + BARCODE + "\n"
                "지역: " + item["city"] + "\n"
                "매장: " + str(item["name"]) + "\n"
                "주소: " + str(item["address"]) + "\n"
                "조회 재고: " + str(quantity) + "개\n"
                "※ 방문 전 매장에 재고를 확인하세요."
            )
            if telegram(message):
                alerted = True
                print("ALERT_SENT:", code, quantity, flush=True)
            else:
                print("ALERT_PENDING:", code, flush=True)
                continue

        state["stores"][code] = {
            "name": item["name"],
            "address": item["address"],
            "city": item["city"],
            "stock": quantity,
            "alerted": alerted,
        }
        print("STORE:", code, item["name"],
              "STOCK:", quantity, "ALERTED:", alerted, flush=True)

    save_state(state)
    print("CU STOCK MONITOR FINISHED", flush=True)

if __name__ == "__main__":
    main()
