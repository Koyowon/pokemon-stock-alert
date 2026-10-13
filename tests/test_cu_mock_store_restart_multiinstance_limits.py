"""Expected-failure security properties of the in-memory mock store.

No subprocesses, network, production imports, or persistent storage.
"""
import unittest
from datetime import datetime, timezone
from cu_hardened_approval_policy import CASES, HOLD, REVIEW_ONLY, evidence_digest
from cu_mock_atomic_approval_store import MockApprovalStore

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
TRUSTED = {"reviewer-all": {"can_review": True, "cases": list(CASES)}}


def fixture(case_id):
    code, topic = CASES[case_id]
    evidence = dict(code=code, topic=topic, source_verified=True, dated=True,
                    address_link_verified=True, unit_or_building_verified=True,
                    independent_review=True, conflicting=False)
    approval = dict(decision="APPROVE", explicit=True, reviewer="reviewer-all",
                    case_id=case_id, code=code, evidence_sha256=evidence_digest(evidence),
                    approval_id="fixture-" + case_id,
                    issued_at="2026-10-12T00:00:00+00:00",
                    expires_at="2026-10-14T00:00:00+00:00")
    return evidence, approval


class InMemoryLimitTests(unittest.TestCase):
    def test_replay_is_blocked_within_one_instance(self):
        store = MockApprovalStore()
        evidence, approval = fixture("ASAN-CU-083")
        self.assertEqual(store.review("ASAN-CU-083", evidence, approval, TRUSTED, NOW)["state"], REVIEW_ONLY)
        self.assertEqual(store.review("ASAN-CU-083", evidence, approval, TRUSTED, NOW)["reason"], "APPROVAL_REPLAY")

    def test_revocation_is_enforced_within_one_instance(self):
        store = MockApprovalStore()
        evidence, approval = fixture("ASAN-CU-092")
        store.revoke("reviewer-all")
        self.assertEqual(store.review("ASAN-CU-092", evidence, approval, TRUSTED, NOW)["reason"], "REVIEWER_REVOKED")

    @unittest.expectedFailure
    def test_replay_remains_blocked_after_simulated_restart(self):
        original = MockApprovalStore()
        evidence, approval = fixture("ASAN-CU-083")
        original.review("ASAN-CU-083", evidence, approval, TRUSTED, NOW)
        restarted = MockApprovalStore()  # Fresh process-memory model
        self.assertEqual(restarted.review("ASAN-CU-083", evidence, approval, TRUSTED, NOW)["state"], HOLD)

    @unittest.expectedFailure
    def test_revocation_survives_simulated_restart(self):
        original = MockApprovalStore()
        original.revoke("reviewer-all")
        restarted = MockApprovalStore()
        evidence, approval = fixture("ASAN-CU-092")
        self.assertEqual(restarted.review("ASAN-CU-092", evidence, approval, TRUSTED, NOW)["state"], HOLD)

    @unittest.expectedFailure
    def test_replay_blocked_across_separate_instances(self):
        instance_a, instance_b = MockApprovalStore(), MockApprovalStore()
        evidence, approval = fixture("ASAN-CU-100")
        instance_a.review("ASAN-CU-100", evidence, approval, TRUSTED, NOW)
        self.assertEqual(instance_b.review("ASAN-CU-100", evidence, approval, TRUSTED, NOW)["state"], HOLD)

    @unittest.expectedFailure
    def test_revocation_propagates_to_other_instance(self):
        instance_a, instance_b = MockApprovalStore(), MockApprovalStore()
        instance_a.revoke("reviewer-all")
        evidence, approval = fixture("ASAN-CU-100")
        self.assertEqual(instance_b.review("ASAN-CU-100", evidence, approval, TRUSTED, NOW)["state"], HOLD)

    def test_recreated_instances_have_empty_consumed_state(self):
        original = MockApprovalStore()
        evidence, approval = fixture("ASAN-CU-083")
        original.review("ASAN-CU-083", evidence, approval, TRUSTED, NOW)
        self.assertEqual(original.consumed_count(), 1)
        self.assertEqual(MockApprovalStore().consumed_count(), 0)

    def test_all_replayed_review_only_results_still_disable_production(self):
        evidence, approval = fixture("ASAN-CU-083")
        for store in (MockApprovalStore(), MockApprovalStore()):
            result = store.review("ASAN-CU-083", evidence, approval, TRUSTED, NOW)
            self.assertFalse(result["production_activation"])
            self.assertFalse(result["same_location_confirmed"])


if __name__ == "__main__":
    unittest.main()
