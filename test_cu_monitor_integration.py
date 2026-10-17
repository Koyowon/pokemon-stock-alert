"""Offline CU monitor integration tests. Run: python -m unittest -v test_cu_monitor_integration
All network, Telegram, and state I/O are patched.
"""
import copy
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
import cu_stock_monitor as monitor


def entry(code="53451", stock=2, name="남원금동점", address="전북특별자치도 남원시 서문로 67"):
    return {"code": code, "name": name, "address": address, "stock": stock, "city": "남원"}


class MonitorIntegration(unittest.TestCase):
    def setUp(self):
        self.saved = []
        self.sent = []
        self.initial = {"stores": {}}
        self.directory = {"53451": {"name": "남원금동점", "address": "전북특별자치도 남원시 서문로 67"}}
        self.patches = [
            patch.object(monitor, "POINTS", {"남원": [(35.416, 127.390)]}),
            patch.object(monitor, "load_state", side_effect=lambda: copy.deepcopy(self.initial)),
            patch.object(monitor, "load_verified_directory", side_effect=lambda: copy.deepcopy(self.directory)),
            patch.object(monitor, "load_enabled_regions", return_value={"namwon"}),
            patch("unified_settings.enabled", return_value={"namwon"}),
            patch.object(monitor, "telegram", side_effect=lambda message: self.sent.append(message) or True),
            patch("urllib.request.urlopen", side_effect=AssertionError("Network access forbidden in offline tests")),
            patch.object(monitor, "save_state", side_effect=lambda state: self.saved.append(copy.deepcopy(state))),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def run_main(self, response=None, error=None):
        with patch.object(monitor, "query", side_effect=error if error else lambda *args: response):
            with redirect_stdout(io.StringIO()) as output:
                if error:
                    with self.assertRaises(RuntimeError):
                        monitor.main()
                else:
                    monitor.main()
        return output.getvalue()

    def test_first_positive_alert(self):
        self.run_main([entry()])
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.saved[0]["stores"]["53451"]["stock"], 2)

    def test_missing_store_not_zero(self):
        self.initial["stores"]["53451"] = {"name": "남원금동점", "address": "전북특별자치도 남원시 서문로 67", "city": "남원", "stock": 4, "alerted": True}
        output = self.run_main([])
        self.assertEqual(self.saved[0], self.initial)
        self.assertFalse(self.sent)
        self.assertIn("OFFICIAL_DIRECTORY_NOT_OBSERVED: 1", output)

    def test_all_queries_failed_state_unchanged(self):
        self.run_main(error=TimeoutError("offline simulated failure"))
        self.assertFalse(self.saved)
        self.assertFalse(self.sent)

    def test_identity_conflict_holds_stock(self):
        self.run_main([entry(name="다른매장")])
        self.assertEqual(self.saved[0]["stores"], {})
        self.assertFalse(self.sent)

    def test_telegram_failure_does_not_save_unalerted_stock(self):
        with patch.object(monitor, "telegram", return_value=False):
            self.run_main([entry()])
        self.assertEqual(self.saved[0]["stores"], {})

    def test_zero_inventory_is_not_first_positive(self):
        self.run_main([entry(stock=0)])
        self.assertFalse(self.sent)
        self.assertEqual(self.saved[0]["stores"]["53451"]["stock"], 0)

    def test_stock_decrease_notification(self):
        self.initial["stores"]["53451"] = {"name": "남원금동점", "address": "전북특별자치도 남원시 서문로 67", "city": "남원", "stock": 5, "alerted": True}
        self.run_main([entry(stock=2)])
        self.assertEqual(len(self.sent), 1)
        self.assertIn("재고 감소", self.sent[0])

    def test_disabled_regions_never_queried(self):
        with patch("unified_settings.enabled", return_value=set()):
            with patch.object(monitor, "query", side_effect=AssertionError("network forbidden")):
                self.run_main([])
        self.assertFalse(self.saved)
        self.assertFalse(self.sent)


if __name__ == "__main__":
    unittest.main()
