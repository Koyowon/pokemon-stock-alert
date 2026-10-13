"""Asan-only live observation probe. Never writes state or sends Telegram.

Run explicitly with --live to call the existing CU inventory API.
All 123 registry candidates remain in the output, including NOT_OBSERVED.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from cu_asan_registry import classify_observations
from cu_stock_monitor import POINTS, BARCODE, query
from asan_coordinate_expansion import build_points
from asan_unmatched_diagnostic import audit_unmatched

def observe(points, query_fn, classify_fn):
    observed, conflicts = {}, set()
    unique_points = list(dict.fromkeys(points))
    successes, failures = 0, 0
    for lat, lng in unique_points:
        try:
            rows = query_fn("아산", lat, lng)
            successes += 1
        except Exception as exc:
            failures += 1
            print("ASAN_QUERY_ERROR:", lat, lng, type(exc).__name__, flush=True)
            continue
        for item in rows:
            code = str(item.get("code", "")).strip()
            if not code or code in conflicts:
                continue
            prior = observed.get(code)
            if prior is None:
                observed[code] = item
            elif any(prior.get(k) != item.get(k) for k in ("stock", "city", "name", "address")):
                conflicts.add(code)
                observed.pop(code, None)
    rows = classify_fn(observed, query_succeeded=successes > 0)
    if len(rows) != 123:
        raise ValueError("Expected 123 registry candidates")
    diagnostic = audit_unmatched(observed, rows, conflicts=conflicts)
    return {"barcode": BARCODE, "candidate_count": len(rows),
            "query_total": len(unique_points),
            "query_succeeded": bool(unique_points) and failures == 0 and successes == len(unique_points) and not conflicts,
            "query_successes": successes, "query_failures": failures,
            "conflicting_codes": sorted(conflicts),
            "status_counts": dict(sorted(Counter(r["status"] for r in rows).items())),
            "candidates": rows, "diagnostic": diagnostic}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="explicitly permit CU API calls")
    parser.add_argument("--output", type=Path, help="optional local JSON report; never stock state")
    parser.add_argument("--send-status", action="store_true", help="explicitly enable persistent Telegram status delivery")
    parser.add_argument("--include-provisional-coordinates", action="store_true", help="opt in to 3 unverified registry coordinates for read-only probes")
    args = parser.parse_args()
    if not args.live:
        parser.error("Live calls disabled by default; specify --live to opt in")
    result = observe(build_points(include_provisional=args.include_provisional_coordinates), query, classify_observations)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if result["query_successes"] == 0:
        raise SystemExit(2)
    if args.send_status:
        from asan_status_delivery import enabled, delivery_key
        from asan_stock_chunks import preview_asan_stock_messages
        from asan_github_status_persistence import GitBranchCAS, deliver_persistent
        from cu_asan_registry import load_registry
        from cu_stock_monitor import telegram
        if not enabled():
            raise SystemExit("Status sending disabled")
        address_by_id = {s["registry_id"]: s["address"] for s in load_registry()}
        snapshot = dict(result)
        snapshot["candidates"] = [dict(row, address=address_by_id[row["registry_id"]]) for row in result["candidates"]]
        delivery_key(snapshot)
        status = deliver_persistent(snapshot, preview_asan_stock_messages(snapshot), telegram,
                                    GitBranchCAS(Path(__file__).resolve().parent), enabled=True)
        print("ASAN_STATUS_DELIVERY:", status, flush=True)
        if status not in ("SENT", "UNCHANGED"):
            raise SystemExit(3)

if __name__ == "__main__":
    main()
