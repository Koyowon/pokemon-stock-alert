"""Offline source manifests and deterministic discovery change detection.

Manifests are operator declarations, NOT evidence of provider authorization.
No network, file writes, production approval or automatic admission.
"""
import hashlib
import json
from datetime import datetime, timezone

from store_registry.convert_external import convert

OFFICIAL_PAGES = {
    "cu": "https://cu.bgfretail.com/store/list.do?category=store",
    "emart24": "https://m.emart24.co.kr/store",
}
REQUIRED = {"chain", "source_page", "captured_at", "capture_method",
            "authorization_reference", "payload"}
REGIONS = frozenset(("namwon", "asan", "jeonju", "jeju"))


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()


def assess(root, manifest, previous=None):
    if not isinstance(manifest, dict) or not REQUIRED.issubset(manifest) or bool(set(manifest) - REQUIRED - {"coverage"}):
        raise ValueError("manifest keys mismatch")
    chain = manifest["chain"]
    if chain not in OFFICIAL_PAGES or manifest["source_page"] != OFFICIAL_PAGES[chain]:
        raise ValueError("unsupported official source page")
    if manifest["capture_method"] != "operator_supplied_export":
        raise ValueError("automated collection is not authorized")
    reference = manifest["authorization_reference"]
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 300:
        raise ValueError("authorization reference required")
    timestamp = manifest["captured_at"]
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise ValueError("UTC capture timestamp required")
    try:
        captured = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if captured > datetime.now(timezone.utc):
        raise ValueError("capture timestamp is in the future")
    coverage = manifest.get("coverage")
    if coverage is None:
        scope, covered = "partial", frozenset()
    else:
        if not isinstance(coverage, dict) or set(coverage) != {"scope", "regions", "evidence"}:
            raise ValueError("invalid coverage fields")
        scope = coverage["scope"]
        regions = coverage["regions"]
        evidence = coverage["evidence"]
        if scope not in ("partial", "complete") or not isinstance(regions, list):
            raise ValueError("invalid coverage scope")
        if not regions or len(set(regions)) != len(regions) or not set(regions).issubset(REGIONS):
            raise ValueError("invalid coverage regions")
        if not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 300:
            raise ValueError("missing coverage evidence")
        covered = frozenset(regions)
    if scope == "complete" and covered != REGIONS:
        raise ValueError("complete scan must cover all regions")
    converted = convert(root, chain, timestamp, manifest["payload"])
    if coverage is not None:
        actual = {s["region"] for s in converted["document"]["snapshots"]}
        if not actual.issubset(covered):
            raise ValueError("data outside declared coverage")
    current = {}
    for snapshot in converted["document"]["snapshots"]:
        for row in snapshot["payload"]["stores"]:
            code = str(row.get("storeCode") or row.get("code")).strip()
            current[code] = {"name": str(row.get("storeName") or row.get("name")).strip(),
                             "address": str(row.get("address")).strip(),
                             "region": snapshot["region"]}
    if previous is not None:
        if not isinstance(previous, dict) or set(previous) != {"chain", "records"} or previous["chain"] != chain:
            raise ValueError("invalid previous snapshot")
        old = previous["records"]
        if not isinstance(old, dict) or any(not isinstance(k, str) or not isinstance(v, dict)
                                            or set(v) != {"name", "address", "region"}
                                            for k, v in old.items()):
            raise ValueError("invalid previous records")
    else:
        old = {}
    added = sorted(set(current) - set(old))
    removed = sorted(set(old) - set(current))
    changed = sorted(code for code in set(old) & set(current) if old[code] != current[code])
    report = converted["report"]
    # A missing store in a partial scan or a rejected row is not a closure.
    removal_review = sorted(code for code in removed if (
        scope != "complete" or report["rejected_rows"] or old[code]["region"] not in covered))
    removal_observed = sorted(set(removed) - set(removal_review))
    age_seconds = int((datetime.now(timezone.utc) - captured).total_seconds())
    return {
        "source_page": manifest["source_page"],
        "source_claim_only": True,
        "authorization_independently_verified": False,
        "input_sha256": _digest(manifest),
        "baseline_sha256": _digest(previous) if previous is not None else None,
        "current": {"chain": chain, "records": current},
        "changes": {"added": added, "removed": removed, "changed": changed},
        "coverage": {"scope": scope, "regions": sorted(covered),
                     "independently_verified": False},
        "freshness": {"captured_at": timestamp, "age_seconds": age_seconds,
                      "stale": age_seconds > 86400},
        "removal_review_required": removal_review,
        "removal_observed_in_complete_scan": removal_observed,
        "safe_to_infer_closure": False,
        "new_store_verification_required": added,
        "repeated_capture_confirmation_required": bool(added or removed or changed),
        "conversion_report": report,
        "approved_for_production": 0,
        "read_only": True,
    }
