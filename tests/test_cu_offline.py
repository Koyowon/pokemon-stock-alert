"""Offline-only safety tests for the CU 30th anniversary stock monitor.

No real API access, Telegram, GitHub Actions, or production state changes.
Run: python -m unittest discover -s tests -p 'test_cu_offline.py' -v
"""
import ast
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import cu_asan_registry as registry
import cu_stock_monitor as monitor

ROOT = Path(__file__).resolve().parents[1]
BARCODE = "8800286275732"


class RegistryTests(unittest.TestCase):
    def test_registry_integrity(self):
        raw = json.loads((ROOT / "asan_cu_watch_registry.json").read_text(encoding="utf-8"))
        stores = registry.load_registry()
        self.assertEqual(raw["schema_version"], 1)
        self.assertEqual(raw["region"], "아산")
        self.assertEqual(raw["candidate_count"], 119)
        self.assertEqual(raw["product_barcode"], BARCODE)
        self.assertEqual(len(stores), 119)
        self.assertEqual(len({s["registry_id"] for s in stores}), 119)
        self.assertEqual(len({s["name"] for s in stores}), 119)
        self.assertEqual(sum(bool(s["cu_store_code"]) for s in stores), 28)
        self.assertTrue(all(s["monitor_candidate"] is True for s in stores))
        self.assertTrue(all(s["product_barcode"] == BARCODE for s in stores))
        self.assertTrue(all(s["product_status"] == "NOT_QUERIED" for s in stores))

    def test_unqueried_is_not_zero(self):
        rows = registry.classify_observations({}, query_succeeded=False)
        self.assertEqual(len(rows), 119)
        self.assertTrue(all(s["status"] == "NOT_QUERIED" and s["stock"] is None for s in rows))

    def test_unobserved_is_not_zero(self):
        rows = registry.classify_observations({}, query_succeeded=True)
        self.assertTrue(all(s["status"] == "NOT_OBSERVED" and s["stock"] is None for s in rows))

    def test_zero_positive_and_invalid_are_distinct(self):
        codes = list(dict.fromkeys(
            s["cu_store_code"] for s in registry.load_registry() if s["cu_store_code"]
        ))
        self.assertGreaterEqual(len(codes), 3)
        observed = {codes[0]: 0, codes[1]: 3, codes[2]: None}
        rows = registry.classify_observations(observed, query_succeeded=True)
        for code, expected in (
            (codes[0], "ZERO_STOCK"),
            (codes[1], "IN_STOCK"),
            (codes[2], "NO_VALID_STOCK_VALUE"),
        ):
            self.assertTrue(any(r["cu_store_code"] == code and r["status"] == expected for r in rows))
        self.assertTrue(any(r["status"] == "NOT_OBSERVED" for r in rows))

    def test_boolean_is_not_stock_integer(self):
        code = next(s["cu_store_code"] for s in registry.load_registry() if s["cu_store_code"])
        rows = registry.classify_observations({code: False}, query_succeeded=True)
        self.assertTrue(any(r["cu_store_code"] == code and r["status"] == "NO_VALID_STOCK_VALUE" for r in rows))


class MonitorTests(unittest.TestCase):
    def test_product_and_regions_unchanged(self):
        self.assertEqual(monitor.BARCODE, BARCODE)
        self.assertEqual(registry.PRODUCT_BARCODE, BARCODE)
        self.assertEqual(monitor.PRODUCT, "포켓몬)30주년기념카드")
        self.assertEqual(set(monitor.POINTS), {"남원", "아산", "전주", "제주"})
        self.assertEqual(len(monitor.POINTS["아산"]), 7)
        self.assertEqual(set(monitor.REGION_IDS.values()), {"namwon", "asan", "jeonju", "jeju"})

    def test_query_rejects_other_barcode_without_network(self):
        class FakeResponse:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self, _):
                return b"<div>success</div><div>true</div><div>stockItemCode</div><div>WRONG</div>"
        with patch.object(monitor.urllib.request, "urlopen", return_value=FakeResponse()) as mocked:
            with self.assertRaisesRegex(RuntimeError, "Wrong selected product"):
                monitor.query("아산", 36.79, 127.0)
            self.assertEqual(mocked.call_count, 1)

    def test_no_live_network_or_notifications_during_main(self):
        # All regions enabled, but all geographic queries are local mocks.
        # An empty result means no stock observation, not zero stock.
        with (
            patch("unified_settings.enabled", return_value={"namwon", "asan", "jeonju", "jeju"}),
            patch.object(monitor, "load_state", return_value={"stores": {}}),
            patch.object(monitor, "query", return_value=[]) as mocked_query,
            patch.object(monitor, "telegram", side_effect=AssertionError("Telegram must not be called")),
            patch.object(monitor, "save_state") as mocked_save,
            patch.object(monitor.urllib.request, "urlopen", side_effect=AssertionError("Network prohibited")),
        ):
            monitor.main()
            self.assertEqual(mocked_query.call_count, sum(map(len, monitor.POINTS.values())))
            mocked_save.assert_called_once_with({"stores": {}})

    def test_alert_logic_is_still_present(self):
        tree = ast.parse((ROOT / "cu_stock_monitor.py").read_text(encoding="utf-8"))
        funcs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertTrue({"query", "telegram", "load_state", "save_state", "main"} <= funcs)
        source = (ROOT / "cu_stock_monitor.py").read_text(encoding="utf-8")
        self.assertIn("if telegram(body):", source)
        self.assertIn("ALERT_PENDING:", source)
        self.assertIn("ALERT_SENT:", source)
        self.assertIn("save_state(state)", source)
        self.assertIn("summarize_observations(", source)
        self.assertIn("asan_successful_queries > 0", source)

    def test_workflow_is_manual_only(self):
        source = (ROOT / ".github/workflows/cu-offline-validation.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertNotIn("schedule:", source)
        self.assertIn("contents: read", source)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", source)
        self.assertNotIn("TELEGRAM_CHAT_ID", source)
        self.assertNotIn("python cu_stock_monitor.py", source)


if __name__ == "__main__":
    unittest.main()
