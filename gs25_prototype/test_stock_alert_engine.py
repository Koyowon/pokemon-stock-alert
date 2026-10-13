"""Offline-only unit tests for the isolated GS25 mock stock alert engine."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stock_alert_engine import StockAlertError, mock_notification_preview, process_mock_snapshot

PRODUCT = "MOCK_POKEMON_30"
NAME = "포켓몬카드 30주년 메가확장팩"
T1 = "2026-10-14T00:00:00+00:00"
T2 = "2026-10-14T00:10:00+00:00"
T3 = "2026-10-14T00:20:00+00:00"
T4 = "2026-10-14T00:30:00+00:00"


def store(quantity, code="MOCK_001", name="GS25 병점역점"):
    return {"storeCode": code, "storeName": name, "realStockQuantity": quantity}


class TestOfflineStockAlerts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "stock-state.json"

    def process(self, stores, time, product=PRODUCT):
        return process_mock_snapshot(self.path, product, NAME, stores, time)

    def test_first_snapshot_is_baseline(self):
        self.assertEqual(self.process([store(2)], T1), [])
        self.assertEqual(json.loads(self.path.read_text())["items"][PRODUCT + "::MOCK_001"]["quantity"], 2)

    def test_restock_and_duplicate_suppression(self):
        self.process([store(0)], T1)
        events = self.process([store(2)], T2)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "restocked")
        self.assertTrue(events[0]["mockOnly"])
        self.assertIn("테스트 데이터", mock_notification_preview(events[0]))
        self.assertEqual(self.process([store(2)], T2), [])
        self.assertEqual(self.process([store(2)], T3), [])

    def test_increase_decrease_and_restock(self):
        self.process([store(2)], T1)
        self.assertEqual(self.process([store(5)], T2)[0]["type"], "increased")
        self.assertEqual(self.process([store(0)], T3), [])
        self.assertEqual(self.process([store(1)], T4)[0]["type"], "restocked")

    def test_multiple_stores_are_independent(self):
        self.process([store(0), store(0, "MOCK_002", "GS25 다른점")], T1)
        events = self.process([store(2), store(0, "MOCK_002", "GS25 다른점")], T2)
        self.assertEqual([event["storeCode"] for event in events], ["MOCK_001"])

    def test_product_separation(self):
        self.process([store(0)], T1)
        self.assertEqual(self.process([store(2)], T2, "MOCK_OTHER"), [])
        self.assertEqual(len(self.process([store(2)], T3)), 1)

    def test_stale_snapshot_ignored(self):
        self.process([store(3)], T2)
        self.assertEqual(self.process([store(9)], T1), [])
        self.assertEqual(self.process([store(3)], T3), [])

    def test_invalid_input_never_mutates_state(self):
        self.process([store(1)], T1)
        before = self.path.read_bytes()
        for invalid in [store(-1), store(True), store("2"), store(10000), store(2, "REAL_1")]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(StockAlertError):
                    self.process([invalid], T2)
                self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(StockAlertError):
            self.process([store(2), store(2)], T2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_corrupt_state_refuses_overwrite(self):
        self.path.write_text("not json")
        with self.assertRaises(StockAlertError):
            self.process([store(2)], T1)
        self.assertEqual(self.path.read_text(), "not json")

    def test_timezone_required(self):
        with self.assertRaises(StockAlertError):
            self.process([store(2)], "2026-10-14T00:00:00")
        self.assertFalse(self.path.exists())

    def test_preview_rejects_non_mock(self):
        with self.assertRaises(StockAlertError):
            mock_notification_preview({"mockOnly": False})


if __name__ == "__main__":
    unittest.main()
