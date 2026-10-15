"""Synthetic regional audit tests; no network, state writes or alerts."""
import json
import unittest

from store_registry import test_manual_review_queue as fixtures
from store_registry.regional_audit import summarize, render_markdown
from store_registry.review_report import build_report

class RegionalAuditTests(unittest.TestCase):
    setUp = fixtures.QueueTests.setUp
    captures = fixtures.QueueTests.captures
    evidence = fixtures.QueueTests.evidence

    def test_confirmed_candidate_regional_counts(self):
        report = build_report(self.root, self.captures(), self.evidence(), fixtures.NOW)
        result = summarize(report)
        self.assertEqual(result["total_candidates"], 1)
        self.assertEqual(result["by_region"]["namwon"]["manual_review"], 1)
        self.assertEqual(result["by_region"]["jeju"]["total"], 0)
        self.assertEqual(result["repeated_capture"]["confirmed"], 1)
        self.assertEqual(result["approved_for_production"], 0)

    def test_evidence_shortfall_and_quarantine_reason(self):
        report = build_report(self.root, self.captures(), now=fixtures.NOW)
        result = summarize(report)
        self.assertEqual(result["evidence"]["missing"], 1)
        self.assertEqual(result["quarantine_reasons"]["independent_evidence_missing"], 1)
        self.assertEqual(result["by_region"]["namwon"]["quarantined"], 1)

    def test_missing_in_second_capture_is_not_closure(self):
        captures = self.captures()
        captures[1]["payload"]["stores"] = []
        result = summarize(build_report(self.root, captures, self.evidence(), fixtures.NOW))
        self.assertEqual(result["capture_change_observations"]["missing_in_one_capture"], 1)
        self.assertEqual(result["closure_candidates"], [])

    def test_identity_change_is_observed_not_approved(self):
        captures = self.captures()
        captures[1]["payload"]["stores"][0]["name"] = "변경점"
        result = summarize(build_report(self.root, captures, self.evidence(), fixtures.NOW))
        self.assertEqual(result["capture_change_observations"]["identity_changed"], 1)
        self.assertEqual(result["approved_for_production"], 0)

    def test_staleness_summary_and_markdown(self):
        from datetime import datetime, timezone
        report = build_report(self.root, self.captures(), self.evidence(),
                              datetime(2026, 10, 20, tzinfo=timezone.utc))
        result = summarize(report)
        self.assertEqual(result["freshness"]["stale"], 1)
        rendered = render_markdown(result)
        self.assertIn("namwon", rendered)
        self.assertIn("stale: 1", rendered)
        self.assertIn("Approved for production: 0", rendered)

    def test_duplicate_candidate_and_approval_rejected(self):
        report = build_report(self.root, self.captures(), self.evidence(), fixtures.NOW)
        report["items"].append(dict(report["items"][0]))
        with self.assertRaises(ValueError):
            summarize(report)
        report["items"].pop()
        report["items"][0]["approved_for_production"] = True
        with self.assertRaises(ValueError):
            summarize(report)

    def test_empty_report_is_valid(self):
        captures = self.captures()
        for capture in captures:
            capture["payload"]["stores"] = []
        result = summarize(build_report(self.root, captures, now=fixtures.NOW))
        self.assertEqual(result["total_candidates"], 0)
        self.assertEqual(sum(r["total"] for r in result["by_region"].values()), 0)


if __name__ == "__main__":
    unittest.main()
