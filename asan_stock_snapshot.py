"""Read-only Asan registry stock snapshot. No I/O, network, state or Telegram."""
from collections import Counter
from cu_asan_registry import classify_observations, load_registry, PRODUCT_BARCODE


def build_snapshot(observed_by_code, *, query_succeeded=False):
    """Return all 123 Asan candidates, preserving unknown vs zero stock."""
    stores = load_registry()
    rows = classify_observations(observed_by_code, query_succeeded=query_succeeded)
    if len(rows) != len(stores):
        raise ValueError("Asan snapshot registry size mismatch")
    by_id = {row["registry_id"]: row for row in rows}
    if len(by_id) != len(stores):
        raise ValueError("Duplicate Asan snapshot registry ID")
    candidates = []
    for store in stores:
        row = by_id[store["registry_id"]]
        candidates.append({
            "registry_id": store["registry_id"],
            "name": store["name"],
            "address": store["address"],
            "cu_store_code": row["cu_store_code"],
            "observed_store_code": row["observed_store_code"],
            "match_method": row["match_method"],
            "status": row["status"],
            "stock": row["stock"],
        })
    return {
        "barcode": PRODUCT_BARCODE,
        "candidate_count": len(candidates),
        "query_succeeded": bool(query_succeeded),
        "status_counts": dict(sorted(Counter(r["status"] for r in candidates).items())),
        "candidates": candidates,
    }
