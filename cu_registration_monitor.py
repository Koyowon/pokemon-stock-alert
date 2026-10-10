"""CU Pokemon 30th registration monitor; independent of Emart24."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://mcp.aka.page/api/cu/inventory"
BARCODE = "8800286275732"
STATE = Path(__file__).with_name("cu_registration_state.json")
KEYWORDS = [
    BARCODE,
    "포켓몬카드",
    "포켓몬30주년",
    "30주년",
    "셀러브레이션",
    "포켓몬확장팩",
]
EXCLUDED = ("교통카드", "이즐", "키링", "빵", "스티커",
            "음료", "젤리", "과자", "카드케이스")

class HTMLReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens = []
        self.in_pre = False
        self.pre_parts = []
        self.pre_blocks = []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.in_pre = True
            self.pre_parts = []

    def handle_endtag(self, tag):
        if tag == "pre" and self.in_pre:
            self.pre_blocks.append("".join(self.pre_parts))
            self.in_pre = False

    def handle_data(self, data):
        value = data.strip()
        if value:
            self.tokens.append(value)
        if self.in_pre:
            self.pre_parts.append(data)

def get_page(keyword, offset=0):
    params = {
        "keyword": keyword,
        "size": 100,
        "offset": offset,
        "storeCheck": "false",
        "format": "html",
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"User-Agent": "PokemonCURegistration/1.0"}
    )
    with urllib.request.urlopen(req, timeout=35) as response:
        status = response.status
        body = response.read(1000000).decode("utf-8", "replace")
    if status != 200:
        raise RuntimeError("HTTP " + str(status))

    parser = HTMLReader()
    parser.feed(body)

    # Prefer a real JSON object when the HTML page embeds one.
    for block in parser.pre_blocks:
        try:
            obj = json.loads(block)
        except (ValueError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("success") is not True:
            raise RuntimeError("CU API success=false")
        data = obj.get("data", {})
        if isinstance(data, dict):
            products = data.get("products")
            if isinstance(products, list):
                total = data.get("total")
                return products, total if type(total) is int else None

    tokens = parser.tokens
    if "success" not in tokens:
        raise RuntimeError("Missing success field")
    pos = tokens.index("success")
    if pos + 1 >= len(tokens) or tokens[pos + 1] != "true":
        raise RuntimeError("CU API success is not true")

    total = None
    if "total" in tokens:
        i = tokens.index("total")
        if i + 1 < len(tokens) and tokens[i + 1].isdigit():
            total = int(tokens[i + 1])

    products = []
    for i, token in enumerate(tokens):
        if token != "itemCode" or i + 1 >= len(tokens):
            continue
        code = tokens[i + 1].strip()
        if not re.fullmatch(r"[0-9]{8,14}", code):
            continue
        name = ""
        # Product fields appear consecutively in the HTML response.
        for j in range(i + 2, min(i + 14, len(tokens) - 1)):
            if tokens[j] == "itemCode":
                break
            if tokens[j] == "itemName":
                name = tokens[j + 1].strip()
                break
        if name:
            products.append({"itemCode": code, "itemName": name})

    if total and not products:
        raise RuntimeError("Products exist but HTML parsing failed")
    return products, total

def is_target(code, name):
    code = str(code).strip()
    name = str(name).strip()
    compact = re.sub(r"\\s+", "", name).upper()

    if any(word.upper() in compact for word in EXCLUDED):
        return False, "excluded"

    if code == BARCODE:
        return True, "exact_barcode"

    anniversary = any(word in compact for word in
                      ("30주년", "30TH", "30THCELEBRATION",
                       "셀러브레이션", "CELEBRATION"))
    pokemon = "포켓몬" in compact or "POKEMON" in compact
    tcg = any(word in compact for word in
              ("카드", "확장팩", "BOOSTER", "TCG", "팩"))
    if anniversary and pokemon and tcg:
        return True, "name_candidate"
    return False, "unrelated"

def load_state():
    if not STATE.exists():
        return {"notified": {}}
    data = json.loads(STATE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("notified"), dict):
        raise RuntimeError("Invalid CU state file")
    return data

def save_state(state):
    temp = STATE.with_suffix(".tmp")
    temp.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    temp.replace(STATE)

def telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("TELEGRAM_SECRETS_MISSING", flush=True)
        return False
    url = "https://api.telegram.org/bot" + token + "/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.load(response)
        return result.get("ok") is True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print("TELEGRAM_ERROR:", type(exc).__name__, flush=True)
        return False

def main():
    print("CU REGISTRATION MONITOR START", flush=True)
    state = load_state()
    found = {}
    successful = 0
    failures = 0

    for keyword in KEYWORDS:
        try:
            offset = 0
            seen_pages = set()
            while offset < 300:
                products, total = get_page(keyword, offset)
                successful += 1
                print("QUERY:", keyword, "OFFSET:", offset,
                      "PRODUCTS:", len(products), "TOTAL:", total,
                      flush=True)
                page_signature = tuple(
                    str(p.get("itemCode", "")) for p in products
                )
                if page_signature in seen_pages:
                    break
                seen_pages.add(page_signature)

                for product in products:
                    if not isinstance(product, dict):
                        continue
                    code = str(product.get("itemCode", "")).strip()
                    name = str(product.get("itemName", "")).strip()
                    match, reason = is_target(code, name)
                    if match and code and name:
                        found[code] = {"name": name, "reason": reason}
                        print("TARGET:", code, name, reason, flush=True)

                if not products or len(products) < 100:
                    break
                if total is not None and offset + 100 >= total:
                    break
                offset += 100
                time.sleep(2)
        except Exception as exc:
            failures += 1
            print("QUERY_ERROR:", keyword,
                  type(exc).__name__, str(exc)[:200], flush=True)
        time.sleep(2)

    if successful == 0:
        raise RuntimeError("All CU API queries failed; no state changes")

    print("SUCCESSFUL_PAGES:", successful, "FAILED_QUERIES:", failures)
    print("TARGET_COUNT:", len(found), flush=True)

    for code, item in sorted(found.items()):
        if code in state["notified"]:
            print("ALREADY_NOTIFIED:", code, flush=True)
            continue
        reason = item["reason"]
        confidence = ("바코드 정확히 일치" if reason == "exact_barcode"
                      else "상품명 일치 후보 - 확인 필요")
        message = (
            "🔔 CU 포켓몬 30주년 상품 등록 감지\n"
            "상품명: " + item["name"] + "\n"
            "상품코드: " + code + "\n"
            "판정: " + confidence + "\n"
            "※ 상품 등록 감지이며 매장 재고 확인은 아닙니다."
        )
        if telegram(message):
            state["notified"][code] = item
            save_state(state)
            print("NOTIFIED:", code, flush=True)
        else:
            print("NOTIFICATION_PENDING:", code, flush=True)

    print("CU REGISTRATION MONITOR FINISHED", flush=True)

if __name__ == "__main__":
    main()
