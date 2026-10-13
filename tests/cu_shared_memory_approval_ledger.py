"""Shared in-memory approval ledger for offline simulations only.

All clients must share ONE ledger object. No persistence, IPC, DB, or auth.
"""
from threading import Lock
from cu_hardened_approval_policy import assess, HOLD, REVIEW_ONLY


def _hold(reason):
    return {"state": HOLD, "reason": reason, "production_activation": False,
            "same_location_confirmed": False, "consume_approval_id": None}


class SharedMemoryApprovalLedger:
    def __init__(self):
        self._lock = Lock()
        self._consumed_ids = set()
        self._revoked_reviewers = set()

    def revoke(self, reviewer):
        with self._lock:
            self._revoked_reviewers.add(reviewer)

    def review_and_consume(self, case_id, evidence, approval, trusted_reviewers, now):
        # Lock protects check, revocation lookup, and consumption as one transaction.
        with self._lock:
            reviewer = approval.get("reviewer") if isinstance(approval, dict) else None
            if reviewer in self._revoked_reviewers:
                return _hold("REVIEWER_REVOKED")
            result = assess(case_id, evidence, approval, trusted_reviewers,
                            self._consumed_ids, now)
            if result["state"] == REVIEW_ONLY:
                self._consumed_ids.add(result["consume_approval_id"])
            return result

    def consumed_count(self):
        with self._lock:
            return len(self._consumed_ids)


class MockReviewClient:
    """Separate clients can share a ledger, not a process boundary."""
    def __init__(self, ledger):
        if not isinstance(ledger, SharedMemoryApprovalLedger):
            raise TypeError("SharedMemoryApprovalLedger required")
        self._ledger = ledger

    def review(self, case_id, evidence, approval, trusted_reviewers, now):
        return self._ledger.review_and_consume(
            case_id, evidence, approval, trusted_reviewers, now)
