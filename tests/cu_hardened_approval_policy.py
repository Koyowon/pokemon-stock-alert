"""Offline-only hardened approval simulation; never grants production authority."""
import hashlib
import json
from datetime import datetime

CASES = {
    "ASAN-CU-083": ("41691", "LOT_ROAD_MAPPING"),
    "ASAN-CU-092": ("27756", "UNIT_BUILDING_DETAIL"),
    "ASAN-CU-100": ("40840", "APARTMENT_NAME_VARIANT"),
}
HOLD = "HOLD_UNVERIFIED"
REVIEW_ONLY = "APPROVED_FOR_REVIEW_ONLY"


def evidence_digest(evidence):
    """Deterministic hash of synthetic evidence, not proof of authenticity."""
    return hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def assess(case_id, evidence, approval, trusted_reviewers, consumed_ids, now):
    """Pure fail-closed assessment; consumed_ids is a read-only external snapshot."""
    if case_id not in CASES:
        raise ValueError("Unknown case")
    if not isinstance(evidence, dict) or not isinstance(trusted_reviewers, dict):
        raise TypeError("Evidence and trusted reviewers must be dictionaries")
    code, topic = CASES[case_id]
    def hold(reason):
        return {"state": HOLD, "reason": reason, "production_activation": False,
                "same_location_confirmed": False, "consume_approval_id": None}
    if evidence.get("conflicting") is True:
        return hold("CONFLICTING_EVIDENCE")
    required = (evidence.get("source_verified") is True,
                evidence.get("dated") is True,
                evidence.get("code") == code,
                evidence.get("topic") == topic,
                evidence.get("address_link_verified") is True,
                evidence.get("unit_or_building_verified") is True,
                evidence.get("independent_review") is True,
                evidence.get("conflicting") is False)
    if not all(required):
        return hold("INSUFFICIENT_EVIDENCE")
    if not isinstance(approval, dict) or approval.get("decision") != "APPROVE" or approval.get("explicit") is not True:
        return hold("NO_EXPLICIT_APPROVAL")
    reviewer = approval.get("reviewer")
    scope = trusted_reviewers.get(reviewer) if isinstance(reviewer, str) else None
    if not isinstance(scope, dict) or scope.get("can_review") is not True or case_id not in scope.get("cases", ()):
        return hold("UNAUTHORIZED_REVIEWER")
    if approval.get("case_id") != case_id or approval.get("code") != code:
        return hold("APPROVAL_SCOPE_MISMATCH")
    try:
        digest = evidence_digest(evidence)
    except (TypeError, ValueError):
        return hold("INVALID_EVIDENCE")
    if approval.get("evidence_sha256") != digest:
        return hold("EVIDENCE_CHANGED_OR_UNBOUND")
    approval_id = approval.get("approval_id")
    if not isinstance(approval_id, str) or not approval_id.strip():
        return hold("INVALID_APPROVAL_ID")
    if approval_id in consumed_ids:
        return hold("APPROVAL_REPLAY")
    try:
        if not isinstance(now, datetime) or now.tzinfo is None:
            return hold("INVALID_CLOCK")
        expires = datetime.fromisoformat(approval.get("expires_at", ""))
        issued = datetime.fromisoformat(approval.get("issued_at", ""))
        if expires.tzinfo is None or issued.tzinfo is None:
            return hold("INVALID_APPROVAL_TIME")
        if not (issued <= now < expires and issued < expires):
            return hold("EXPIRED_OR_NOT_YET_VALID")
    except (ValueError, TypeError):
        return hold("INVALID_APPROVAL_TIME")
    return {"state": REVIEW_ONLY, "reason": "SYNTHETIC_REVIEW_GATE_PASSED",
            "production_activation": False, "same_location_confirmed": False,
            "consume_approval_id": approval_id}
