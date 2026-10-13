"""Deterministic TOCTOU thread tests against the existing offline gateway.

Expected failures deliberately expose non-atomic binding validation/dispatch.
No network, database, persistent storage, or production imports.
"""
import threading
import unittest
from datetime import datetime, timezone

from cu_hardened_approval_policy import CASES, HOLD, REVIEW_ONLY, evidence_digest
from cu_fail_closed_ledger_gateway import FakeLedgerBinding, FailClosedReviewGateway
from cu_shared_memory_approval_ledger import SharedMemoryApprovalLedger

NOW = datetime(2026, 10, 13, 1, tzinfo=timezone.utc)
TRUSTED = {"fixture-reviewer": {"can_review": True, "cases": list(CASES)}}


def fixture(cid="ASAN-CU-083"):
    code, topic = CASES[cid]
    evidence = dict(code=code, topic=topic, source_verified=True, dated=True,
                    address_link_verified=True, unit_or_building_verified=True,
                    independent_review=True, conflicting=False)
    approval = dict(decision="APPROVE", explicit=True, reviewer="fixture-reviewer",
                    case_id=cid, code=code, evidence_sha256=evidence_digest(evidence),
                    approval_id="toctou-" + cid,
                    issued_at="2026-10-12T00:00:00+00:00",
                    expires_at="2026-10-14T00:00:00+00:00")
    return evidence, approval


class InterleavedBinding(FakeLedgerBinding):
    """Pause on third ledger read: after validation snapshot, before dispatch."""
    def __init__(self):
        self._ledger = SharedMemoryApprovalLedger()
        self.read_count = 0
        self.at_gap = threading.Event()
        self.resume = threading.Event()
        self.identity = "ledger-A"
        self.generation = "epoch-1"
        self.ready = True
        self.initialized = True

    @property
    def ledger(self):
        self.read_count += 1
        current = self._ledger
        if self.read_count == 3:
            self.at_gap.set()
            if not self.resume.wait(timeout=3):
                raise RuntimeError("test synchronization timed out")
        return current

    @ledger.setter
    def ledger(self, value):
        self._ledger = value


def interleave(change):
    binding = InterleavedBinding()
    gateway = FailClosedReviewGateway(binding, "ledger-A", "epoch-1")
    evidence, approval = fixture()
    def mutate():
        if not binding.at_gap.wait(timeout=3):
            binding.resume.set()
            raise RuntimeError("gateway did not reach synchronization point")
        try:
            change(binding, gateway)
        finally:
            binding.resume.set()
    thread = threading.Thread(target=mutate, name="synthetic-ledger-mutator")
    thread.start()
    try:
        result = gateway.review("ASAN-CU-083", evidence, approval, TRUSTED, NOW)
    finally:
        binding.resume.set()
        thread.join(timeout=3)
    if thread.is_alive():
        raise AssertionError("mutator thread did not terminate")
    return result, binding


class GatewayTOCTOUTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_ledger_replaced_after_validation_should_hold(self):
        result, binding = interleave(
            lambda b, g: setattr(b, "ledger", SharedMemoryApprovalLedger()))
        self.assertEqual(result["state"], HOLD)  # Currently REVIEW_ONLY.
        self.assertEqual(binding._ledger.consumed_count(), 0)

    @unittest.expectedFailure
    def test_ready_revoked_after_validation_should_hold(self):
        result, _ = interleave(lambda b, g: setattr(b, "ready", False))
        self.assertEqual(result["state"], HOLD)  # Currently REVIEW_ONLY.

    @unittest.expectedFailure
    def test_generation_changed_after_validation_should_hold(self):
        result, _ = interleave(lambda b, g: setattr(b, "generation", "epoch-2"))
        self.assertEqual(result["state"], HOLD)  # Currently REVIEW_ONLY.

    @unittest.expectedFailure
    def test_gateway_binding_swapped_after_snapshot_should_hold(self):
        def swap(b, g):
            g.binding = FakeLedgerBinding(SharedMemoryApprovalLedger(),
                                          "ledger-B", "epoch-2", ready=False)
        result, _ = interleave(swap)
        self.assertEqual(result["state"], HOLD)  # Local b still used.

    def test_no_mutation_allows_review_only(self):
        result, binding = interleave(lambda b, g: None)
        self.assertEqual(result["state"], REVIEW_ONLY)
        self.assertEqual(binding._ledger.consumed_count(), 1)

    def test_ledger_swap_consumes_replacement_ledger(self):
        result, binding = interleave(
            lambda b, g: setattr(b, "ledger", SharedMemoryApprovalLedger()))
        self.assertEqual(result["state"], REVIEW_ONLY)
        self.assertEqual(binding._ledger.consumed_count(), 1)
        self.assertFalse(result["production_activation"])
        self.assertFalse(result["same_location_confirmed"])

    def test_ready_change_still_does_not_activate_production(self):
        result, _ = interleave(lambda b, g: setattr(b, "ready", False))
        self.assertEqual(result["state"], REVIEW_ONLY)
        self.assertIs(result["production_activation"], False)
        self.assertIs(result["same_location_confirmed"], False)

    def test_preexisting_unavailable_binding_still_holds(self):
        binding = FakeLedgerBinding(SharedMemoryApprovalLedger(), "ledger-A",
                                    "epoch-1", ready=False)
        gateway = FailClosedReviewGateway(binding, "ledger-A", "epoch-1")
        evidence, approval = fixture()
        self.assertEqual(gateway.review("ASAN-CU-083", evidence, approval,
                                        TRUSTED, NOW)["state"], HOLD)


if __name__ == "__main__":
    unittest.main()
