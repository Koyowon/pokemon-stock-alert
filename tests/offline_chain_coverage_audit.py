"""Read-only CU/Emart24 coverage and product-scope audit; no network or alerts."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = "8800286275732"


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def audit():
    cu = read("asan_cu_watch_registry.json")
    emart = read("stores.json")
    control = read("unified_control.json")
    cu_rows = cu["stores"]
    codes = [str(s.get("cu_store_code") or "").strip() for s in cu_rows]
    linked = [c for c in codes if c]
    emart_rows = emart["stores"]
    regions = {
        "남원": "남원시", "아산": "아산시",
        "전주": "전주시", "제주": "제주시",
    }
    by_city = Counter(
        city for s in emart_rows.values()
        for city, token in regions.items()
        if token in str(s.get("address", ""))
    )
    findings = {
        "target_barcode": TARGET,
        "cu_asan": {
            "candidate_count": len(cu_rows),
            "unique_registry_ids": len({s["registry_id"] for s in cu_rows}),
            "code_linked": len(linked),
            "code_missing": len(cu_rows) - len(linked),
            "duplicate_linked_codes": len(linked) - len(set(linked)),
            "wrong_barcode": sum(s.get("product_barcode") != TARGET for s in cu_rows),
            "note": "Candidate registration is not proof of live inventory coverage.",
        },
        "emart24": {
            "cached_store_count": len(emart_rows),
            "cached_by_city": dict(by_city),
            "enabled_regions": [k for k, v in control["chains"]["emart24"].items() if v],
            "note": "Cache is not proof of complete store directory or successful inventory queries.",
        },
    }
    return findings


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
