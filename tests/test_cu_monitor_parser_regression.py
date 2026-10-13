"""Regression fixtures for the real CU parser/query functions; no live API calls.

Run locally against the checked-out feature branch:
    python -m unittest discover -s tests -p 'test_cu_monitor_parser_regression.py' -v
This module NEVER calls monitor.main(), telegram(), or save_state().
"""
import unittest
from unittest.mock import patch
import cu_stock_monitor as monitor


class FakeResponse:
    status = 200

    def __init__(self, html):
        self.body = html.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.body[:size]


def fixture_html(*stores, barcode=monitor.BARCODE, success="true"):
    def field(k, v):
        return f"<span>{k}</span><span>{v}</span>"
    return field("success", success) + field("stockItemCode", barcode) + "".join(
        "".join(field(k, v) for k, v in store.items()) for store in stores
    )


def store(**changes):
    result = {
        "storeCode": "12345",
        "storeName": "아산테스트점",
        "address": "충청남도 아산시 온천동 1",
        "stock": "2",
    }
    result.update(changes)
    return result


class ParserRegression(unittest.TestCase):
    def query_fixture(self, html):
        with patch.object(monitor.urllib.request, "urlopen", return_value=FakeResponse(html)) as urlopen:
            result = monitor.query("아산", 36.790, 127.000)
            self.assertEqual(urlopen.call_count, 1)
            return result

    def test_valid_store(self):
        rows = self.query_fixture(fixture_html(store()))
        self.assertEqual([(r["code"], r["stock"], r["city"]) for r in rows], [("12345", 2, "아산")])

    def test_explicit_zero(self):
        self.assertEqual(self.query_fixture(fixture_html(store(stock="0")))[0]["stock"], 0)

    def test_invalid_stock_filtered(self):
        self.assertEqual(self.query_fixture(fixture_html(store(stock="-1"))), [])

    def test_missing_stock_filtered(self):
        row = store()
        row.pop("stock")
        self.assertEqual(self.query_fixture(fixture_html(row)), [])

    def test_wrong_city_filtered(self):
        self.assertEqual(self.query_fixture(fixture_html(store(address="충청남도 천안시 1"))), [])

    def test_invalid_store_code_filtered(self):
        self.assertEqual(self.query_fixture(fixture_html(store(storeCode="ABC"))), [])

    def test_wrong_barcode_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Wrong selected product"):
            self.query_fixture(fixture_html(barcode="WRONG"))

    def test_api_failure_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "success not true"):
            self.query_fixture(fixture_html(success="false"))

    def test_query_returns_duplicates_for_later_reconciliation(self):
        self.assertEqual(len(self.query_fixture(fixture_html(store(), store()))), 2)

    def test_stock_number_validation(self):
        for value in (None, True, -1, 1.2, "-1", "1.2", "없음"):
            self.assertIsNone(monitor.stock_number(value))
        self.assertEqual(monitor.stock_number(" 003 "), 3)

    def test_query_parameters(self):
        with patch.object(monitor.urllib.request, "urlopen", return_value=FakeResponse(fixture_html())) as mocked:
            monitor.query("아산", 36.790, 127.000)
            url = mocked.call_args.args[0].full_url
            self.assertIn("size=100", url)
            self.assertIn("offset=0", url)

    def test_no_real_http_even_if_fixture_fails(self):
        with patch.object(monitor.urllib.request, "urlopen", side_effect=RuntimeError("mock blocked")):
            with self.assertRaisesRegex(RuntimeError, "mock blocked"):
                monitor.query("아산", 36.790, 127.000)


if __name__ == "__main__":
    unittest.main()
