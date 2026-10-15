"""No-network source manifest and delta regression tests."""
import unittest
from store_registry import test_candidates as fixtures
from store_registry.source_audit import assess, OFFICIAL_PAGES


class SourceAuditTests(unittest.TestCase):
    setUp = fixtures.CandidateReviewTests.setUp

    def manifest(self):
        return {
            "chain": "cu", "source_page": OFFICIAL_PAGES["cu"],
            "captured_at": "2026-10-01T00:00:00Z",
            "capture_method": "operator_supplied_export",
            "authorization_reference": "manual-review-pending",
            "payload": {"stores": [
                {"code": "123", "name": "신규", "address": "전북특별자치도 남원시 1"}]},
        }

    def test_unverified_source_never_self_approves(self):
        result = assess(self.root, self.manifest())
        self.assertFalse(result["authorization_independently_verified"])
        self.assertEqual(result["approved_for_production"], 0)
        self.assertEqual(result["changes"]["added"], ["123"])
        self.assertEqual(result["conversion_report"]["new_unverified"], 1)

    def test_repeat_snapshot_no_changes(self):
        first = assess(self.root, self.manifest())
        second = assess(self.root, self.manifest(), first["current"])
        self.assertEqual(second["changes"], {"added": [], "removed": [], "changed": []})
        self.assertEqual(first["input_sha256"], second["input_sha256"])

    def test_changed_name_and_removed_code(self):
        first = assess(self.root, self.manifest())
        manifest = self.manifest()
        manifest["payload"]["stores"][0]["name"] = "다른 이름"
        second = assess(self.root, manifest, first["current"])
        self.assertEqual(second["changes"]["changed"], ["123"])
        empty = self.manifest()
        empty["payload"]["stores"] = []
        third = assess(self.root, empty, first["current"])
        self.assertEqual(third["changes"]["removed"], ["123"])

    def test_source_spoofing_and_automated_capture_rejected(self):
        manifest = self.manifest()
        manifest["source_page"] = "https://example.com/official"
        with self.assertRaises(ValueError):
            assess(self.root, manifest)
        manifest = self.manifest()
        manifest["capture_method"] = "automated_scrape"
        with self.assertRaises(ValueError):
            assess(self.root, manifest)

    def test_manifest_cannot_claim_approval(self):
        manifest = self.manifest()
        manifest["approved_for_production"] = True
        with self.assertRaises(ValueError):
            assess(self.root, manifest)


if __name__ == "__main__":
    unittest.main()
