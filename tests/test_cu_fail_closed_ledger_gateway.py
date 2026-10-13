"""Offline synthetic fail-closed gateway regression tests."""
import unittest
from datetime import datetime, timezone
from cu_hardened_approval_policy import CASES, HOLD, REVIEW_ONLY, evidence_digest
from cu_shared_memory_approval_ledger import SharedMemoryApprovalLedger
from cu_fail_closed_ledger_gateway import FakeLedgerBinding, FailClosedReviewGateway

NOW = datetime(2026, 10, 13, 1, tzinfo=timezone.utc)
TRUSTED = {"fixture-reviewer": {"can_review": True, "cases": list(CASES)}}


def fixture(cid="ASAN-CU-083"):
    code, topic = CASES[cid]
    ev = dict(code=code, topic=topic, source_verified=True, dated=True,
              address_link_verified=True, unit_or_building_verified=True,
              independent_review=True, conflicting=False)
    ap = dict(decision="APPROVE", explicit=True, reviewer="fixture-reviewer",
              case_id=cid, code=code, evidence_sha256=evidence_digest(ev),
              approval_id="synthetic-" + cid,
              issued_at="2026-10-12T00:00:00+00:00",
              expires_at="2026-10-14T00:00:00+00:00")
    return ev, ap


def gateway(ready=True, initialized=True, identity="ledger-A", generation="epoch-1"):
    binding = FakeLedgerBinding(SharedMemoryApprovalLedger(), identity,
                                generation, ready, initialized)
    return FailClosedReviewGateway(binding, "ledger-A", "epoch-1")


class FailClosedLedgerTests(unittest.TestCase):
    def check_hold(self, g, reason):
        ev, ap = fixture()
        result = g.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)
        self.assertEqual((result["state"], result["reason"]), (HOLD, reason))
        self.assertIs(result["production_activation"], False)
        self.assertIs(result["same_location_confirmed"], False)
        self.assertIsNone(result["consume_approval_id"])

    def test_healthy_binding_review_only(self):
        g = gateway()
        ev, ap = fixture()
        result = g.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)
        self.assertEqual(result["state"], REVIEW_ONLY)
        self.assertFalse(result["production_activation"])

    def test_connection_lost(self):
        self.check_hold(gateway(ready=False), "LEDGER_UNAVAILABLE")

    def test_binding_removed(self):
        g = gateway()
        g.binding = None
        self.check_hold(g, "LEDGER_UNAVAILABLE")

    def test_ledger_removed(self):
        g = gateway()
        g.binding.ledger = None
        self.check_hold(g, "LEDGER_UNAVAILABLE")

    def test_new_instance_uninitialized(self):
        self.check_hold(gateway(initialized=False), "LEDGER_UNINITIALIZED")

    def test_identity_mismatch(self):
        self.check_hold(gateway(identity="ledger-B"), "LEDGER_IDENTITY_MISMATCH")

    def test_missing_identity(self):
        self.check_hold(gateway(identity=""), "LEDGER_IDENTITY_MISMATCH")

    def test_generation_mismatch(self):
        self.check_hold(gateway(generation="epoch-2"), "LEDGER_GENERATION_MISMATCH")

    def test_replacement_ledger_same_labels_blocked(self):
        g = gateway()
        g.binding.ledger = SharedMemoryApprovalLedger()
        self.check_hold(g, "LEDGER_GENERATION_MISMATCH")

    def test_identity_changes_after_initial_success(self):
        g = gateway()
        ev, ap = fixture()
        self.assertEqual(g.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)["state"], REVIEW_ONLY)
        g.binding.identity = "ledger-B"
        self.check_hold(g, "LEDGER_IDENTITY_MISMATCH")

    def test_reconnect_requires_original_binding(self):
        g = gateway(ready=False)
        self.check_hold(g, "LEDGER_UNAVAILABLE")
        g.binding.ready = True
        ev, ap = fixture()
        self.assertEqual(g.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)["state"], REVIEW_ONLY)

    def test_denial_does_not_consume_id(self):
        g = gateway(ready=False)
        ev, ap = fixture()
        self.assertEqual(g.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)["state"], HOLD)
        self.assertEqual(g.binding.ledger.consumed_count(), 0)

    def test_review_only_still_rejects_replay(self):
        g = gateway()
        ev, ap = fixture()
        self.assertEqual(g.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)["state"], REVIEW_ONLY)
        self.assertEqual(g.review("ASAN-CU-083", ev, ap, TRUSTED, NOW)["reason"], "APPROVAL_REPLAY")

    def test_evidence_change_still_blocked(self):
        g = gateway()
        ev, ap = fixture()
        self.assertEqual(g.review("ASAN-CU-083", dict(ev, revision="changed"), ap, TRUSTED, NOW)["reason"], "EVIDENCE_CHANGED_OR_UNBOUND")

    def test_conflict_still_blocked(self):
        g = gateway()
        ev, ap = fixture()
        self.assertEqual(g.review("ASAN-CU-083", dict(ev, conflicting=True), ap, TRUSTED, NOW)["reason"], "CONFLICTING_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
