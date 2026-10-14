"""Evidence-gated CU matching; never automatically assigns a code."""
import re

def canonical(value):
    return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower()).removeprefix("씨유").removeprefix("cu")

def review(candidate, observation, existing_codes=()):
    """Return review status only. Require exact store name and address and source provenance."""
    code = str(observation.get("code") or "").strip()
    if not code.isdigit():
        return "REJECT_INVALID_CODE"
    if code in set(map(str, existing_codes)):
        return "REJECT_ALREADY_ASSIGNED"
    if not observation.get("source") or not observation.get("observed_at"):
        return "REJECT_NO_PROVENANCE"
    if not canonical(candidate.get("name")) or canonical(candidate.get("name")) != canonical(observation.get("name")):
        return "REJECT_NAME_MISMATCH"
    if not canonical(candidate.get("address")) or canonical(candidate.get("address")) != canonical(observation.get("address")):
        return "REJECT_ADDRESS_MISMATCH"
    return "MANUAL_REVIEW_REQUIRED"
