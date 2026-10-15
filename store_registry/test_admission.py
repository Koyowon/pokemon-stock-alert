"""Offline production-admission regression tests."""
import unittest
from store_registry import test_candidates as fixtures

# Reuse only the fixture setup, not inherited test methods.
from store_registry.admission import plan


class AdmissionTests(unittest.TestCase):
    setUp = fixtures.CandidateReviewTests.setUp
    def candidate(self, chain="cu"):
        return {"chain": chain, "store_id": "NEW1", "name": "신규점",
                "address": "남원시 도통동 2", "region": "namwon"}

    def test_no_evidence_never_admits(self):
        result = plan(self.root, [self.candidate()])
        self.assertEqual(result["eligible_count"], 0)
        self.assertFalse(result["automatic_production_changes"])

    def test_gs25_blocked_even_with_proof(self):
        proof = {"gs25:NEW1": {"source_verified": True,
                 "stock_lookup_supported": True, "identity_verified": True}}
        result = plan(self.root, [self.candidate("gs25")], proof)
        self.assertEqual(result["eligible_count"], 0)
        self.assertIn("provider_not_ready", result["decisions"][0]["reasons"])

    def test_verified_cu_only_eligible_for_review(self):
        proof = {"cu:NEW1": {"source_verified": True,
                 "stock_lookup_supported": True, "identity_verified": True}}
        result = plan(self.root, [self.candidate()], proof)
        self.assertEqual(result["eligible_count"], 1)
        self.assertEqual(result["decisions"][0]["decision"], "eligible_for_staged_review")
        self.assertFalse(result["automatic_production_changes"])


if __name__ == "__main__":
    unittest.main()
