"""Offline fail-closed guard for a shared in-memory CU review ledger.

Identity tokens and readiness are synthetic, not authenticated health checks.
"""
from cu_hardened_approval_policy import HOLD
from cu_shared_memory_approval_ledger import SharedMemoryApprovalLedger


def hold(reason):
    return {"state": HOLD, "reason": reason, "production_activation": False,
            "same_location_confirmed": False, "consume_approval_id": None}


class FakeLedgerBinding:
    def __init__(self, ledger, identity, generation, ready=True, initialized=True):
        self.ledger = ledger
        self.identity = identity
        self.generation = generation
        self.ready = ready
        self.initialized = initialized


class FailClosedReviewGateway:
    """Pin expected ledger identity, generation and exact object reference."""
    def __init__(self, binding, expected_identity, expected_generation):
        self.binding = binding
        self.expected_identity = expected_identity
        self.expected_generation = expected_generation
        self.expected_ledger = binding.ledger if isinstance(binding, FakeLedgerBinding) else None

    def review(self, case_id, evidence, approval, trusted_reviewers, now):
        b = self.binding
        if not isinstance(b, FakeLedgerBinding) or b.ready is not True:
            return hold("LEDGER_UNAVAILABLE")
        if not isinstance(b.ledger, SharedMemoryApprovalLedger):
            return hold("LEDGER_UNAVAILABLE")
        if b.initialized is not True:
            return hold("LEDGER_UNINITIALIZED")
        if (not isinstance(self.expected_identity, str) or not self.expected_identity
                or b.identity != self.expected_identity):
            return hold("LEDGER_IDENTITY_MISMATCH")
        if (not isinstance(self.expected_generation, str) or not self.expected_generation
                or b.generation != self.expected_generation
                or b.ledger is not self.expected_ledger):
            return hold("LEDGER_GENERATION_MISMATCH")
        try:
            return b.ledger.review_and_consume(case_id, evidence, approval,
                                               trusted_reviewers, now)
        except (TypeError, ValueError, KeyError, RuntimeError):
            return hold("LEDGER_REVIEW_ERROR")
