"""Synthetic offline intake tests; no API calls or state writes."""
import unittest
from store_registry import test_candidates as fixtures
from store_registry.discovery_pipeline import inspect


class DiscoveryPipelineTests(unittest.TestCase):
    setUp = fixtures.CandidateReviewTests.setUp

    def test_cu_new_and_existing_without_approval(self):
        snapshots = [{"chain": "cu", "region": "namwon", "source": "cu_parsed_inventory",
                      "payload": {"stores": [
                          {"code": "0012", "name": "신규CU", "address": "전북특별자치도 남원시 3"},
                          {"code": "C1", "name": "기존", "address": "전북특별자치도 남원시 1"}]}}]
        result = inspect(self.root, snapshots)
        self.assertEqual(result["new_unverified"], 1)
        self.assertEqual(result["approved_for_production"], 0)
        self.assertEqual(result["eligible_for_staged_review"], 0)

    def test_emart24_deduplication(self):
        payload = {"stores": [{"storeCode": "00123", "storeName": "신규",
                               "address": "충청남도 아산시 1"},
                              {"storeCode": "00123", "storeName": "신규",
                               "address": "충청남도 아산시 1"}]}
        result = inspect(self.root, [{"chain": "emart24", "region": "asan",
                                     "source": "emart24_store_directory", "payload": payload}])
        self.assertEqual(result["statuses"], {
            "duplicate_in_submission": 1, "pending_approval": 1})

    def test_bad_snapshots_fail_closed(self):
        result = inspect(self.root, [None, {"chain": "gs25", "region": "namwon",
                          "source": "emart24_seed", "payload": {"stores": []}},
                          {"chain": "cu", "region": "namwon",
                           "source": "cu_parsed_inventory", "payload": {"stores": {}}}])
        self.assertEqual(len(result["rejected_snapshots"]), 3)
        self.assertEqual(result["candidate_rows"], 0)

    def test_snapshot_claim_cannot_self_approve(self):
        result = inspect(self.root, [{"chain": "emart24", "region": "asan",
                         "source": "emart24_seed",
                         "source_verified": True, "stock_lookup_supported": True,
                         "identity_verified": True,
                         "payload": {"stores": [{"storeCode": "00123",
                         "storeName": "신규", "address": "충청남도 아산시 1"}]}}])
        self.assertEqual(result["new_unverified"], 1)
        self.assertEqual(result["eligible_for_staged_review"], 0)


if __name__ == "__main__":
    unittest.main()
