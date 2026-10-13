"""Offline CU monitor regression tests. All I/O is mocked."""
import contextlib
import io
import unittest
from unittest.mock import patch

import cu_stock_monitor as monitor
import cu_asan_registry as registry

REGIONS = ("남원", "아산", "전주", "제주")
ADDRESSES = {
    "남원": "전북특별자치도 남원시 시민로 10",
    "아산": "충청남도 아산시 시민로 10",
    "전주": "전북특별자치도 전주시 완산구 시민로 10",
    "제주": "제주특별자치도 제주시 시민로 10",
}

def store(city, stock=3):
    return {"code": str(10001 + REGIONS.index(city)),
            "name": "CU 테스트" + city, "address": ADDRESSES[city],
            "stock": stock, "city": city}

class CUAlertIsolationTests(unittest.TestCase):
    def run_monitor(self, *, diagnostic_error=None, regions=REGIONS,
                    stocks=None, initial=None, fail_all=False,
                    telegram_success=True):
        stocks = stocks or {}
        messages, saved, calls = [], [], []
        original = {"stores": dict(initial or {})}
        def fake_query(city, lat, lng):
            calls.append(city)
            if fail_all:
                raise RuntimeError("simulated query failure")
            if (lat, lng) != monitor.POINTS[city][0]:
                return []
            return [store(city, stocks.get(city, 3))]
        def fake_telegram(message):
            messages.append(message)
            return telegram_success
        def fake_diagnostic(*args, **kwargs):
            if diagnostic_error:
                raise diagnostic_error
            return []
        output = io.StringIO()
        with patch.object(monitor, "POINTS",
                          {city: monitor.POINTS[city][:1] for city in REGIONS}), \
             patch.object(monitor, "load_enabled_regions", return_value={monitor.REGION_IDS[city] for city in regions}), \
             patch("unified_settings.enabled", return_value={monitor.REGION_IDS[city] for city in regions}), \
             patch.object(monitor, "query", side_effect=fake_query), \
             patch.object(monitor, "load_state", return_value=original), \
             patch.object(monitor, "save_state", side_effect=lambda state: saved.append(
                 {"stores": {key: dict(value) for key, value in state["stores"].items()}})), \
             patch.object(monitor, "telegram", side_effect=fake_telegram), \
             patch.object(registry, "summarize_observations", side_effect=fake_diagnostic), \
             contextlib.redirect_stdout(output):
            if fail_all:
                with self.assertRaisesRegex(RuntimeError, "All CU queries failed"):
                    monitor.main()
            else:
                monitor.main()
        return messages, saved, calls, output.getvalue()

    def test_diagnostic_value_error_does_not_block_four_regions(self):
        messages, saved, calls, output = self.run_monitor(
            diagnostic_error=ValueError("bad registry"))
        self.assertEqual(len(messages), 4)
        self.assertEqual(len(saved), 1)
        self.assertEqual(len(saved[0]["stores"]), 4)
        self.assertIn("ASAN_CU_DIAGNOSTIC_ERROR: ValueError", output)
        for city in REGIONS:
            self.assertIn(city, calls)
            self.assertTrue(any("지역: " + city in msg for msg in messages))

    def test_missing_registry_does_not_block_alerts(self):
        messages, saved, _, output = self.run_monitor(
            diagnostic_error=FileNotFoundError("registry missing"))
        self.assertEqual(len(messages), 4)
        self.assertEqual(len(saved[0]["stores"]), 4)
        self.assertIn("ASAN_CU_DIAGNOSTIC_ERROR: FileNotFoundError", output)

    def test_normal_diagnostic_preserves_four_region_alerts(self):
        messages, saved, _, output = self.run_monitor()
        self.assertEqual(len(messages), 4)
        self.assertEqual(len(saved[0]["stores"]), 4)
        self.assertNotIn("ASAN_CU_DIAGNOSTIC_ERROR", output)

    def test_namwon_increase_and_jeonju_zero_stock(self):
        old = {store("남원")["code"]: {**store("남원", 1), "alerted": True},
               store("전주")["code"]: {**store("전주", 2), "alerted": True}}
        messages, saved, _, _ = self.run_monitor(
            diagnostic_error=ValueError("bad registry"),
            stocks={"남원": 4, "전주": 0}, initial=old)
        self.assertTrue(any("재고 입고/증가" in m and "지역: 남원" in m for m in messages))
        self.assertTrue(any("품절 확인" in m and "지역: 전주" in m for m in messages))
        self.assertEqual(saved[0]["stores"][store("전주")["code"]]["stock"], 0)

    def test_asan_disabled_skips_diagnostic(self):
        messages, saved, calls, output = self.run_monitor(
            regions=("남원", "전주", "제주"),
            diagnostic_error=ValueError("must not run"))
        self.assertEqual(len(messages), 3)
        self.assertNotIn("아산", calls)
        self.assertNotIn("ASAN_CU_DIAGNOSTIC_ERROR", output)
        self.assertEqual(len(saved[0]["stores"]), 3)

    def test_all_queries_failed_preserves_state(self):
        messages, saved, _, output = self.run_monitor(
            fail_all=True, diagnostic_error=ValueError("bad registry"))
        self.assertFalse(messages)
        self.assertFalse(saved)
        self.assertIn("ASAN_CU_DIAGNOSTIC_ERROR", output)

    def test_failed_telegram_does_not_save_unsent_stores(self):
        messages, saved, _, output = self.run_monitor(
            diagnostic_error=ValueError("bad registry"), telegram_success=False)
        self.assertEqual(len(messages), 4)
        self.assertEqual(saved[0]["stores"], {})
        self.assertIn("ALERT_PENDING:", output)

    def test_duplicate_observation_conflict_is_held(self):
        # Conflicting repeated observations for one store must not notify or persist.
        first = store("아산", 2)
        second = store("아산", 4)
        messages, saved = [], []
        count = [0]
        def query(city, lat, lng):
            if city != "아산":
                return []
            count[0] += 1
            return [first if count[0] == 1 else second]
        with patch.object(monitor, "POINTS", {"아산": monitor.POINTS["아산"][:2]}), \
             patch.object(monitor, "load_enabled_regions", return_value={"asan"}), \
             patch("unified_settings.enabled", return_value={"asan"}), \
             patch.object(monitor, "query", side_effect=query), \
             patch.object(monitor, "load_state", return_value={"stores": {}}), \
             patch.object(monitor, "save_state", side_effect=lambda state: saved.append(state)), \
             patch.object(monitor, "telegram", side_effect=lambda msg: messages.append(msg)), \
             patch.object(registry, "summarize_observations", return_value=[]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            monitor.main()
        self.assertFalse(messages)
        self.assertEqual(saved[0]["stores"], {})
        self.assertIn("STOCK_CONFLICT:", output.getvalue())

if __name__ == "__main__":
    unittest.main()
