"""Synthetic, in-process atomic CU binding gate. Not production authorization."""
from threading import RLock
from cu_hardened_approval_policy import HOLD
from cu_shared_memory_approval_ledger import SharedMemoryApprovalLedger


def hold(reason):
    return {"state": HOLD, "reason": reason, "production_activation": False,
            "same_location_confirmed": False, "consume_approval_id": None}


class AtomicBindingGateway:
    """All mutations and reviews must use these methods and the same lock."""
    def __init__(self, ledger, identity, generation):
        self._lock = RLock()
        self._ledger = ledger
        self._identity = identity
        self._generation = generation
        self._ready = True
        self._initialized = True
        self._expected_ledger = ledger
        self._expected_identity = identity
        self._expected_generation = generation
        self._before_consume = None  # Synthetic test-only hook, invoked under lock.

    def mutate(self, *, ledger=None, identity=None, generation=None,
               ready=None, initialized=None):
        with self._lock:
            if ledger is not None:
                self._ledger = ledger
            if identity is not None:
                self._identity = identity
            if generation is not None:
                self._generation = generation
            if ready is not None:
                self._ready = ready
            if initialized is not None:
                self._initialized = initialized

    def review(self, case_id, evidence, approval, trusted_reviewers, now):
        with self._lock:
            if self._ready is not True or not isinstance(self._ledger, SharedMemoryApprovalLedger):
                return hold("LEDGER_UNAVAILABLE")
            if self._initialized is not True:
                return hold("LEDGER_UNINITIALIZED")
            if not self._expected_identity or self._identity != self._expected_identity:
                return hold("LEDGER_IDENTITY_MISMATCH")
            if (not self._expected_generation or self._generation != self._expected_generation
                    or self._ledger is not self._expected_ledger):
                return hold("LEDGER_GENERATION_MISMATCH")
            if self._before_consume is not None:
                self._before_consume()
            try:
                return self._ledger.review_and_consume(case_id, evidence, approval,
                                                       trusted_reviewers, now)
            except (TypeError, ValueError, KeyError, RuntimeError):
                return hold("LEDGER_REVIEW_ERROR")
