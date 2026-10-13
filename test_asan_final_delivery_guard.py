"""Offline final regression checks: Asan preview never sends extra Telegram messages."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch
from urllib.parse import quote
import cu_stock_monitor as monitor
from asan_stock_snapshot import build_snapshot
from asan_stock_chunks import preview_asan_stock_messages

class AsanFinalDeliveryGuardTests(unittest.TestCase):
    def run_monitor(self, stock, previous=None, alerted=False, query_error=False):
        sent, saved = [], []
        code = "53982"
        item = {"code": code, "name": "씨유 아산온천타운점", "address": "충청남도 아산시 중앙로 27 (온천동)", "stock": stock, "city": "아산"}
        old = {} if previous is None else {code: {**item, "stock": previous, "alerted": alerted}}
        def query(city, lat, lng):
            if city != "아산":
                return []
            if query_error:
                raise TimeoutError("offline injected")
            return [item] if (lat, lng) == monitor.POINTS["아산"][0] else []
        with patch("unified_settings.enabled", return_value={"asan"}), \
             patch.object(monitor, "load_state", return_value={"stores": old}), \
             patch.object(monitor, "save_state", side_effect=lambda s: saved.append(s)), \
             patch.object(monitor, "query", side_effect=query), \
             patch.object(monitor, "telegram", side_effect=lambda m: sent.append(m) or True), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            if query_error:
                with self.assertRaises(RuntimeError):
                    monitor.main()
            else:
                monitor.main()
        previews = [json.loads(line.split(":", 1)[1]) for line in output.getvalue().splitlines() if line.startswith("ASAN_CU_STOCK_ALERT_PREVIEW:")]
        return sent, saved, previews

    def test_initial_positive_only_legacy_sends(self):
        sent, saved, previews = self.run_monitor(3)
        self.assertEqual(len(sent), 1)
        self.assertIn("첫 재고 확인", sent[0])
        self.assertEqual(len(previews), 1)
        self.assertEqual(previews[0]["delivery"], "NOT_SENT")
        self.assertIn("— 3개", "".join(previews[0]["pages"]))
        self.assertEqual(len(saved), 1)

    def test_unchanged_stock_no_send(self):
        sent, saved, previews = self.run_monitor(3, previous=3, alerted=True)
        self.assertEqual(sent, [])
        self.assertEqual(len(previews), 1)
        self.assertEqual(len(saved), 1)

    def test_decrease_to_zero_one_legacy_send(self):
        sent, saved, previews = self.run_monitor(0, previous=3, alerted=True)
        self.assertEqual(len(sent), 1)
        self.assertIn("품절 확인", sent[0])
        self.assertIn("— 0개", "".join(previews[0]["pages"]))

    def test_initial_zero_not_alerted(self):
        sent, _, previews = self.run_monitor(0)
        self.assertEqual(sent, [])
        self.assertIn("— 0개", "".join(previews[0]["pages"]))

    def test_failed_queries_no_state_or_send(self):
        sent, saved, previews = self.run_monitor(3, query_error=True)
        self.assertEqual(sent, [])
        self.assertEqual(saved, [])
        self.assertEqual(len(previews), 1)
        self.assertNotIn("— 0개", "".join(previews[0]["pages"]))

    def test_exact_map_link_and_unknown_not_zero(self):
        snapshot = build_snapshot({"53982": {"stock": 2}, "40059": {"stock": 0}}, query_succeeded=True)
        pages = preview_asan_stock_messages(snapshot)
        joined = "\n".join(p.split("\n", 1)[1] for p in pages) if len(pages) > 1 else pages[0]
        for row in snapshot["candidates"]:
            if row["status"] in ("IN_STOCK", "ZERO_STOCK"):
                self.assertIn("https://map.naver.com/p/search/" + quote(row["address"], safe=""), joined)
        self.assertEqual(joined.count("확인 불가 (NOT_OBSERVED)"), 121)
        self.assertEqual(joined.count("네이버지도:"), 2)
        self.assertTrue(all(len(page) <= 4096 for page in pages))

if __name__ == "__main__":
    unittest.main()
