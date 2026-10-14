"""Offline Emart24 Jeju seed readiness regression. No API or alerts."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "jeju_plan", Path(__file__).with_name("offline_emart24_jeju_plan.py")
)
plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan)


class JejuPlanTests(unittest.TestCase):
    def setUp(self):
        self.valid = {
            "version": 1, "region_id": "jeju", "product_barcode": plan.TARGET_BARCODE,
            "stores": {"01234": {
                "name": "제주테스트점",
                "address": "제주특별자치도 제주시 테스트로 1",
                "evidence": "fixture-only",
            }},
        }

    def test_verified_seed_accepts_fixture(self):
        self.assertEqual(len(plan.validate_seed(self.valid)), 1)

    def test_empty_seed_fails_closed(self):
        self.valid["stores"] = {}
        with self.assertRaises(ValueError):
            plan.validate_seed(self.valid)

    def test_wrong_barcode_fails_closed(self):
        self.valid["product_barcode"] = "OTHER"
        with self.assertRaises(ValueError):
            plan.validate_seed(self.valid)

    def test_missing_evidence_fails_closed(self):
        del self.valid["stores"]["01234"]["evidence"]
        with self.assertRaises(ValueError):
            plan.validate_seed(self.valid)

    def test_non_jeju_address_fails_closed(self):
        self.valid["stores"]["01234"]["address"] = "충청남도 아산시 테스트로 1"
        with self.assertRaises(ValueError):
            plan.validate_seed(self.valid)

    def test_flag_does_not_enable_missing_seed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cfg = root / "config.json"
            cfg.write_text(json.dumps({"chains": {"emart24": {"jeju": True}}}), encoding="utf-8")
            self.assertEqual(
                plan.readiness(root / "missing.json", cfg)["reason"], "NO_VERIFIED_SEED"
            )

    def test_valid_seed_is_only_offline_ready(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cfg, seed = root / "config.json", root / "seed.json"
            cfg.write_text(json.dumps({"chains": {"emart24": {"jeju": False}}}), encoding="utf-8")
            seed.write_text(json.dumps(self.valid), encoding="utf-8")
            self.assertEqual(plan.readiness(seed, cfg), {
                "ready": True, "reason": "OFFLINE_SEED_VALID_ONLY",
                "enabled": False, "store_count": 1,
            })


if __name__ == "__main__":
    unittest.main()
