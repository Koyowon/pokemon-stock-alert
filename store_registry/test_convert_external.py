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
        self.assertEqual(report["accepted_rows"], 0)
        self.assertEqual(report["rejected_rows"], 2)
        self.assertTrue(all("submission_identity_conflict" in r["reasons"] for r in report["rejected"]))

    def test_reject_ambiguous_region(self):
        row = {"storeCode": "123", "storeName": "잘못된 주소",
               "address": "남원시와 전주시 사이"}
        result = convert(self.root, "emart24", DATE, {"stores": [row]})
        self.assertEqual(result["report"]["accepted_rows"], 0)
        self.assertEqual(result["report"]["rejected_rows"], 1)


    def test_identical_duplicates_both_quarantined(self):
        row = {"storeCode": "123", "storeName": "같은점", "address": "충청남도 아산시 1"}
        report = convert(self.root, "emart24", DATE, {"stores": [row, row]})["report"]
        self.assertEqual(report["rejected_rows"], 2)
        self.assertEqual(report["accepted_rows"], 0)

    def test_existing_code_with_changed_identity_quarantined(self):
        from store_registry.build_registry import build
        old = next(r for r in build(self.root)["records"] if r["chain"] == "cu")
        row = {"code": old["store_id"], "name": "변경된 이름",
               "address": "전북특별자치도 남원시 다른길 9"}
        report = convert(self.root, "cu", DATE, {"stores": [row]})["report"]
        self.assertEqual(report["accepted_rows"], 0)
        self.assertIn("existing_identity_conflict", report["rejected"][0]["reasons"])

    def test_cu_region_marker_without_prefix_quarantined(self):
        row = {"code": "999", "name": "위치 모호", "address": "임의 주소 남원시 도통동"}
        report = convert(self.root, "cu", DATE, {"stores": [row]})["report"]
        self.assertEqual(report["accepted_rows"], 0)
        self.assertIn("adapter_region_prefix_mismatch", report["rejected"][0]["reasons"])

    def test_row_accounting_for_mixed_valid_invalid(self):
        rows = [{"storeCode": "123", "storeName": "정상", "address": "충청남도 아산시 1"},
                {"storeCode": "abc", "storeName": "오류", "address": "충청남도 아산시 2"},
                {"storeCode": "555", "storeName": "", "address": "충청남도 아산시 3"}]
        report = convert(self.root, "emart24", DATE, {"stores": rows})["report"]
        self.assertEqual(report["source_rows"], report["accepted_rows"] + report["rejected_rows"])

    def test_bad_provider_and_payload_fail_closed(self):
        with self.assertRaises(ValueError):
            convert(self.root, "gs25", DATE, {"stores": []})
        with self.assertRaises(ValueError):
            convert(self.root, "cu", DATE, {"stores": {}})


if __name__ == "__main__":
    unittest.main()
