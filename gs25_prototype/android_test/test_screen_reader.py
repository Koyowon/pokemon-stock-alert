"""Offline-only unit tests for mock GS25 stock UI data extraction."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screen_reader import MockScreenError, parse_mock_html, parse_mock_uiautomator_xml

def html(quantity="2개", name="GS25 병점역점", code="MOCK_001"):
    return ('<section class="stock-row" data-store-code="' + code +
            '"><span class="store-name">' + name +
            '</span><span class="stock-quantity">' + quantity +
            '</span></section>')

class TestMockScreenReader(unittest.TestCase):
    def test_html_stock_quantities(self):
        for quantity, expected in [("0개", 0), ("2개", 2), ("12개", 12)]:
            with self.subTest(quantity=quantity):
                self.assertEqual(parse_mock_html(html(quantity))["stores"][0]["realStockQuantity"], expected)

    def test_real_mock_file(self):
        source = Path(__file__).with_name("mock_screen.html").read_text(encoding="utf-8")
        self.assertEqual(parse_mock_html(source), {"stores": [
            {"storeCode": "MOCK_001", "storeName": "GS25 병점역점", "realStockQuantity": 2}]})

    def test_invalid_fields_fail_closed(self):
        for source in [html("재고없음"), html("-1개"), html("1.5개"),
                       html(name=""), html(code="REAL_001"), "<main>no rows</main>",
                       html() + html()]:
            with self.subTest(source=source[:40]):
                with self.assertRaises(MockScreenError):
                    parse_mock_html(source)

    def test_uiautomator_mock_node(self):
        xml = '<hierarchy><node text="MOCK_001 | GS25 병점역점 | 2개"/></hierarchy>'
        self.assertEqual(parse_mock_uiautomator_xml(xml)["stores"][0]["realStockQuantity"], 2)

    def test_uiautomator_invalid_node(self):
        with self.assertRaises(MockScreenError):
            parse_mock_uiautomator_xml('<hierarchy><node text="MOCK_001 | GS25 병점역점 | ?"/></hierarchy>')

if __name__ == "__main__":
    unittest.main()
