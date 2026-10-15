"""Offline candidate intake. Never contacts providers or writes operational files."""
import argparse
import json
from collections import Counter
from pathlib import Path

from store_registry.build_registry import REGIONS, build, normalize_text

CHAINS = frozenset(("gs25", "cu", "emart24"))
REGION_MARKERS = {
    "namwon": ("남원시",),
    "asan": ("아산시",),
    "jeonju": ("전주시",),
    "jeju": ("제주시", "서귀포시"),
}


def review(root, candidates):
    existing = {(r["chain"], r["store_id"]): r for r in build(root)["records"]}
    seen = set()
    result = []
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            result.append({"index": index, "status": "invalid", "reason": "not_object"})
            continue
        chain = normalize_text(item.get("chain")).lower()
        code = normalize_text(item.get("store_id"))
        name = normalize_text(item.get("name"))
        address = normalize_text(item.get("address"))
        region = normalize_text(item.get("region")).lower()
        key = (chain, code)
        entry = {"index": index, "chain": chain, "store_id": code,
                 "name": name, "address": address, "region": region}
        if chain not in CHAINS or not code or not name or not address or region not in REGIONS:
            entry.update(status="invalid", reason="required_field_or_region")
        elif key in seen:
            entry.update(status="duplicate_in_submission", reason="same_chain_code")
        elif key in existing:
            old = existing[key]
            changed = [f for f in ("name", "address", "region")
                       if old.get(f) and old[f] != entry[f]]
            entry.update(status="existing_conflict" if changed else "already_registered",
                         reason=",".join(changed) if changed else "same_chain_code")
        elif not any(marker in address for marker in REGION_MARKERS[region]):
            entry.update(status="needs_region_review", reason="address_region_mismatch")
        else:
            entry.update(status="pending_approval", reason="new_store_unverified")
        if chain in CHAINS and code:
            seen.add(key)
        result.append(entry)
    return {"read_only": True, "counts": dict(sorted(Counter(x["status"] for x in result).items())),
            "candidates": result, "approved_for_production": 0}


def main():
    parser = argparse.ArgumentParser(description="Offline new-store candidate review")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.candidates.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        parser.error("candidate file must be a JSON array")
    print(json.dumps(review(args.root, data), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
