"""Read-only CU/Emart24 coverage and product-scope audit; no network or alerts."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
    jeonju = read("emart24_jeonju_seed.json")["stores"]
    cu_source = (ROOT / "cu_stock_monitor.py").read_text(encoding="utf-8")
    emart_source = (ROOT / "monitor.py").read_text(encoding="utf-8")
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
            "jeonju_seed_count": len(jeonju),
            "jeonju_seed_missing_in_cache": len(set(jeonju) - set(emart_rows)),
            "cached_by_city": dict(by_city),
            "enabled_regions": [k for k, v in control["chains"]["emart24"].items() if v],
            "note": "Cache is not proof of complete store directory or successful inventory queries.",
        },
    }
    findings["static_checks"] = {
        "cu_barcode_exact": 'BARCODE = "8800286275732"' in cu_source,
        "emart24_only_target_product": 'PRODUCTS = {"30주년 셀레브레이션 팩": "8800286275732"}' in emart_source,
        "cu_decrease_and_sold_out": 'quantity < previous' in cu_source and 'quantity == 0' in cu_source,
        "emart24_decrease_and_sold_out": 'qty < old' in emart_source and 'qty == 0' in emart_source,
        "emart24_jeju_supported": '"제주": "제주시"' in emart_source,
        "cu_single_first_page": '"offset": 0' in cu_source and '"size": 100' in cu_source,
    }
    return findings


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
