"""Offline concurrency, evidence binding, and revocation regression tests."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from cu_hardened_approval_policy import CASES, HOLD, REVIEW_ONLY, evidence_digest
from cu_mock_atomic_approval_store import MockApprovalStore

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
TRUSTED = {"reviewer-all": {"can_review": True, "cases": list(CASES)}}

def evidence(cid):
    code, topic = CASES[cid]
    return dict(code=code, topic=topic, source_verified=True, dated=True,
                address_link_verified=True, unit_or_building_verified=True,
                independent_review=True, conflicting=False)

def approval(cid, ev):
    return dict(decision="APPROVE", explicit=True, reviewer="reviewer-all",
                case_id=cid, code=CASES[cid][0], evidence_sha256=evidence_digest(ev),
                approval_id="fixture-" + cid, issued_at="2026-10-12T00:00:00+00:00",
                expires_at="2026-10-14T00:00:00+00:00")

class MockAtomicApprovalTests(unittest.TestCase):
    def test_simultaneous_same_id_only_one_review_pass(self):
        cid = "ASAN-CU-083"
        ev = evidence(cid)
        ap = approval(cid, ev)
        store = MockApprovalStore()
        barrier = Barrier(8)
        def worker(_):
            barrier.wait()
            return store.review(cid, ev, ap, TRUSTED, NOW)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(worker, range(8)))
        self.assertEqual(sum(x["state"] == REVIEW_ONLY for x in results), 1)
        self.assertEqual(sum(x["reason"] == "APPROVAL_REPLAY" for x in results), 7)
        self.assertEqual(store.consumed_count(), 1)

    def test_evidence_changed_after_approval_is_rejected(self):
        cid = "ASAN-CU-092"
        original = evidence(cid)
        ap = approval(cid, original)
        changed = dict(original, address_revision="changed")
        result = MockApprovalStore().review(cid, changed, ap, TRUSTED, NOW)
        self.assertEqual(result["reason"], "EVIDENCE_CHANGED_OR_UNBOUND")

    def test_evidence_change_does_not_consume_approval(self):
        cid = "ASAN-CU-092"
        ev = evidence(cid)
        store = MockApprovalStore()
        ap = approval(cid, ev)
        changed = dict(ev, address_revision="changed")
        store.review(cid, changed, ap, TRUSTED, NOW)
        self.assertEqual(store.consumed_count(), 0)
        self.assertEqual(store.review(cid, ev, ap, TRUSTED, NOW)["state"], REVIEW_ONLY)

    def test_revoked_reviewer_rejected(self):
        cid = "ASAN-CU-100"
        ev = evidence(cid)
        store = MockApprovalStore()
        store.revoke("reviewer-all")
        result = store.review(cid, ev, approval(cid, ev), TRUSTED, NOW)
        self.assertEqual(result["reason"], "REVIEWER_REVOKED")
        self.assertEqual(store.consumed_count(), 0)

    def test_revocation_after_first_review_blocks_fresh_id(self):
        cid = "ASAN-CU-100"
        ev = evidence(cid)
        store = MockApprovalStore()
        ap = approval(cid, ev)
        self.assertEqual(store.review(cid, ev, ap, TRUSTED, NOW)["state"], REVIEW_ONLY)
        store.revoke("reviewer-all")
        newer = dict(ap, approval_id="second-approval")
        self.assertEqual(store.review(cid, ev, newer, TRUSTED, NOW)["state"], HOLD)

    def test_revocation_does_not_retroactively_erase_prior_result(self):
        cid = "ASAN-CU-083"
        ev = evidence(cid)
        store = MockApprovalStore()
        result = store.review(cid, ev, approval(cid, ev), TRUSTED, NOW)
        store.revoke("reviewer-all")
        self.assertEqual(result["state"], REVIEW_ONLY)
        self.assertEqual(store.consumed_count(), 1)

    def test_per_case_separate_approvals(self):
        store = MockApprovalStore()
        for cid in CASES:
            ev = evidence(cid)
            self.assertEqual(store.review(cid, ev, approval(cid, ev), TRUSTED, NOW)["state"], REVIEW_ONLY)
        self.assertEqual(store.consumed_count(), 3)

    def test_conflicting_evidence_never_consumed(self):
        cid = "ASAN-CU-083"
        ev = dict(evidence(cid), conflicting=True)
        store = MockApprovalStore()
        result = store.review(cid, ev, approval(cid, ev), TRUSTED, NOW)
        self.assertEqual(result["reason"], "CONFLICTING_EVIDENCE")
        self.assertEqual(store.consumed_count(), 0)

    def test_expired_approval_never_consumed(self):
        cid = "ASAN-CU-083"
        ev = evidence(cid)
        ap = dict(approval(cid, ev), expires_at="2026-10-13T11:00:00+00:00")
        store = MockApprovalStore()
        self.assertEqual(store.review(cid, ev, ap, TRUSTED, NOW)["state"], HOLD)
        self.assertEqual(store.consumed_count(), 0)

    def test_all_results_not_production(self):
        cid = "ASAN-CU-083"
        ev = evidence(cid)
        store = MockApprovalStore()
        for result in (store.review(cid, ev, approval(cid, ev), TRUSTED, NOW),
                       store.review(cid, ev, approval(cid, ev), TRUSTED, NOW)):
            self.assertFalse(result["production_activation"])
            self.assertFalse(result["same_location_confirmed"])

if __name__ == "__main__":
    unittest.main()
