"""Synthetic conversion and validation tests."""
import unittest
from store_registry import test_candidates as fixtures
from store_registry.convert_external import convert
from store_registry.intake import validate_document

DATE = "2026-10-15T00:00:00Z"


class ConversionTests(unittest.TestCase):
    setUp = fixtures.CandidateReviewTests.setUp

    def test_cu_new_existing_and_missing_fields(self):
        rows = [{"code": "123", "name": "신규", "address": "전북특별자치도 남원시 1"},
                {"code": "456", "address": "전북특별자치도 남원시 2"},
                {"code": "789", "name": "타지역", "address": "서울특별시 3"}]
        result = convert(self.root, "cu", DATE, {"stores": rows})
        self.assertEqual(result["report"]["source_rows"], 3)
        self.assertEqual(result["report"]["accepted_rows"], 1)
        self.assertEqual(result["report"]["rejected_rows"], 2)
        self.assertEqual(result["report"]["new_unverified"], 1)
        self.assertEqual(result["report"]["approved_for_production"], 0)
        validate_document(result["document"])

    def test_emart24_duplicate_ids_and_conflict(self):
        rows = [{"storeCode": "123", "storeName": "첫째", "address": "충청남도 아산시 1"},
                {"storeCode": "123", "storeName": "둘째", "address": "충청남도 아산시 2"}]
        report = convert(self.root, "emart24", DATE, {"stores": rows})["report"]
        self.assertEqual(report["statuses"],
                         {"duplicate_in_submission": 1, "pending_approval": 1})

    def test_reject_ambiguous_region(self):
        row = {"storeCode": "123", "storeName": "잘못된 주소",
               "address": "남원시와 전주시 사이"}
        result = convert(self.root, "emart24", DATE, {"stores": [row]})
        self.assertEqual(result["report"]["accepted_rows"], 0)
        self.assertEqual(result["report"]["rejected_rows"], 1)

    def test_bad_provider_and_payload_fail_closed(self):
        with self.assertRaises(ValueError):
            convert(self.root, "gs25", DATE, {"stores": []})
        with self.assertRaises(ValueError):
            convert(self.root, "cu", DATE, {"stores": {}})


if __name__ == "__main__":
    unittest.main()
