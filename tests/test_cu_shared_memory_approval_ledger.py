"""Offline shared-ledger tests: synthetic evidence and fake clock only."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

from cu_hardened_approval_policy import CASES, HOLD, REVIEW_ONLY, evidence_digest
from cu_shared_memory_approval_ledger import MockReviewClient, SharedMemoryApprovalLedger

NOW = datetime(2026, 10, 13, 1, tzinfo=timezone.utc)
TRUSTED = {"fixture-reviewer": {"can_review": True, "cases": list(CASES)}}


def fixture(case_id):
    code, topic = CASES[case_id]
    ev = dict(code=code, topic=topic, source_verified=True, dated=True,
              address_link_verified=True, unit_or_building_verified=True,
              independent_review=True, conflicting=False)
    ap = dict(decision="APPROVE", explicit=True, reviewer="fixture-reviewer",
              case_id=case_id, code=code, evidence_sha256=evidence_digest(ev),
              approval_id="fixture-" + case_id,
              issued_at="2026-10-12T00:00:00+00:00",
              expires_at="2026-10-14T00:00:00+00:00")
    return ev, ap


class SharedLedgerTests(unittest.TestCase):
    def test_two_clients_share_replay_history(self):
        ledger = SharedMemoryApprovalLedger()
        a, b = MockReviewClient(ledger), MockReviewClient(ledger)
        ev, ap = fixture("ASAN-CU-083")
        self.assertEqual(a.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)["state"], REVIEW_ONLY)
        self.assertEqual(b.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)["reason"], "APPROVAL_REPLAY")

    def test_eight_concurrent_clients_consume_once(self):
        ledger = SharedMemoryApprovalLedger()
        clients = [MockReviewClient(ledger) for _ in range(8)]
        ev, ap = fixture("ASAN-CU-092")
        barrier = Barrier(8)
        def run(i):
            barrier.wait(timeout=5)
            return clients[i].review("ASAN-CU-092", ev, ap, TRUSTED, NOW)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(run, range(8)))
        self.assertEqual(sum(r["state"] == REVIEW_ONLY for r in results), 1)
        self.assertEqual(sum(r["reason"] == "APPROVAL_REPLAY" for r in results), 7)
        self.assertEqual(ledger.consumed_count(), 1)

    def test_revocation_propagates_to_other_client(self):
        ledger = SharedMemoryApprovalLedger()
        client = MockReviewClient(ledger)
        ledger.revoke("fixture-reviewer")
        ev, ap = fixture("ASAN-CU-100")
        self.assertEqual(client.review("ASAN-CU-100", ev, ap, TRUSTED, NOW)["reason"], "REVIEWER_REVOKED")
        self.assertEqual(ledger.consumed_count(), 0)

    def test_revocation_after_first_review_blocks_new_id(self):
        ledger = SharedMemoryApprovalLedger()
        client = MockReviewClient(ledger)
        ev, ap = fixture("ASAN-CU-100")
        self.assertEqual(client.review("ASAN-CU-100", ev, ap, TRUSTED, NOW)["state"], REVIEW_ONLY)
        ledger.revoke("fixture-reviewer")
        new_ap = dict(ap, approval_id="another-approval")
        self.assertEqual(MockReviewClient(ledger).review("ASAN-CU-100", ev, new_ap, TRUSTED, NOW)["reason"], "REVIEWER_REVOKED")

    def test_changed_evidence_blocks_old_approval(self):
        ledger = SharedMemoryApprovalLedger()
        ev, ap = fixture("ASAN-CU-083")
        changed = dict(ev, synthetic_address_revision="B")
        self.assertEqual(MockReviewClient(ledger).review("ASAN-CU-083", changed, ap, TRUSTED, NOW)["reason"], "EVIDENCE_CHANGED_OR_UNBOUND")
        self.assertEqual(ledger.consumed_count(), 0)

    def test_conflicting_evidence_blocks_before_consumption(self):
        ledger = SharedMemoryApprovalLedger()
        ev, ap = fixture("ASAN-CU-092")
        changed = dict(ev, conflicting=True)
        self.assertEqual(MockReviewClient(ledger).review("ASAN-CU-092", changed, ap, TRUSTED, NOW)["reason"], "CONFLICTING_EVIDENCE")
        self.assertEqual(ledger.consumed_count(), 0)

    def test_expired_approval_not_consumed(self):
        ledger = SharedMemoryApprovalLedger()
        ev, ap = fixture("ASAN-CU-083")
        ap = dict(ap, expires_at="2026-10-13T00:00:00+00:00")
        self.assertEqual(MockReviewClient(ledger).review("ASAN-CU-083", ev, ap, TRUSTED, NOW)["state"], HOLD)
        self.assertEqual(ledger.consumed_count(), 0)

    def test_each_case_can_be_reviewed_separately(self):
        ledger = SharedMemoryApprovalLedger()
        for case_id in CASES:
            ev, ap = fixture(case_id)
            self.assertEqual(MockReviewClient(ledger).review(case_id, ev, ap, TRUSTED, NOW)["state"], REVIEW_ONLY)
        self.assertEqual(ledger.consumed_count(), 3)

    def test_separate_ledgers_do_not_share_state(self):
        ev, ap = fixture("ASAN-CU-083")
        a, b = MockReviewClient(SharedMemoryApprovalLedger()), MockReviewClient(SharedMemoryApprovalLedger())
        self.assertEqual(a.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)["state"], REVIEW_ONLY)
        self.assertEqual(b.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)["state"], REVIEW_ONLY)

    def test_results_never_activate_production(self):
        ledger = SharedMemoryApprovalLedger()
        ev, ap = fixture("ASAN-CU-083")
        client = MockReviewClient(ledger)
        for result in (client.review("ASAN-CU-083", ev, ap, TRUSTED, NOW),
                       client.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)):
            self.assertFalse(result["production_activation"])
            self.assertFalse(result["same_location_confirmed"])

    def test_invalid_client_ledger_fails_closed(self):
        with self.assertRaises(TypeError):
            MockReviewClient(None)


if __name__ == "__main__":
    unittest.main()
