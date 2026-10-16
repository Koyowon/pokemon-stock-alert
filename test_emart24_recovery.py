"""Offline-only unit tests: never contact the real API or send Telegram."""
import io
import json
import unittest
import sys
import types
from unittest.mock import patch
import urllib.error
from emart24_recovery import (
    InventoryUnavailable, InventoryAccessBlocked, configured_route, request_inventory, OFFICIAL_V3,
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


class OperationalSafetyTests(unittest.TestCase):
    def test_access_blocking_codes(self):
        for status in (401, 403, 429):
            calls = []
            def opener(req, timeout):
                calls.append(1)
                raise urllib.error.HTTPError("mock", status, "blocked", {}, None)
            with self.subTest(status=status), self.assertRaises(InventoryAccessBlocked) as ctx:
                request_inventory({"pluCd": "1", "bizNoArr": "00001"},
                                  environ={"EMART24_INVENTORY_ROUTE": "official_v3"},
                                  opener=opener, sleeper=lambda _: None)
            self.assertEqual(ctx.exception.status, status)
            self.assertEqual(len(calls), 1)

    def test_missing_quantity_field_is_unknown(self):
        with self.assertRaises(InventoryUnavailable):
            request_inventory({"pluCd": "1", "bizNoArr": "00001"},
                              environ={"EMART24_INVENTORY_ROUTE": "official_v3"},
                              opener=lambda req, timeout: response({"storeGoodsQty": [{"BIZNO": "00001"}]}),
                              sleeper=lambda _: None)

    def test_primary_remains_default(self):
        self.assertEqual(configured_route({}), "https://mcp.aka.page/api/emart24")


class MonitorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "region_config" not in sys.modules:
            stub = types.ModuleType("region_config")
            stub.load_enabled_regions = lambda: {"namwon", "asan"}
            sys.modules["region_config"] = stub
        import monitor
        cls.monitor = monitor

    def codes(self):
        return [f"{i:05d}" for i in range(1, 115)]

    def run_stock(self, handler):
        with patch.object(self.monitor, "request_inventory", side_effect=handler), patch.object(self.monitor.time, "sleep", return_value=None):
            return self.monitor.stock("1", self.codes())

    def test_114_stores_38_batches(self):
        calls = []
        def handler(params, **kwargs):
            batch = params["bizNoArr"].split(",")
            calls.append(batch)
            return {"stores": [{"bizNo": c, "bizQty": 0 if i == 0 else 4} for i, c in enumerate(batch)]}
        values, statuses = self.run_stock(handler)
        self.assertEqual(len(calls), 38)
        self.assertEqual(len(values), 114)
        self.assertEqual(values["00001"], 0)
        self.assertTrue(all(v == "OK" for v in statuses.values()))

    def test_access_denied_halts_all_batches(self):
        for code in (401, 403, 429):
            calls = []
            def handler(params, **kwargs):
                calls.append(params)
                raise InventoryAccessBlocked(code)
            with self.subTest(code=code):
                values, statuses = self.run_stock(handler)
                self.assertEqual(len(calls), 1)
                self.assertFalse(values)
                self.assertEqual(sum(v == "NOT_CHECKED" for v in statuses.values()), 111)
                self.assertEqual(sum(v == "ACCESS_BLOCKED" for v in statuses.values()), 3)

    def test_isolated_batch_failure_continues(self):
        calls = []
        def handler(params, **kwargs):
            codes = params["bizNoArr"].split(",")
            calls.append(codes)
            if len(codes) == 3 and codes[0] in ("00001", "00004", "00007"):
                raise InventoryUnavailable("bad batch")
            return {"stores": [{"bizNo": c, "bizQty": 1} for c in codes]}
        values, statuses = self.run_stock(handler)
        self.assertEqual(len(values), 111)
        self.assertEqual(sum(len(c) == 3 for c in calls), 38)
        self.assertEqual(sum(len(c) == 1 for c in calls), 6)
        self.assertEqual(sum(v == "NOT_CHECKED" for v in statuses.values()), 0)
        self.assertEqual(sum(v == "BATCH_ERROR" for v in statuses.values()), 3)

    def test_global_failure_stops_after_three_batches(self):
        calls = []
        def handler(params, **kwargs):
            calls.append(params)
            raise InventoryUnavailable("HTTP 502")
        values, statuses = self.run_stock(handler)
        self.assertFalse(values)
        self.assertEqual(len(calls), 9)
        self.assertEqual(sum(v == "NOT_CHECKED" for v in statuses.values()), 105)

    def test_missing_and_conflicting_quantities(self):
        def handler(params, **kwargs):
            codes = params["bizNoArr"].split(",")
            if codes[0] == "00001":
                return {"stores": [{"bizNo": "00001", "bizQty": 2}]}
            return {"stores": [{"bizNo": c, "bizQty": 0} for c in codes]}
        values, statuses = self.run_stock(handler)
        self.assertEqual(statuses["00002"], "MISSING_IN_RESPONSE")
        self.assertEqual(values["00004"], 0)
        self.assertNotIn("00002", values)

    def test_main_preserves_state_on_unknown_and_failed_alert(self):
        import contextlib
        import io as _io
        monitor = self.monitor
        stores = {"00001": {"name": "test", "address": "남원시"}}
        key = "이마트24|00001|8800286275732"
        saved = []
        def save(path, data):
            saved.append(dict(data))
        settings = types.ModuleType("unified_settings")
        settings.enabled = lambda service, regions: {"namwon"}
        with patch.dict(sys.modules, {"unified_settings": settings}), patch.object(monitor, "get_stores", return_value=stores), patch.object(monitor, "read_json", return_value={key: 1}), patch.object(monitor, "save_json", side_effect=save), patch.object(monitor, "notify", return_value=False), patch.object(monitor, "stock", return_value=({}, {"00001": "NOT_CHECKED"})), contextlib.redirect_stdout(_io.StringIO()):
            monitor.main()
        self.assertFalse(saved)
        with patch.dict(sys.modules, {"unified_settings": settings}), patch.object(monitor, "get_stores", return_value=stores), patch.object(monitor, "read_json", return_value={key: 1}), patch.object(monitor, "save_json", side_effect=save), patch.object(monitor, "notify", return_value=False), patch.object(monitor, "stock", return_value=({"00001": 3}, {"00001": "OK"})), contextlib.redirect_stdout(_io.StringIO()):
            monitor.main()
        self.assertEqual(saved[-1][key], 1)

if __name__ == "__main__":
    unittest.main()
