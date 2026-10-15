"""Read-only, standard-library store registry builder. No network or operational writes."""
import argparse
import json
from collections import Counter
from pathlib import Path

INPUTS = {
    "gs25": "gs25_independent/gs25_stock_state.json",
    "cu": "cu_stock_state.json",
    "emart24": "stores.json",
}
SEED = "emart24_jeonju_seed.json"
REGIONS = {"namwon": "남원", "asan": "아산", "jeonju": "전주", "jeju": "제주"}


def read_object(root, name):
    data = json.loads((root / name).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object: " + name)
    return data


def normalize_text(value):
    return " ".join(str(value or "").split())


def build(root):
    root = Path(root)
    registry = {}
    conflicts = []
    issues = []
    sources = Counter()

    def add(chain, code, item, region, origin):
        code = str(code).strip()
        if not code or not isinstance(item, dict):
            issues.append({"source": origin, "code": code, "reason": "invalid_entry"})
            return
        name = normalize_text(item.get("name") or item.get("storeName"))
        address = normalize_text(item.get("address"))
        if not name:
            issues.append({"source": origin, "code": code, "reason": "missing_name"})
        if not address:
            issues.append({"source": origin, "code": code, "reason": "missing_address"})
        key = chain + ":" + code
        candidate = {
            "chain": chain, "store_id": code, "name": name,
            "address": address or None, "region": region,
            "sources": [origin], "verification": "observed_in_saved_data",
        }
        sources[origin] += 1
        if key not in registry:
            registry[key] = candidate
            return
        current = registry[key]
        for field in ("name", "address", "region"):
            if current[field] and candidate[field] and current[field] != candidate[field]:
                conflicts.append({
                    "key": key, "field": field, "existing": current[field],
                    "incoming": candidate[field], "source": origin,
                })
        if not current["name"] and name:
            current["name"] = name
        if not current["address"] and address:
            current["address"] = address
        if not current["region"] and region:
            current["region"] = region
        if origin not in current["sources"]:
            current["sources"].append(origin)

    gs = read_object(root, INPUTS["gs25"])
    for region, data in gs.get("regions", {}).items():
        for code, item in data.get("stores", {}).items():
            add("gs25", code, item, region, INPUTS["gs25"])

    cu = read_object(root, INPUTS["cu"])
    for code, item in cu.get("stores", {}).items():
        city = normalize_text(item.get("city"))
        region = next((k for k, v in REGIONS.items() if v == city), None)
        if region is None:
            issues.append({"source": INPUTS["cu"], "code": code, "reason": "unknown_region"})
        add("cu", code, item, region, INPUTS["cu"])

    em = read_object(root, INPUTS["emart24"])
    for code, item in em.get("stores", {}).items():
        address = normalize_text(item.get("address"))
        region = next((k for k, v in REGIONS.items() if v + "시" in address), None)
        if region is None:
            issues.append({"source": INPUTS["emart24"], "code": code, "reason": "unknown_region"})
        add("emart24", code, item, region, INPUTS["emart24"])

    seed = read_object(root, SEED)
    for code, item in seed.get("stores", {}).items():
        add("emart24", code, item, "jeonju", SEED)

    # Name-based geographic anomalies are review candidates, not proven errors.
    # Never reassign a store or modify operational state from these hints.
    region_review_candidates = []
    for record in registry.values():
        if record["chain"] != "gs25":
            continue
        name, region = record["name"], record["region"]
        reason = None
        if region == "namwon" and "진해" in name:
            reason = "jin hae name in namwon region"
        elif region == "jeonju" and (
            "종로" in name or name in {"세종마을점", "수성동계곡점"}
        ):
            reason = "non-jeonju place name in jeonju region"
        if reason:
            region_review_candidates.append({
                "chain": "gs25", "store_id": record["store_id"],
                "name": name, "assigned_region": region,
                "reason": reason, "status": "needs_manual_review",
            })
    region_review_candidates.sort(key=lambda x: (x["assigned_region"], x["store_id"]))

    records = sorted(registry.values(), key=lambda x: (x["chain"], x["store_id"]))
    counts = dict(sorted(Counter(x["chain"] for x in records).items()))
    by_region = {chain: dict(sorted(Counter(x["region"] or "unknown" for x in records if x["chain"] == chain).items())) for chain in INPUTS}
    return {
        "schema_version": 1, "read_only": True, "records": records,
        "report": {"total_unique": len(records), "by_chain": counts,
                   "by_region": by_region, "source_rows": dict(sources),
                   "conflicts": conflicts, "issues": issues,
                   "region_review_candidates": region_review_candidates},
    }


def main():
    parser = argparse.ArgumentParser(description="Offline read-only registry audit")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(build(args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
