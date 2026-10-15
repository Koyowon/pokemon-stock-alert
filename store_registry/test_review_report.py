"""Synthetic read-only report tests; no network, disk writes or notifications."""
import json
import unittest

from store_registry import test_manual_review_queue as queue_fixtures
from store_registry.review_report import build_report, render_json, render_markdown


class ReportTests(unittest.TestCase):
    setUp = queue_fixtures.QueueTests.setUp
    capture = queue_fixtures.QueueTests.capture
    captures = queue_fixtures.QueueTests.captures
    evidence = queue_fixtures.QueueTests.evidence
    def test_json_report_contains_review_fields_and_no_approval(self):
        report = build_report(self.root, self.captures(), self.evidence(), queue_fixtures.NOW)
        data = json.loads(render_json(report))
        self.assertEqual(data["approved_for_production"], 0)
        self.assertFalse(data["automatic_registration"])
        item = data["items"][0]
        self.assertEqual(item["store_id"], "987654")
        self.assertEqual(item["region"], "namwon")
        self.assertEqual(item["repeated_capture"], "confirmed")
        self.assertEqual(len(item["evidence"]), 2)
        self.assertFalse(item["evidence_independently_verified"])

    def test_markdown_reports_quarantine_and_next_steps(self):
        report = build_report(self.root, self.captures(), now=NOW)
        markdown = render_markdown(report)
        self.assertIn("987654", markdown)
        self.assertIn("independent_evidence_missing", markdown)
        self.assertIn("Supply two independently checkable sources", markdown)
        self.assertIn("Production approvals: 0", markdown)

    def test_stale_capture_is_visible(self):
        from datetime import datetime, timezone
        report = build_report(self.root, self.captures(), self.evidence(),
                              datetime(2026, 10, 20, tzinfo=timezone.utc))
        self.assertEqual(report["items"][0]["freshness"], "stale")
        self.assertIn("stale_capture", report["items"][0]["quarantine_reasons"])

    def test_missing_capture_not_marked_closed(self):
        captures = self.captures()
        captures[1]["payload"]["stores"] = []
        report = build_report(self.root, captures, self.evidence(), queue_fixtures.NOW)
        self.assertEqual(report["closure_candidates"], [])
        self.assertEqual(report["items"][0]["repeated_capture"], "unconfirmed")
        self.assertIn("not_repeated", report["items"][0]["quarantine_reasons"])

    def test_markdown_escapes_pipe(self):
        report = build_report(self.root, self.captures(), self.evidence(), queue_fixtures.NOW)
        report["items"][0]["name"] = "Name | Other"
        self.assertIn("Name \\| Other", render_markdown(report))


if __name__ == "__main__":
    unittest.main()
