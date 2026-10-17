#!/usr/bin/env python3
"""Offline verification of coordinate registry against saved stock records. No network access."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/stock/verified_coordinates.json"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def validate():
    cu = load("cu_stock_state.json")["stores"]
    em = load("stores.json")["stores"]
    gs = load("gs25_independent/gs25_stock_state.json")["regions"]
    registry = load("docs/stock/verified_coordinates.json")["stores"]
    errors = []
    for key, entry in registry.items():
        try:
            chain, sid = key.split("|", 1)
            if chain == "CU":
                store = cu[sid]
            elif chain == "이마트24":
                store = em[sid]
            elif chain == "GS25":
                matches = [r["stores"][sid] for r in gs.values() if sid in r.get("stores", {})]
                if len(matches) != 1:
                    raise ValueError("GS25 store ID missing or ambiguous")
                store = matches[0]
            else:
                raise ValueError("Unknown chain")
            if entry.get("chain") != chain or entry.get("store_id") != sid:
                raise ValueError("Chain/store ID mismatch")
            if not store.get("address") or entry.get("address") != store["address"]:
                raise ValueError("Exact address match unavailable")
            if entry.get("verification") != "ADDRESS_AND_STORE_ID_MATCH":
                raise ValueError("Verification missing")
            if not isinstance(entry.get("source"), str) or not entry["source"].startswith("https://"):
                raise ValueError("Verified source URL required")
            lat, lng = entry.get("lat"), entry.get("lng")
            if not (type(lat) in (float, int) and type(lng) in (float, int) and
                    33 <= lat <= 39 and 124 <= lng <= 132):
                raise ValueError("Coordinates invalid")
        except (KeyError, ValueError, TypeError) as exc:
            errors.append(f"{key}: {exc}")
    return len(registry), errors


if __name__ == "__main__":
    count, errors = validate()
    for error in errors:
        print("REJECT", error)
    print(f"COORDINATE_VALIDATION total={count} rejected={len(errors)}")
    sys.exit(bool(errors))
