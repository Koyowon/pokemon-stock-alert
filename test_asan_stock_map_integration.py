"""Offline Asan snapshot/alert preview integration regression tests."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch
import cu_stock_monitor as monitor
from asan_stock_snapshot import build_snapshot
from asan_stock_message import format_asan_stock_message
from asan_stock_chunks import preview_asan_stock_messages


class AsanStockMapIntegrationTests(unittest.TestCase):
    def test_confirmed_stock_maps_unknown_separate(self):
        snapshot = build_snapshot({"53982": {"stock": 3}, "40059": {"stock": 0}}, query_succeeded=True)
        message = format_asan_stock_message(snapshot)
        self.assertIn("— 3개", message)
        self.assertIn("— 0개", message)
        self.assertEqual(message.count("https://map.naver.com/p/search/"), 2)
        self.assertEqual(message.count("확인 불가 (NOT_OBSERVED)"), 121)

    def test_absent_not_zero(self):
        message = format_asan_stock_message(build_snapshot({}, query_succeeded=True))
        self.assertNotIn("— 0개", message)
        self.assertNotIn("https://map.naver.com/p/search/", message)

    def test_pages_safe(self):
        pages = preview_asan_stock_messages(build_snapshot({"53982": {"stock": 3}}, query_succeeded=True))
        self.assertTrue(all(len(page) <= 4096 for page in pages))

    def test_monitor_does_not_send_extra_preview_alerts(self):
        sent, saved = [], []
        def fake_query(city, lat, lng):
            if city != "아산" or (lat, lng) != monitor.POINTS["아산"][0]:
                return []
            return [{"code": "53982", "name": "씨유 아산온천타운점",
                     "address": "충청남도 아산시 중앙로 27 (온천동)", "stock": 3, "city": "아산"}]
        with patch("unified_settings.enabled", return_value={"asan"}), \
             patch.object(monitor, "load_state", return_value={"stores": {}}), \
             patch.object(monitor, "save_state", side_effect=lambda state: saved.append(state)), \
             patch.object(monitor, "query", side_effect=fake_query), \
             patch.object(monitor, "telegram", side_effect=lambda msg: sent.append(msg) or True), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            monitor.main()
        lines = [line for line in output.getvalue().splitlines() if line.startswith("ASAN_CU_STOCK_ALERT_PREVIEW:")]
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0].split(":", 1)[1])
        self.assertEqual(payload["delivery"], "NOT_SENT")
        self.assertTrue(any("네이버지도:" in page for page in payload["pages"]))
        self.assertEqual(len(sent), 1)  # Existing stock-change alert only
        self.assertEqual(len(saved), 1)


if __name__ == "__main__":
    unittest.main()
