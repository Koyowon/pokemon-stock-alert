"""Regression checks for saved-main offline audit."""
import json
import unittest
from store_registry import test_candidates as fixtures
from store_registry.audit_saved_discovery import audit


class SavedAuditTests(unittest.TestCase):
    setUp = fixtures.CandidateReviewTests.setUp

    def test_saved_data_is_not_new_discovery(self):
        cu_path = self.root / "cu_stock_state.json"
        em_path = self.root / "stores.json"
        seed_path = self.root / "emart24_jeonju_seed.json"
        cu_path.write_text(json.dumps({"stores": {"0001": {
            "name": "기존CU", "address": "전북특별자치도 남원시 1", "city": "남원"}}},
            ensure_ascii=False), encoding="utf-8")
        em = {"stores": {"0002": {"name": "기존이마트",
                                     "address": "전북특별자치도 전주시 완산구 2"}}}
        em_path.write_text(json.dumps(em, ensure_ascii=False), encoding="utf-8")
        seed_path.write_text(json.dumps(em, ensure_ascii=False), encoding="utf-8")
        result = audit(self.root)
        self.assertEqual(result["new_candidates"], 0)
        self.assertEqual(result["approved_for_production"], 0)
        self.assertTrue(result["inputs_unchanged"])
        self.assertTrue(result["network_blocked"])


if __name__ == "__main__":
    unittest.main()
