"""Offline regression for cross-chain gap analysis. No network or alerts."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "offline_store_gap_analysis", Path(__file__).with_name("offline_store_gap_analysis.py")
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class GapTests(unittest.TestCase):
    def test_name_only_match_is_not_auto_assigned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = {
                "asan_cu_watch_registry.json": {"stores": [
                    {"registry_id": "1", "name": "CU 아산중앙점",
                     "cu_store_code": "", "product_barcode": module.TARGET},
                    {"registry_id": "2", "name": "CU 아산서부점",
                     "cu_store_code": "002", "product_barcode": module.TARGET},
                ]},
                "cu_stock_state.json": {"stores": {
                    "001": {"name": "씨유 아산중앙점", "city": "아산"},
                    "002": {"name": "아산서부점", "city": "아산"},
                }},
                "stores.json": {"stores": {
                    "e1": {"address": "전북특별자치도 전주시 완산구"},
                }},
                "emart24_jeonju_seed.json": {"stores": {"e1": {}, "e2": {}}},
                "unified_control.json": {"chains": {"emart24": {
                    "namwon": True, "asan": True, "jeonju": True, "jeju": False
                }}},
            }
            for name, obj in fixtures.items():
                (root / name).write_text(json.dumps(obj), encoding="utf-8")
            (root / "monitor.py").write_text(
                'PRODUCTS = {"30주년 셀레브레이션 팩": "8800286275732"}\n"limit": 100',
                encoding="utf-8",
            )
            (root / "cu_stock_monitor.py").write_text(
                '"offset": 0\n"size": 100', encoding="utf-8"
            )
            report = module.analyze(root)
            self.assertEqual(report["cu"]["missing"], 1)
            self.assertEqual(
                report["cu"]["potential_name_matches_for_manual_review"],
                [{"registry_id": "1", "candidate_codes": ["001"],
                  "status": "REVIEW_ONLY_DO_NOT_ASSIGN"}],
            )
            self.assertEqual(report["emart24"]["jeonju_seed_not_cached"], ["e2"])
            self.assertFalse(report["emart24"]["jeju_supported_in_monitor"])


if __name__ == "__main__":
    unittest.main()
