"""Read-only intake of externally captured discovery snapshots.

Snapshots are supplied as files by an operator; this module never fetches APIs,
trusts verification flags, sends alerts, or mutates operational state.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from store_registry.discovery_adapters import normalize_saved
from store_registry.review_candidates import review
from store_registry.admission import plan

REGIONS = frozenset(("namwon", "asan", "jeonju", "jeju"))
CHAINS = frozenset(("cu", "emart24"))


def inspect(root, snapshots):
    if not isinstance(snapshots, list):
        raise ValueError("snapshots must be a list")
    candidates, rejected, seen_snapshots = [], [], set()
    for index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, dict):
            rejected.append({"index": index, "reason": "invalid_snapshot"})
            continue
        chain, region = snapshot.get("chain"), snapshot.get("region")
        source = snapshot.get("source")
        if chain not in CHAINS or region not in REGIONS or source not in (
                "cu_parsed_inventory", "emart24_store_directory", "emart24_seed"):
            rejected.append({"index": index, "reason": "unsupported_source"})
            continue
        if (chain == "cu" and source != "cu_parsed_inventory") or (
                chain == "emart24" and source == "cu_parsed_inventory"):
            rejected.append({"index": index, "reason": "source_chain_mismatch"})
            continue
        marker = (chain, region, source)
        if marker in seen_snapshots:
            rejected.append({"index": index, "reason": "duplicate_snapshot"})
            continue
        seen_snapshots.add(marker)
        try:
            rows = normalize_saved(chain, region, snapshot.get("payload"))
        except (ValueError, TypeError):
            rejected.append({"index": index, "reason": "invalid_payload"})
            continue
        candidates.extend(rows)
    reviewed = review(root, candidates)
    # Untrusted snapshots never provide independent proof for admission.
    decision = plan(root, candidates)
    return {
        "read_only": True,
        "snapshot_count": len(snapshots),
        "candidate_rows": len(candidates),
        "statuses": reviewed["counts"],
        "rejected_snapshots": rejected,
        "new_unverified": reviewed["counts"].get("pending_approval", 0),
        "eligible_for_staged_review": decision["eligible_count"],
        "approved_for_production": 0,
        "automatic_production_changes": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline discovery snapshot intake")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    args = parser.parse_args()
    snapshots = json.loads(args.snapshots.read_text(encoding="utf-8"))
    print(json.dumps(inspect(args.root, snapshots), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
