"""Audit saved main CU/emart24 store records against the read-only registry.

Saved operational state is not evidence of a newly discovered store.
Never sends requests, writes state, or authorizes admission.
"""
import argparse
import hashlib
import json
import socket
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from store_registry.build_registry import build
from store_registry.discovery_adapters import normalize_saved
from store_registry.review_candidates import review

FILES = ("cu_stock_state.json", "stores.json", "emart24_jeonju_seed.json",
         "gs25_independent/gs25_stock_state.json")
CITIES = {"남원": "namwon", "아산": "asan", "전주": "jeonju", "제주": "jeju"}


def audit(root):
    root = Path(root)
    before = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in FILES}
    with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")), \
         patch.object(socket.socket, "connect_ex", side_effect=AssertionError("network forbidden")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
        registry = build(root)
        registered = {(x["chain"], x["store_id"]) for x in registry["records"]}
        cu = json.loads((root / FILES[0]).read_text(encoding="utf-8"))
        em = json.loads((root / FILES[1]).read_text(encoding="utf-8"))
        rows = []
        counts = {}
        excluded = {}
        for chain, data in (("cu", cu), ("emart24", em)):
            per_region = {r: [] for r in CITIES.values()}
            for code, item in data["stores"].items():
                if chain == "cu":
                    region = CITIES.get(item.get("city"))
                else:
                    address = str(item.get("address", ""))
                    region = next((r for r, marker in
                                   (("namwon", "남원시"), ("asan", "아산시"),
                                    ("jeonju", "전주시"), ("jeju", "제주시"))
                                   if marker in address), None)
                if region is None:
                    excluded.setdefault(chain, []).append(code)
                    continue
                per_region[region].append(dict(item, storeCode=code))
            normalized = []
            for region, candidates in per_region.items():
                normalized.extend(normalize_saved(chain, region, {"stores": candidates}))
            counts[chain] = {"saved": len(data["stores"]), "normalized": len(normalized)}
            excluded.setdefault(chain, []).extend(
                sorted(set(data["stores"]) - {x["store_id"] for x in normalized}))
            rows.extend(normalized)
        report = review(root, rows)
        novel = [x for x in report["candidates"] if x["status"] == "pending_approval"]
        if any((x["chain"], x["store_id"]) not in registered for x in rows) and not novel:
            raise AssertionError("unregistered row silently lost")
    after = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in FILES}
    assert before == after, "saved inputs changed"
    return {"baseline_unique": len(registry["records"]),
            "saved_counts": counts, "candidate_status": report["counts"],
            "new_candidates": len(novel), "excluded_by_adapter": {
                k: {"count": len(v), "codes": sorted(set(v))} for k, v in excluded.items()},
            "approved_for_production": 0, "inputs_unchanged": True,
            "network_blocked": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
