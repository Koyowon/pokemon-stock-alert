"""Synthetic no-network manual review queue regression tests."""
import unittest
from datetime import datetime, timezone

from store_registry import test_candidates as fixtures
from store_registry.manual_review_queue import queue
from store_registry.source_audit import OFFICIAL_PAGES

NOW = datetime(2026, 10, 15, 13, 0, tzinfo=timezone.utc)


class QueueTests(unittest.TestCase):
    setUp = fixtures.CandidateReviewTests.setUp

    def capture(self, date, rows=None, regions=None):
        if rows is None:
            rows = [{"code": "987654", "name": "새로운점",
                     "address": "전북특별자치도 남원시 1"}]
        return {"chain": "cu", "source_page": OFFICIAL_PAGES["cu"],
                "captured_at": date, "capture_method": "operator_supplied_export",
                "authorization_reference": "pending-permission",
                "coverage": {"scope": "partial", "regions": regions or ["namwon"],
                             "evidence": "operator-note"},
                "payload": {"stores": rows}}

    def captures(self):
        return [self.capture("2026-10-14T12:00:00Z"),
                self.capture("2026-10-15T12:00:00Z")]

    def evidence(self):
        base = {"chain": "cu", "store_id": "987654", "name": "새로운점",
                "address": "전북특별자치도 남원시 1", "region": "namwon"}
        return {"987654": [dict(base, source="directory", reference="ref-a"),
                            dict(base, source="operator-verification", reference="ref-b")]}

    def test_repeated_consistent_two_source_candidate_is_manual_only(self):
        result = queue(self.root, self.captures(), self.evidence(), NOW)
        self.assertEqual(result["counts"], {"manual_review": 1})
        self.assertEqual(result["approved_for_production"], 0)
        self.assertFalse(result["items"][0]["evidence_independently_verified"])

    def test_missing_evidence_quarantined(self):
        result = queue(self.root, self.captures(), now=NOW)
        self.assertEqual(result["counts"], {"quarantined": 1})
        self.assertIn("independent_evidence_missing", result["items"][0]["reasons"])

    def test_changed_identity_quarantined(self):
        captures = self.captures()
        captures[1]["payload"]["stores"][0]["name"] = "이름변경"
        result = queue(self.root, captures, self.evidence(), NOW)
        self.assertIn("identity_changed", result["items"][0]["reasons"])

    def test_missing_store_is_not_closure(self):
        captures = self.captures()
        captures[1]["payload"]["stores"] = []
        result = queue(self.root, captures, self.evidence(), NOW)
        self.assertEqual(result["closure_candidates"], [])
        self.assertIn("not_repeated", result["items"][0]["reasons"])

    def test_coverage_and_staleness_quarantine(self):
        captures = self.captures()
        captures[0]["coverage"]["regions"] = ["asan"]
        with self.assertRaises(ValueError):
            queue(self.root, captures, self.evidence(), NOW)
        captures = self.captures()
        result = queue(self.root, captures, self.evidence(),
                       datetime(2026, 10, 20, tzinfo=timezone.utc))
        self.assertIn("stale_capture", result["items"][0]["reasons"])

    def test_duplicate_capture_timestamp_rejected(self):
        captures = self.captures()
        captures[1]["captured_at"] = captures[0]["captured_at"]
        with self.assertRaises(ValueError):
            queue(self.root, captures, self.evidence(), NOW)


if __name__ == "__main__":
    unittest.main()
