"""Offline regression checks for the coverage audit. No API, Actions, or Telegram."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import offline_chain_coverage_audit as audit_module


class CoverageAuditTests(unittest.TestCase):
    def test_offline_fixtures_and_product_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "asan_cu_watch_registry.json": {"stores": [
                    {"registry_id": "A", "cu_store_code": "123", "product_barcode": audit_module.TARGET},
                    {"registry_id": "B", "cu_store_code": "", "product_barcode": audit_module.TARGET},
                ]},
                "stores.json": {"stores": {
                    "e1": {"address": "충청남도 아산시"}, "e2": {"address": "전주시"}
                }},
                "unified_control.json": {"chains": {"emart24": {
                    "namwon": True, "asan": True, "jeonju": True, "jeju": False
                }}},
                "emart24_jeonju_seed.json": {"stores": {"e2": {}, "e3": {}}},
            }
            for name, obj in files.items():
                (root / name).write_text(json.dumps(obj), encoding="utf-8")
            (root / "cu_stock_monitor.py").write_text(
                'BARCODE = "8800286275732"\n"offset": 0\n"size": 100\nquantity < previous\nquantity == 0',
                encoding="utf-8",
            )
            (root / "monitor.py").write_text(
                'PRODUCTS = {"30주년 셀레브레이션 팩": "8800286275732"}\nqty < old\nqty == 0',
                encoding="utf-8",
            )
            with patch.object(audit_module, "ROOT", root):
                result = audit_module.audit()
            self.assertEqual(result["cu_asan"]["candidate_count"], 2)
            self.assertEqual(result["cu_asan"]["code_missing"], 1)
            self.assertEqual(result["emart24"]["jeonju_seed_missing_in_cache"], 1)
            self.assertEqual(result["emart24"]["cached_by_city"], {"아산": 1, "전주": 1})
            self.assertTrue(result["static_checks"]["cu_decrease_and_sold_out"])
            self.assertTrue(result["static_checks"]["emart24_decrease_and_sold_out"])
            self.assertFalse(result["static_checks"]["emart24_jeju_supported"])


if __name__ == "__main__":
    unittest.main()
