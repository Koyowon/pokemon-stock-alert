"""Offline-only evidence review state machine. Not used by production."""
CASES = {
    "ASAN-CU-083": ("41691", "LOT_ROAD_MAPPING"),
    "ASAN-CU-092": ("27756", "UNIT_BUILDING_DETAIL"),
    "ASAN-CU-100": ("40840", "APARTMENT_NAME_VARIANT"),
}
HOLD = "HOLD_UNVERIFIED"
APPROVED = "APPROVED_FOR_REVIEW_ONLY"


def assess(case_id, evidence, approval=None):
    """Synthetic evidence ONLY. No external lookups, persistence, or production approval."""
    if case_id not in CASES:
        raise ValueError("Unknown case")
    if not isinstance(evidence, dict):
        raise TypeError("evidence must be a dictionary")
    expected_code, expected_topic = CASES[case_id]
    if evidence.get("conflicting") is True:
        grade = "CONFLICTING"
    elif (evidence.get("source_verified") is True
          and evidence.get("dated") is True
          and evidence.get("code") == expected_code
          and evidence.get("topic") == expected_topic
          and evidence.get("address_link_verified") is True
          and evidence.get("unit_or_building_verified") is True
          and evidence.get("independent_review") is True):
        grade = "SUFFICIENT"
    elif any(bool(v) for v in evidence.values()):
        grade = "PARTIAL"
    else:
        grade = "NONE"
    explicitly_approved = (
        isinstance(approval, dict)
        and approval.get("decision") == "APPROVE"
        and approval.get("case_id") == case_id
        and approval.get("code") == expected_code
        and isinstance(approval.get("reviewer"), str)
        and bool(approval["reviewer"].strip())
        and isinstance(approval.get("approval_reference"), str)
        and bool(approval["approval_reference"].strip())
        and approval.get("explicit") is True
    )
    state = APPROVED if grade == "SUFFICIENT" and explicitly_approved else HOLD
    return {"case_id": case_id, "evidence_grade": grade, "state": state,
            "approval_recorded": explicitly_approved,
            "production_activation": False, "same_location_confirmed": False}
