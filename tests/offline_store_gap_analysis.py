"""Offline-only CU identity crosswalk and Emart24 coverage readiness.

Reads saved repository snapshots. Never calls external APIs or sends alerts.
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = "8800286275732"


def load(name, root=ROOT):
    return json.loads((root / name).read_text(encoding="utf-8"))


def norm_name(value):
    return re.sub(r"[^0-9a-z가-힣]", "", str(value).lower()).removeprefix("씨유").removeprefix("cu")


def analyze(root=ROOT):
    registry = load("asan_cu_watch_registry.json", root)["stores"]
    saved_cu = load("cu_stock_state.json", root)["stores"]
    emart = load("stores.json", root)["stores"]
    jeonju = load("emart24_jeonju_seed.json", root)["stores"]
    control = load("unified_control.json", root)["chains"]
    cu_as = {code: item for code, item in saved_cu.items()
             if item.get("city") == "아산" and str(code).isdigit()}
    existing = {str(r.get("cu_store_code") or "").strip() for r in registry}
    existing.discard("")
    missing = [r for r in registry if not str(r.get("cu_store_code") or "").strip()]
    name_index = {}
    for code, row in cu_as.items():
        name_index.setdefault(norm_name(row.get("name", "")), []).append(code)
    review_only = []
    for row in missing:
        candidates = [c for c in name_index.get(norm_name(row.get("name", "")), [])
                      if c not in existing]
        if candidates:
            review_only.append({"registry_id": row["registry_id"],
                                "candidate_codes": sorted(candidates),
                                "status": "REVIEW_ONLY_DO_NOT_ASSIGN"})
    cities = {"namwon": "남원시", "asan": "아산시",
              "jeonju": "전주시", "jeju": "제주시"}
    emart_counts = {region: sum(token in str(r.get("address", ""))
                                for r in emart.values())
                    for region, token in cities.items()}
    source = (root / "monitor.py").read_text(encoding="utf-8")
    cu_source = (root / "cu_stock_monitor.py").read_text(encoding="utf-8")
    return {
        "target": TARGET,
        "cu": {
            "candidates": len(registry), "coded": len(existing),
            "missing": len(missing), "saved_asan_codes": len(cu_as),
            "potential_name_matches_for_manual_review": review_only,
            "all_candidate_product_codes_correct": all(r.get("product_barcode") == TARGET for r in registry),
            "all_codes_are_unique": len(existing) == sum(bool(r.get("cu_store_code")) for r in registry),
            "pagination_first_page_only": '"offset": 0' in cu_source and '"size": 100' in cu_source,
        },
        "emart24": {
            "cached": len(emart), "by_region": emart_counts,
            "jeonju_seed": len(jeonju),
            "jeonju_seed_not_cached": sorted(set(jeonju) - set(emart)),
            "jeju_enabled_in_control": control["emart24"]["jeju"],
            "jeju_supported_in_monitor": '"제주": "제주시"' in source,
            "only_target_product": 'PRODUCTS = {"30주년 셀레브레이션 팩": "8800286275732"}' in source,
            "search_limit_100": '"limit": 100' in source,
        },
        "caveat": "Saved candidates/cache cannot establish a complete live store directory.",
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
