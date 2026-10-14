"""Offline-only unit tests: never contact the real API or send Telegram."""
import io
import json
import unittest
import urllib.error
from emart24_recovery import (
    InventoryUnavailable, configured_route, request_inventory,
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


if __name__ == "__main__":
    unittest.main()
