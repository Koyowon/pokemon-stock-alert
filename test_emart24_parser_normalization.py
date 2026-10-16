"""Offline-only tests. No API, Telegram, or state-file writes."""
import unittest
from unittest.mock import patch
import monitor


class InventoryNormalizationTests(unittest.TestCase):
    def test_store_code(self):
        codes = ["01073", "22906"]
        for raw in ("01073", 1073, "1073", "001073"):
            with self.subTest(raw=raw):
                self.assertEqual(monitor.normalize_inventory_code(raw, codes), "01073")
        self.assertEqual(monitor.normalize_inventory_code("22906", codes), "22906")

    def test_code_collision_and_invalid(self):
        for raw, known in [
            (1073, ["01073", "1073"]),
            ("01073", ["01073", "1073"]),
            (-1, ["01073"]),
            (True, ["1"]),
            (1.0, ["1"]),
            ("-1073", ["01073"]),
            ("abc", ["01073"]),
            (None, ["01073"]),
            ("", ["01073"]),
            (" 1073 ", ["01073"]),
            ("１０７３", ["01073"]),
        ]:
            with self.subTest(raw=raw, known=known):
                self.assertIsNone(monitor.normalize_inventory_code(raw, known))

    def test_quantity_valid(self):
        for raw, expected in [(0, 0), (3, 3), ("0", 0), ("003", 3), (" 3 ", 3)]:
            with self.subTest(raw=raw):
                self.assertEqual(monitor.normalize_inventory_quantity(raw), expected)

    def test_quantity_invalid(self):
        for raw in [-1, "-1", "3개", "", " ", None, True, False, 3.0, "3.0", "１", "1e2"]:
            with self.subTest(raw=raw):
                self.assertIsNone(monitor.normalize_inventory_quantity(raw))

    def test_stock_integration_no_network(self):
        codes = ["01073", "22906"]
        payload = {"stores": [{"bizNo": 1073, "bizQty": "003"},
                              {"bizNo": "22906", "bizQty": 0}]}
        with patch.object(monitor, "api", return_value=payload), patch.object(monitor.time, "sleep"):
            values, statuses = monitor.stock("fake-product", codes)
        self.assertEqual(values, {"01073": 3, "22906": 0})
        self.assertEqual(statuses, {"01073": "OK", "22906": "OK"})

    def test_stock_rejects_ambiguous_and_invalid(self):
        codes = ["01073", "1073", "22906"]
        payload = {"stores": [{"bizNo": 1073, "bizQty": 7},
                              {"bizNo": "22906", "bizQty": "-2"}]}
        with patch.object(monitor, "api", return_value=payload), patch.object(monitor.time, "sleep"):
            values, statuses = monitor.stock("fake-product", codes)
        self.assertEqual(values, {})
        self.assertEqual(statuses["22906"], "NULL_OR_INVALID_QTY")
        self.assertEqual(statuses["01073"], "MISSING_IN_RESPONSE")
        self.assertEqual(statuses["1073"], "MISSING_IN_RESPONSE")


    def test_duplicate_same_quantity_allowed(self):
        payload = {"stores": [{"bizNo": "01073", "bizQty": 3},
                              {"bizNo": 1073, "bizQty": "003"}]}
        with patch.object(monitor, "api", return_value=payload), patch.object(monitor.time, "sleep"):
            values, statuses = monitor.stock("fake-product", ["01073"])
        self.assertEqual(values, {"01073": 3})
        self.assertEqual(statuses["01073"], "OK")

    def test_duplicate_conflicts_both_orders(self):
        for first, second in [(3, 7), (7, 3)]:
            with self.subTest(first=first, second=second):
                payload = {"stores": [{"bizNo": "01073", "bizQty": first},
                                      {"bizNo": 1073, "bizQty": second}]}
                with patch.object(monitor, "api", return_value=payload), patch.object(monitor.time, "sleep"):
                    values, statuses = monitor.stock("fake-product", ["01073"])
                self.assertNotIn("01073", values)
                self.assertEqual(statuses["01073"], "CONFLICTING_QTY")

    def test_valid_and_unknown_conflict_both_orders(self):
        for first, second in [(3, None), (None, 3)]:
            with self.subTest(first=first, second=second):
                payload = {"stores": [{"bizNo": "01073", "bizQty": first},
                                      {"bizNo": "01073", "bizQty": second}]}
                with patch.object(monitor, "api", return_value=payload), patch.object(monitor.time, "sleep"):
                    values, statuses = monitor.stock("fake-product", ["01073"])
                self.assertNotIn("01073", values)
                self.assertEqual(statuses["01073"], "CONFLICTING_QTY")

    def test_conflict_sticky_after_valid_response(self):
        payload = {"stores": [{"bizNo": "01073", "bizQty": 3},
                              {"bizNo": "01073", "bizQty": 7},
                              {"bizNo": "01073", "bizQty": 3}]}
        with patch.object(monitor, "api", return_value=payload), patch.object(monitor.time, "sleep"):
            values, statuses = monitor.stock("fake-product", ["01073"])
        self.assertEqual(values, {})
        self.assertEqual(statuses["01073"], "CONFLICTING_QTY")

    def test_unknown_duplicates_do_not_become_zero(self):
        payload = {"stores": [{"bizNo": "01073", "bizQty": None},
                              {"bizNo": "01073", "bizQty": "bad"}]}
        with patch.object(monitor, "api", return_value=payload), patch.object(monitor.time, "sleep"):
            values, statuses = monitor.stock("fake-product", ["01073"])
        self.assertEqual(values, {})
        self.assertEqual(statuses["01073"], "NULL_OR_INVALID_QTY")


if __name__ == "__main__":
    unittest.main()
