"""Offline conversion of saved provider rows into strict discovery input.

Reject incomplete rows instead of silently losing them. No network or writes.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from store_registry.discovery_adapters import normalize_saved
from store_registry.intake import validate_document
from store_registry.review_candidates import review
from store_registry.build_registry import build

REGIONS = ("namwon", "asan", "jeonju", "jeju")
REGION_MARKERS = {
    "namwon": ("남원시",), "asan": ("아산시",),
    "jeonju": ("전주시",), "jeju": ("제주시", "서귀포시"),
}
SOURCES = {"cu": "cu_parsed_inventory", "emart24": "emart24_store_directory"}


def convert(root, chain, captured_at, payload):
    if chain not in SOURCES:
        raise ValueError("unsupported chain")
    if not isinstance(payload, dict) or not isinstance(payload.get("stores"), (list, dict)):
        raise ValueError("stores must be list or mapping")
    entries = payload["stores"]
    if chain == "cu" and not isinstance(entries, list):
        raise ValueError("CU stores must be list")
    if len(entries) > 2000:
        raise ValueError("too many stores")
    source_rows = []
    for code, item in (entries.items() if isinstance(entries, dict)
                       else enumerate(entries)):
        if not isinstance(item, dict):
            source_rows.append((str(code), {}))
        else:
            source_rows.append((str(code), dict(item, storeCode=code)
                                if isinstance(entries, dict) else item))
    # Audit every original row; quarantine every identity involved in a collision.
    existing = {(r["chain"], r["store_id"]): r for r in build(root)["records"]}
    groups = defaultdict(list)
    examined = []
    for index, (key, item) in enumerate(source_rows):
        code = str(item.get("storeCode") or item.get("code") or "").strip()
        name = str(item.get("storeName") or item.get("name") or "").strip()
        address = str(item.get("address") or "").strip()
        regions = [region for region, markers in REGION_MARKERS.items()
                   if any(marker in address for marker in markers)]
        reasons = []
        if not re.fullmatch(r"[0-9]+", code): reasons.append("invalid_store_code")
        if not name: reasons.append("missing_name")
        if not address: reasons.append("missing_address")
        if len(regions) != 1: reasons.append("ambiguous_or_outside_region")
        # CU normalization only supports addresses with an explicit accepted prefix.
        region = regions[0] if len(regions) == 1 else None
        if region and chain == "cu":
            from store_registry.discovery_adapters import CU_PREFIXES
            if not address.startswith(CU_PREFIXES[region]):
                reasons.append("adapter_region_prefix_mismatch")
        old = existing.get((chain, code))
        if old and any(old.get(field) and old[field] != value for field, value in (
                ("name", name), ("address", address), ("region", region))):
            reasons.append("existing_identity_conflict")
        entry = {"index": index, "source_key": key, "code": code,
                 "name": name, "address": address, "region": region,
                 "reasons": reasons, "row": item}
        examined.append(entry)
        if re.fullmatch(r"[0-9]+", code):
            groups[code].append(entry)
    for entries in groups.values():
        if len(entries) > 1:
            identities = {(e["name"], e["address"], e["region"]) for e in entries}
            reason = ("submission_identity_conflict" if len(identities) > 1
                      else "duplicate_store_code")
            for entry in entries:
                entry["reasons"].append(reason)

    partitions = {region: [] for region in REGIONS}
    rejected = []
    for entry in examined:
        if entry["reasons"]:
            rejected.append({k: entry[k] for k in ("index", "source_key", "code", "reasons")})
        else:
            partitions[entry["region"]].append(entry["row"])
    snapshots = [{"chain": chain, "region": region, "source": SOURCES[chain],
                  "captured_at": captured_at, "payload": {"stores": rows}}
                 for region, rows in partitions.items() if rows]
    doc = {"schema_version": 1, "snapshots": snapshots}
    validate_document(doc)
    normalized = []
    for snap in snapshots:
        rows = snap["payload"]["stores"]
        accepted = normalize_saved(chain, snap["region"], snap["payload"])
        if len(accepted) != len(rows):
            raise ValueError("adapter silently dropped rows; refusing partial conversion")
        normalized.extend(accepted)
    statuses = review(root, normalized)["counts"]
    if sum(statuses.values()) != len(normalized):
        raise ValueError("review row accounting mismatch")
    if len(normalized) + len(rejected) != len(source_rows):
        raise ValueError("conversion row accounting mismatch")
    return {"document": doc, "report": {
        "source_rows": len(source_rows), "accepted_rows": len(normalized),
        "rejected_rows": len(rejected), "rejected": rejected,
        "statuses": statuses, "new_unverified": statuses.get("pending_approval", 0),
        "approved_for_production": 0, "read_only": True}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--chain", choices=tuple(SOURCES), required=True)
    parser.add_argument("--captured-at", required=True)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    if args.input.stat().st_size > 2_000_000:
        raise ValueError("input too large")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = convert(args.root, args.chain, args.captured_at, payload)
    # stdout only: do not create files or touch production state.
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
