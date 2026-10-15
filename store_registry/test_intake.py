"""Offline external snapshot contract tests."""
import json
import tempfile
import unittest
from pathlib import Path

from store_registry import test_candidates as fixtures
from store_registry.intake import evaluate, validate_document


def document(stores=None):
    return {"schema_version": 1, "snapshots": [{
        "chain": "cu", "region": "namwon", "source": "cu_parsed_inventory",
        "captured_at": "2026-10-15T00:00:00Z",
        "payload": {"stores": stores if stores is not None else [
            {"code": "00123", "name": "신규CU",
             "address": "전북특별자치도 남원시 도통동 1"}]}}]}


class IntakeTests(unittest.TestCase):
    setUp = fixtures.CandidateReviewTests.setUp

    def test_file_intake_is_read_only_and_not_approved(self):
        path = self.root / "discovery.json"
        path.write_text(json.dumps(document(), ensure_ascii=False), encoding="utf-8")
        before = path.read_bytes()
        result = evaluate(self.root, path)
        self.assertEqual(result["new_unverified"], 1)
        self.assertEqual(result["approved_for_production"], 0)
        self.assertEqual(result["eligible_for_staged_review"], 0)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(len(result["input_sha256"]), 64)

    def test_unknown_fields_and_self_approval_rejected(self):
        value = document()
        value["snapshots"][0]["source_verified"] = True
        with self.assertRaises(ValueError):
            validate_document(value)

    def test_wrong_schema_and_payload_rejected(self):
        value = document()
        value["schema_version"] = 2
        with self.assertRaises(ValueError):
            validate_document(value)
        value = document()
        value["snapshots"][0]["payload"] = {"stores": {}}
        with self.assertRaises(ValueError):
            validate_document(value)

    def test_oversized_batch_and_invalid_date_rejected(self):
        value = document()
        value["snapshots"] *= 33
        with self.assertRaises(ValueError):
            validate_document(value)
        value = document()
        value["snapshots"][0]["captured_at"] = "yesterday"
        with self.assertRaises(ValueError):
            validate_document(value)


if __name__ == "__main__":
    unittest.main()
