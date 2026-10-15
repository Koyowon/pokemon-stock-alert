"""Validate a read-only snapshot of main's four JSON inputs; no inventory API."""
import argparse
import hashlib
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

from store_registry.build_registry import build

FILES = (
    "gs25_independent/gs25_stock_state.json",
    "cu_stock_state.json",
    "stores.json",
    "emart24_jeonju_seed.json",
)
EXPECTED = {"gs25": 119, "cu": 164, "emart24": 114}


def verify(root):
    root = Path(root)
    before = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in FILES}
    with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")), \
         patch.object(socket.socket, "connect_ex", side_effect=AssertionError("network forbidden")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
        result = build(root)
    after = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in FILES}
    assert before == after, "Input JSON was modified"
    report = result["report"]
    assert report["total_unique"] == 397, report["total_unique"]
    assert report["by_chain"] == EXPECTED, report["by_chain"]
    assert len(report["conflicts"]) == 0, report["conflicts"]
    missing_gs25 = [x for x in report["issues"] if x["reason"] == "missing_address"
                    and x["source"] == FILES[0]]
    assert len(missing_gs25) == 119, len(missing_gs25)
    seed = json.loads((root / FILES[3]).read_text(encoding="utf-8"))
    cache = json.loads((root / FILES[2]).read_text(encoding="utf-8"))
    overlap = set(seed["stores"]) & set(cache["stores"])
    assert len(overlap) == 63, len(overlap)
    assert all(seed["stores"][code] == cache["stores"][code] for code in overlap)
    candidates = report["region_review_candidates"]
    by_region = {
        region: [x for x in candidates if x["assigned_region"] == region]
        for region in ("namwon", "jeonju")
    }
    assert len(by_region["namwon"]) == 7, by_region["namwon"]
    assert len(by_region["jeonju"]) == 7, by_region["jeonju"]
    assert len(candidates) == 14, candidates
    summary = {
        "total_unique": report["total_unique"], "by_chain": report["by_chain"],
        "conflicts": len(report["conflicts"]), "gs25_missing_address": len(missing_gs25),
        "emart24_seed_cache_overlap": len(overlap),
        "gs25_region_review": {k: len(v) for k, v in by_region.items()},
        "inputs_unchanged": before == after, "network_blocked": True,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    try:
        verify(args.root)
    except Exception as exc:
        print(f"OFFLINE_VERIFICATION_FAILED: {exc}", file=sys.stderr)
        raise
