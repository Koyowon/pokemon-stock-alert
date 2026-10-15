"""Offline source manifests and deterministic discovery change detection.

Manifests are operator declarations, NOT evidence of provider authorization.
No network, file writes, production approval or automatic admission.
"""
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone

from store_registry.convert_external import convert

OFFICIAL_PAGES = {
    "cu": "https://cu.bgfretail.com/store/list.do?category=store",
    "emart24": "https://m.emart24.co.kr/store",
}
REQUIRED = {"chain", "source_page", "captured_at", "capture_method",
            "authorization_reference", "payload"}


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()


def assess(root, manifest, previous=None):
    if not isinstance(manifest, dict) or set(manifest) != REQUIRED:
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
    converted = convert(root, chain, timestamp, manifest["payload"])
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
    return {
        "source_page": manifest["source_page"],
        "source_claim_only": True,
        "authorization_independently_verified": False,
        "input_sha256": _digest(manifest),
        "baseline_sha256": _digest(previous) if previous is not None else None,
        "current": {"chain": chain, "records": current},
        "changes": {"added": added, "removed": removed, "changed": changed},
        "conversion_report": report,
        "approved_for_production": 0,
        "read_only": True,
    }
