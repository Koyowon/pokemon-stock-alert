"""Read-only, fail-closed manual review queue for discovery observations.

No provider calls, notifications, writes, automatic admission or closure.
"""
from collections import Counter
from datetime import datetime, timezone

from store_registry.build_registry import build
from store_registry.source_audit import assess, REGIONS


def _valid_evidence(evidence, code, identity, chain):
    """Two independently supplied attestations; declarations are not verified."""
    if not isinstance(evidence, dict):
        return False
    items = evidence.get(code)
    if not isinstance(items, list) or len(items) < 2:
        return False
    sources = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"source", "reference", "chain",
                                                        "store_id", "name", "address", "region"}:
            return False
        if any(not isinstance(item[k], str) or not item[k].strip()
               for k in item):
            return False
        if (item["chain"] != chain or item["store_id"] != code or
            any(item[k] != identity[k] for k in ("name", "address", "region"))):
            return False
        sources.add(item["source"])
    return len(sources) >= 2


def queue(root, captures, evidence=None, now=None):
    """Require two separate captures, coverage, freshness and identity agreement.

    Evidence is operator-supplied and cannot independently prove authorization.
    A 'manual_review' item is not approval for production.
    """
    if not isinstance(captures, list) or len(captures) != 2:
        raise ValueError("exactly two capture manifests required")
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a mapping")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    chain = captures[0].get("chain") if isinstance(captures[0], dict) else None
    if not all(isinstance(c, dict) and c.get("chain") == chain for c in captures):
        raise ValueError("captures must have same chain")
    first, second = [assess(root, c) for c in captures]
    t1, t2 = [datetime.fromisoformat(c["captured_at"].replace("Z", "+00:00"))
              for c in captures]
    if t1 >= t2:
        raise ValueError("captures must be strictly time-ordered")
    existing = {(r["chain"], r["store_id"]) for r in build(root)["records"]}
    old, current = first["current"]["records"], second["current"]["records"]
    records = []
    all_codes = sorted(set(old) | set(current))
    for code in all_codes:
        identity = current.get(code) or old[code]
        reasons = []
        if code not in old or code not in current:
            reasons.append("not_repeated")
        elif old[code] != current[code]:
            reasons.append("identity_changed")
        region = identity["region"]
        for result in (first, second):
            coverage = result["coverage"]
            if region not in coverage["regions"]:
                reasons.append("coverage_unverified")
            if result["conversion_report"]["rejected_rows"]:
                reasons.append("capture_has_quarantined_rows")
        if (now - t2).total_seconds() > 86400 or (now - t1).total_seconds() > 7 * 86400:
            reasons.append("stale_capture")
        if (chain, code) in existing:
            reasons.append("already_registered")
        if not _valid_evidence(evidence, code, identity, chain):
            reasons.append("independent_evidence_missing")
        # Provider permissions and evidence provenance are never established by
        # a user-supplied manifest or user-supplied attestations alone.
        if reasons:
            status = "quarantined"
        else:
            status = "manual_review"
        records.append({"chain": chain, "store_id": code, "identity": identity,
                        "status": status, "reasons": sorted(set(reasons)),
                        "evidence_independently_verified": False,
                        "approved_for_production": False})
    return {"chain": chain, "items": records,
            "counts": dict(sorted(Counter(r["status"] for r in records).items())),
            "closure_candidates": [],
            "source_authorization_verified": False,
            "approved_for_production": 0, "automatic_registration": False,
            "read_only": True}
