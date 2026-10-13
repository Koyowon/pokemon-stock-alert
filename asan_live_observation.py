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
    successes, failures = 0, 0
    for lat, lng in dict.fromkeys(points):
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
            "query_successes": successes, "query_failures": failures,
            "conflicting_codes": sorted(conflicts),
            "status_counts": dict(sorted(Counter(r["status"] for r in rows).items())),
            "candidates": rows, "diagnostic": diagnostic}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="explicitly permit CU API calls")
    parser.add_argument("--output", type=Path, help="optional local JSON report; never stock state")
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

if __name__ == "__main__":
    main()
