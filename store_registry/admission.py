"""Fail-closed offline production admission decisions. No provider requests or writes."""
from store_registry.review_candidates import review

PROVIDERS = {
    "gs25": {"discovery": "saved_state_only", "stock_interface": False},
    "cu": {"discovery": "geo_product_search", "stock_interface": True},
    "emart24": {"discovery": "keyword_and_seed", "stock_interface": True},
}


def plan(root, candidates, evidence=None):
    """Evidence must be independently verified; no implicit trust in candidate rows."""
    evidence = evidence or {}
    reviewed = review(root, candidates)
    decisions = []
    for item in reviewed["candidates"]:
        chain, code = item.get("chain"), item.get("store_id")
        proof = evidence.get(chain + ":" + code, {}) if chain and code else {}
        reasons = []
        if item["status"] != "pending_approval":
            reasons.append(item["status"])
        if chain not in PROVIDERS or not PROVIDERS[chain]["stock_interface"]:
            reasons.append("provider_not_ready")
        if not isinstance(proof, dict) or proof.get("source_verified") is not True:
            reasons.append("source_not_verified")
        if not isinstance(proof, dict) or proof.get("stock_lookup_supported") is not True:
            reasons.append("stock_lookup_not_verified")
        if not isinstance(proof, dict) or proof.get("identity_verified") is not True:
            reasons.append("identity_not_verified")
        decisions.append({"chain": chain, "store_id": code,
                          "decision": "eligible_for_staged_review" if not reasons else "blocked",
                          "reasons": reasons})
    return {"read_only": True, "automatic_production_changes": False,
            "decisions": decisions, "eligible_count": sum(
                x["decision"] == "eligible_for_staged_review" for x in decisions)}
