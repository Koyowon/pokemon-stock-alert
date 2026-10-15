"""Offline adapters regression tests, synthetic provider snapshots only."""
import unittest
from store_registry.discovery_adapters import normalize_saved, compare_saved
from store_registry import test_candidates as fixtures


class DiscoveryAdapterTests(unittest.TestCase):
    setUp = fixtures.CandidateReviewTests.setUp

    def test_cu_parsed_discovery_and_strict_region(self):
        data = {"stores": [
            {"code": "0023", "name": "신규CU", "address": "전북특별자치도 남원시 도통동 1", "stock": 0},
            {"code": "0024", "name": "외부", "address": "서울특별시 종로구 1"},
            {"code": "ABC", "name": "무효", "address": "전북특별자치도 남원시 2"},
        ]}
        rows = normalize_saved("cu", "namwon", data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["store_id"], "0023")
        self.assertNotIn("stock", rows[0])
        self.assertEqual(compare_saved(self.root, "cu", "namwon", data)["counts"],
                         {"pending_approval": 1})

    def test_emart24_mapping_and_existing_comparison(self):
        data = {"stores": {
            "E1": {"name": "기존이마트", "address": "전주시 2"},
            "00077": {"name": "신규", "address": "전북특별자치도 전주시 완산구 3"},
        }}
        # Existing synthetic E1 has a nonnumeric code and is intentionally filtered.
        rows = normalize_saved("emart24", "jeonju", data)
        self.assertEqual([x["store_id"] for x in rows], ["00077"])
        self.assertEqual(compare_saved(self.root, "emart24", "jeonju", data)["counts"],
                         {"pending_approval": 1})

    def test_invalid_payload_and_unsupported_provider_fail_closed(self):
        with self.assertRaises(ValueError):
            normalize_saved("gs25", "namwon", {"stores": []})
        with self.assertRaises(ValueError):
            normalize_saved("cu", "namwon", {"stores": {}})
        with self.assertRaises(ValueError):
            normalize_saved("emart24", "namwon", [])

    def test_duplicate_candidate_detected(self):
        row = {"storeCode": "123", "storeName": "신규", "address": "충청남도 아산시 1"}
        result = compare_saved(self.root, "emart24", "asan", {"stores": [row, row]})
        self.assertEqual(result["counts"],
                         {"duplicate_in_submission": 1, "pending_approval": 1})
        self.assertEqual(result["approved_for_production"], 0)


if __name__ == "__main__":
    unittest.main()
