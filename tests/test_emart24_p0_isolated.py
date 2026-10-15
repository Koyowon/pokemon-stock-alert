"""Offline regression specifications for main's emart24 monitor.
Run: python -m unittest discover -s tests -p 'test_emart24_p0_isolated.py' -v
No real network, Telegram, Git push or operational state writes.
"""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class Emart24P0Isolated(unittest.TestCase):
    def setUp(self):
        self.m = importlib.import_module("monitor")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "state.json"
        self.stores = Path(self.temp.name) / "stores.json"
        self.state.write_text('{"이마트24|100|8800286275732": 7}', encoding="utf-8")
        self.patches = [
            patch.object(self.m, "STATE_FILE", self.state),
            patch.object(self.m, "STORES_FILE", self.stores),
            patch.object(self.m, "get_stores", return_value={"100": {"name": "테스트점", "address": "전북특별자치도 남원시 테스트로 1"}}),
            patch.object(self.m, "load_enabled_regions", return_value={"namwon"}),
            patch("unified_settings.enabled", return_value={"namwon"}),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_01_all_502_is_failure_and_preserves_state(self):
        """P0 expected: all 502 must cause nonzero exit, never a success-looking run."""
        before = self.state.read_bytes()
        with patch.object(self.m, "stock", return_value=({}, {"100": "BATCH_ERROR"})), patch.object(self.m, "notify") as notify:
            with self.assertRaises(RuntimeError):
                self.m.main()
            notify.assert_not_called()
        self.assertEqual(self.state.read_bytes(), before)

    def test_02_partial_success_keeps_failed_store(self):
        """Only verified numeric quantities can advance; absent stores stay untouched."""
        self.state.write_text('{"이마트24|100|8800286275732": 7, "이마트24|200|8800286275732": 9}', encoding="utf-8")
        stores = {
            "100": {"name": "테스트점", "address": "전북특별자치도 남원시 테스트로 1"},
            "200": {"name": "다른점", "address": "전북특별자치도 남원시 테스트로 2"},
        }
        with patch.object(self.m, "get_stores", return_value=stores), patch.object(self.m, "stock", return_value=({"100": 7}, {"100": "OK", "200": "BATCH_ERROR"})), patch.object(self.m, "notify") as notify:
            self.m.main()
            notify.assert_not_called()
        import json
        data = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(data["이마트24|200|8800286275732"], 9)

    def test_03_numeric_zero_is_real_stock_and_alerts(self):
        with patch.object(self.m, "stock", return_value=({"100": 0}, {"100": "OK"})), patch.object(self.m, "notify", return_value=True) as notify:
            self.m.main()
            notify.assert_called_once()
        import json
        self.assertEqual(json.loads(self.state.read_text(encoding="utf-8"))["이마트24|100|8800286275732"], 0)

    def test_04_telegram_failure_does_not_advance_baseline(self):
        before = self.state.read_bytes()
        with patch.object(self.m, "stock", return_value=({"100": 8}, {"100": "OK"})), patch.object(self.m, "notify", return_value=False):
            self.m.main()
        import json
        self.assertEqual(json.loads(self.state.read_text(encoding="utf-8")), json.loads(before.decode("utf-8")))

    def test_05_write_failure_preserves_existing_state(self):
        """P0 expected: write failure must not corrupt the previous JSON."""
        before = self.state.read_bytes()
        with patch.object(self.m, "stock", return_value=({"100": 7}, {"100": "OK"})), \
             patch.object(self.m.os, "replace", side_effect=OSError("disk interrupted")):
            with self.assertRaises(OSError):
                self.m.main()
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(list(self.state.parent.glob(".state.json.*.tmp")), [])

    def test_06_workflow_push_collision_policy(self):
        """Static workflow guard: detect non-isolated cross-chain pushes to main."""
        root = Path(__file__).resolve().parents[1]
        em = (root / ".github/workflows/stock-monitor.yml").read_text(encoding="utf-8")
        cu = (root / ".github/workflows/cu-stock-monitor.yml").read_text(encoding="utf-8")
        gs = (root / ".github/workflows/gs25-stock-monitor.yml").read_text(encoding="utf-8")
        self.assertIn("git push", em)
        self.assertIn("git push", cu)
        self.assertIn("git push", gs)
        # P0 target: a shared state-write lock or proven conflict-safe push mechanism.
        self.assertTrue(
            all("group: shared-state-push" in w for w in (em, cu, gs))
            or all("retry" in w.lower() and "git push" in w for w in (em, cu, gs)),
            "Cross-workflow state pushes lack a shared lock or explicit retry policy",
        )


if __name__ == "__main__":
    unittest.main()
