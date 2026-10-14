"""Static offline gate regression: flags alone never enable Jeju."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "offline_emart24_integration_gate", Path(__file__).with_name("offline_emart24_integration_gate.py")
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class GateTests(unittest.TestCase):
    def test_current_monitor_is_not_jeju_ready(self):
        src = ('PRODUCTS = {"30주년": "8800286275732"}\n'
               'REGIONS = {"남원": "남원시"}\n'
               'REGION_IDS = {"남원": "namwon"}\n'
               'qty < old\nqty == 0\nif qty is None:\n    continue\n'
               'consecutive_failures >= 3')
        result = gate.inspect_monitor(src)
        self.assertFalse(result["jeju_region_declared"])
        self.assertFalse(result["jeju_offline_integration_ready"])

    def test_valid_regions_still_cannot_activate_without_integration(self):
        src = ('PRODUCTS = {"30주년": "8800286275732"}\n'
               'REGIONS = {"제주": "제주시"}\n'
               'REGION_IDS = {"제주": "jeju"}\n'
               'def f(qty, old):\n'
               '    if qty is None:\n        return\n'
               '    if qty < old:\n'
               '        if qty == 0:\n            return\n'
               '    if consecutive_failures >= 3:\n        return\n')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "monitor.py"
            p.write_text(src, encoding="utf-8")
            result = gate.validate_before_merge(p, {"ready": True})
            self.assertTrue(result["jeju_region_declared"])
            self.assertFalse(result["can_activate_jeju"])

    def test_extra_product_fails_scope(self):
        src = ('PRODUCTS = {"30주년": "8800286275732", "other": "111"}\n'
               'REGIONS = {}\nREGION_IDS = {}\n')
        self.assertFalse(gate.inspect_monitor(src)["only_30th_product"])


if __name__ == "__main__":
    unittest.main()
