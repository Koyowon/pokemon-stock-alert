"""Parse offline mock screen text. No Android, network, login, or GS25 API calls."""
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

class MockScreenError(ValueError):
    pass

class _MockHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_row = False
        self.field = None
        self.rows = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "section" and "stock-row" in classes:
            if self.in_row:
                raise MockScreenError("nested stock rows")
            self.in_row = True
            self.current = {"storeCode": attrs.get("data-store-code", "")}
        elif self.in_row and tag == "span":
            if "store-name" in classes:
                self.field = "storeName"
            elif "stock-quantity" in classes:
                self.field = "quantityText"

    def handle_data(self, data):
        if self.in_row and self.field:
            self.current[self.field] = self.current.get(self.field, "") + data

    def handle_endtag(self, tag):
        if tag == "span":
            self.field = None
        elif tag == "section" and self.in_row:
            self.rows.append(self.current)
            self.current = None
            self.in_row = False

def _normalize(rows):
    if not rows:
        raise MockScreenError("no rows")
    result = []
    seen = set()
    for row in rows:
        code = row.get("storeCode", "").strip()
        name = row.get("storeName", "").strip()
        raw = row.get("quantityText", "").strip()
        if not re.fullmatch(r"MOCK_[0-9]{3}", code) or not name or len(name) > 80:
            raise MockScreenError("invalid store")
        if code in seen:
            raise MockScreenError("duplicate store")
        if not re.fullmatch(r"[0-9]+개", raw):
            raise MockScreenError("invalid quantity")
        quantity = int(raw[:-1])
        if quantity > 9999:
            raise MockScreenError("quantity too large")
        seen.add(code)
        result.append({"storeCode": code, "storeName": name, "realStockQuantity": quantity})
    return {"stores": result}

def parse_mock_html(html):
    parser = _MockHTML()
    parser.feed(html)
    parser.close()
    return _normalize(parser.rows)

def parse_mock_uiautomator_xml(xml):
    """Parse Android UIAutomator XML for a single mock row with accessibility text.

    Expected: one text node containing 'MOCK_001 | GS25 병점역점 | 2개'.
    Not intended for the official GS25 app.
    """
    root = ET.fromstring(xml)
    rows = []
    for node in root.iter("node"):
        value = node.get("text", "")
        if not value.startswith("MOCK_"):
            continue
        parts = [part.strip() for part in value.split("|")]
        if len(parts) != 3:
            raise MockScreenError("invalid mock node")
        rows.append({"storeCode": parts[0], "storeName": parts[1], "quantityText": parts[2]})
    return _normalize(rows)
