"""Offline integration tests of the actual Emart24 monitor.main/stock.

All I/O boundaries are mocked. No API, Telegram, or state-file writes.
Run: python -B -m unittest -v test_emart24_integration
"""
import contextlib
import io
import os
import unittest
import urllib.error
from unittest.mock import patch

import monitor


PLU = next(iter(monitor.PRODUCTS.values()))


def stores(count=114):
    return {
        f"{i:05d}": {"name": f"Fixture {i}", "address": "전북특별자치도 남원시 테스트로 1"}
        for i in range(count)
    }


def key(code):
    return f"이마트24|{code}|{PLU}"


class MonitorIntegrationTests(unittest.TestCase):
    def run_monitor(self, fixtures, previous, request_side_effect, *, notify_result=True,
                    route=None):
        saved = []
        sent = []
        output = io.StringIO()
        env = {"EMART24_INVENTORY_ROUTE": route} if route is not None else {}
        with patch.dict(os.environ, env, clear=True), \
             patch("region_config.load_enabled_regions", return_value={"namwon"}), \
             patch("unified_settings.enabled", return_value={"namwon"}), \
             patch.object(monitor, "get_stores", return_value=fixtures), \
             patch.object(monitor, "read_json", return_value=dict(previous)), \
             patch.object(monitor, "save_json", side_effect=lambda path, data: saved.append((path, dict(data)))), \
             patch.object(monitor, "notify", side_effect=lambda msg: sent.append(msg) or notify_result), \
             patch.object(monitor.time, "sleep", return_value=None), \
             patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK ACCESS FORBIDDEN")), \
             patch.object(monitor, "request_inventory", side_effect=request_side_effect), \
             contextlib.redirect_stdout(output):
            monitor.main()
        return saved, sent, output.getvalue()

    def test_114_stores_all_502_no_state_save_or_telegram(self):
        fixtures = stores()
        previous = {key(code): 7 for code in fixtures}
        calls = []
        def fail(params, **kwargs):
            calls.append((params, kwargs))
            raise urllib.error.HTTPError("mock", 502, "Bad Gateway", {}, None)
        saved, sent, log = self.run_monitor(fixtures, previous, fail)
        self.assertEqual(saved, [])
        self.assertEqual(sent, [])
        self.assertIn("Finished: 0 numeric inventory entries, 114 unknown entries", log)
        self.assertIn("3 consecutive failed batches", log)
        self.assertLessEqual(len(calls), 9)  # 3 batches + max 6 singles
        self.assertIn("state.json left unchanged", log)

    def test_partial_success_updates_only_verified_stores(self):
        fixtures = stores(3)
        previous = {key(code): 0 for code in fixtures}
        codes = list(fixtures)
        def partial(params, **kwargs):
            return {"stores": [{"bizNo": codes[0], "bizQty": 0},
                               {"bizNo": codes[1], "bizQty": 3}]}
        saved, sent, log = self.run_monitor(fixtures, previous, partial)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0][1][key(codes[0])], 0)
        self.assertEqual(saved[0][1][key(codes[1])], 3)
        self.assertEqual(saved[0][1][key(codes[2])], 0)  # prior state preserved
        self.assertEqual(len(sent), 1)
        self.assertIn("2 numeric inventory entries, 1 unknown entries", log)

    def test_verified_zero_is_not_unknown(self):
        fixtures = stores(1)
        code = next(iter(fixtures))
        previous = {key(code): 2}
        saved, sent, log = self.run_monitor(
            fixtures, previous, lambda params, **kwargs: {
                "stores": [{"bizNo": code, "bizQty": 0}]})
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0][1][key(code)], 0)
        self.assertEqual(len(sent), 1)
        self.assertIn("품절 확인", sent[0])
        self.assertIn("1 numeric inventory entries, 0 unknown entries", log)

    def test_notification_failure_does_not_advance_state(self):
        fixtures = stores(1)
        code = next(iter(fixtures))
        previous = {key(code): 0}
        saved, sent, log = self.run_monitor(
            fixtures, previous, lambda params, **kwargs: {
                "stores": [{"bizNo": code, "bizQty": 5}]}, notify_result=False)
        self.assertEqual(len(sent), 1)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0][1][key(code)], 0)
        self.assertIn("alert failed, state not advanced", log)

    def test_unapproved_route_never_contacts_network_or_saves(self):
        fixtures = stores(1)
        previous = {key(code): 9 for code in fixtures}
        # Exercise real route validation and transport, but intercept network.
        from emart24_recovery import request_inventory
        with patch.dict(os.environ, {"EMART24_INVENTORY_ROUTE": "unapproved"}, clear=True), \
             patch("region_config.load_enabled_regions", return_value={"namwon"}), \
             patch("unified_settings.enabled", return_value={"namwon"}), \
             patch.object(monitor, "get_stores", return_value=fixtures), \
             patch.object(monitor, "read_json", return_value=dict(previous)), \
             patch.object(monitor, "save_json") as save, \
             patch.object(monitor, "notify") as notify, \
             patch.object(monitor.time, "sleep", return_value=None), \
             patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK ACCESS FORBIDDEN")) as network, \
             patch.object(monitor, "request_inventory", side_effect=request_inventory), \
             contextlib.redirect_stdout(io.StringIO()):
            monitor.main()
        network.assert_not_called()
        save.assert_not_called()
        notify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
