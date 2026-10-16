"""Offline-only unit tests: never contact the real API or send Telegram."""
import io
import json
import unittest
import urllib.error
from emart24_recovery import (
    InventoryUnavailable, configured_route, request_inventory, OFFICIAL_V3,
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


def response(data):
    return FakeResponse(json.dumps(data).encode("utf-8"))


class RecoveryTests(unittest.TestCase):
    def test_default_route_is_existing_documented_proxy(self):
        self.assertEqual(configured_route({}), "https://mcp.aka.page/api/emart24")

    def test_unapproved_alternate_is_blocked_before_network(self):
        with self.assertRaises(InventoryUnavailable):
            request_inventory({"pluCd": "1", "bizNoArr": "2"},
                              environ={"EMART24_INVENTORY_ROUTE": "alternate"},
                              opener=lambda *a, **k: self.fail("network attempted"))

    def test_success_preserves_verified_zero(self):
        data = request_inventory({"pluCd": "1", "bizNoArr": "2"},
                                 opener=lambda *a, **k: response({
                                     "success": True, "data": {"stores": [
                                         {"bizNo": "2", "bizQty": 0}]} }))
        self.assertEqual(data["stores"][0]["bizQty"], 0)

    def test_502_retries_then_unknown(self):
        calls = []
        def fail(*args, **kwargs):
            calls.append(1)
            raise urllib.error.HTTPError("mock", 502, "Bad Gateway", {}, None)
        with self.assertRaisesRegex(InventoryUnavailable, "UNKNOWN"):
            request_inventory({"pluCd": "1", "bizNoArr": "2"},
                              opener=fail, sleeper=lambda seconds: None)
        self.assertEqual(len(calls), 2)

    def test_403_is_not_retried(self):
        calls = []
        def fail(*args, **kwargs):
            calls.append(1)
            raise urllib.error.HTTPError("mock", 403, "Forbidden", {}, None)
        with self.assertRaises(InventoryUnavailable):
            request_inventory({"pluCd": "1", "bizNoArr": "2"},
                              opener=fail, sleeper=lambda seconds: None)
        self.assertEqual(len(calls), 1)

    def test_invalid_response_not_stock(self):
        for data in [{"success": False, "data": {"stores": []}},
                     {"success": True, "data": {"stores": [{"bizQty": -1}]}},
                     {"success": True, "data": {"stores": "invalid"}}]:
            with self.subTest(data=data), self.assertRaises(InventoryUnavailable):
                request_inventory({"pluCd": "1", "bizNoArr": "2"},
                                  opener=lambda *a, **k: response(data),
                                  sleeper=lambda seconds: None)

    def test_timeout_is_unknown(self):
        with self.assertRaises(InventoryUnavailable):
            request_inventory({"pluCd": "1", "bizNoArr": "2"},
                              opener=lambda *a, **k: (_ for _ in ()).throw(TimeoutError()),
                              sleeper=lambda seconds: None)


class OfficialV3Tests(unittest.TestCase):
    ROUTE = {"EMART24_INVENTORY_ROUTE": "official_v3"}

    def check(self, payload, codes="00001", opener=None):
        return request_inventory(
            {"pluCd": "8800286275732", "bizNoArr": codes},
            environ=self.ROUTE,
            opener=opener or (lambda req, timeout: response(payload)),
            sleeper=lambda seconds: None,
        )

    def test_route_opt_in_and_query(self):
        self.assertNotEqual(configured_route({}), OFFICIAL_V3)
        urls = []
        def opener(req, timeout):
            urls.append(req.full_url)
            return response({"storeGoodsQty": [{"BIZNO": "00001", "BIZQTY": 0}]})
        self.check({}, opener=opener)
        self.assertIn("searchPluCode=8800286275732", urls[0])
        self.assertIn("bizNoArr=00001", urls[0])
        self.assertNotIn("pluCd=", urls[0])

    def test_zero_positive_null(self):
        rows = [{"BIZNO": "00001", "BIZQTY": 0},
                {"BIZNO": "00002", "BIZQTY": "5"},
                {"BIZNO": "00003", "BIZQTY": None}]
        got = self.check({"storeGoodsQty": rows}, "00001,00002,00003")
        self.assertEqual([r["bizQty"] for r in got["stores"]], [0, 5, None])

    def test_all_114_stores(self):
        codes = [f"{i:05d}" for i in range(1, 115)]
        rows = [{"BIZNO": c, "BIZQTY": i % 4} for i, c in enumerate(codes)]
        self.assertEqual(len(self.check({"storeGoodsQty": rows}, ",".join(codes))["stores"]), 114)

    def test_partial_missing_is_unknown(self):
        got = self.check({"storeGoodsQty": [{"BIZNO": "00001", "BIZQTY": 2}]}, "00001,00002")
        self.assertEqual(got["stores"], [{"bizNo": "00001", "bizQty": 2}])

    def test_conflicting_duplicate_rejected(self):
        with self.assertRaises(InventoryUnavailable):
            self.check({"storeGoodsQty": [{"BIZNO": "00001", "BIZQTY": 1},
                                          {"BIZNO": "00001", "BIZQTY": 2}]})

    def test_invalid_quantities_rejected(self):
        for qty in [-1, True, "unknown", 1.5]:
            with self.subTest(qty=qty), self.assertRaises(InventoryUnavailable):
                self.check({"storeGoodsQty": [{"BIZNO": "00001", "BIZQTY": qty}]})

    def test_502_and_timeout_unknown(self):
        for err in [urllib.error.HTTPError("mock", 502, "Bad Gateway", {}, None), TimeoutError()]:
            with self.subTest(err=str(err)), self.assertRaises(InventoryUnavailable):
                self.check({}, opener=lambda req, timeout, e=err: (_ for _ in ()).throw(e))

    def test_403_no_retry(self):
        calls = []
        def opener(req, timeout):
            calls.append(1)
            raise urllib.error.HTTPError("mock", 403, "Forbidden", {}, None)
        with self.assertRaises(InventoryUnavailable):
            self.check({}, opener=opener)
        self.assertEqual(len(calls), 1)

    def test_bad_payload_unknown(self):
        for payload in [{}, {"storeGoodsQty": None}, {"storeGoodsQty": "bad"}]:
            with self.subTest(payload=payload), self.assertRaises(InventoryUnavailable):
                self.check(payload)

if __name__ == "__main__":
    unittest.main()
