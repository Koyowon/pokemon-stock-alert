"""Synthetic in-memory approval gate; never production authorization."""
from threading import Lock
from cu_hardened_approval_policy import assess, HOLD, REVIEW_ONLY


class MockApprovalStore:
    """In-process atomic consume, no persistence or external authentication."""
    def __init__(self):
        self._lock = Lock()
        self._consumed = set()
        self._revoked_reviewers = set()

    def revoke(self, reviewer):
        with self._lock:
            self._revoked_reviewers.add(reviewer)

    def review(self, case_id, evidence, approval, trusted_reviewers, now):
        with self._lock:
            reviewer = approval.get("reviewer") if isinstance(approval, dict) else None
            if reviewer in self._revoked_reviewers:
                return {"state": HOLD, "reason": "REVIEWER_REVOKED",
                        "production_activation": False, "same_location_confirmed": False,
                        "consume_approval_id": None}
            result = assess(case_id, evidence, approval, trusted_reviewers,
                            self._consumed, now)
            if result["state"] == REVIEW_ONLY:
                self._consumed.add(result["consume_approval_id"])
            return result

    def consumed_count(self):
        with self._lock:
            return len(self._consumed)
