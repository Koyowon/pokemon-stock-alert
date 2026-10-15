"""Offline conversion of saved provider rows into strict discovery input.

Reject incomplete rows instead of silently losing them. No network or writes.
"""
import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from store_registry.discovery_adapters import normalize_saved
from store_registry.intake import validate_document
from store_registry.review_candidates import review

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
    partitions = {region: [] for region in REGIONS}
    rejected = []
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
        if reasons:
            rejected.append({"index": index, "source_key": key, "code": code,
                             "reasons": reasons})
        else:
            partitions[regions[0]].append(item)
    snapshots = [{"chain": chain, "region": region, "source": SOURCES[chain],
                  "captured_at": captured_at, "payload": {"stores": rows}}
                 for region, rows in partitions.items() if rows]
    doc = {"schema_version": 1, "snapshots": snapshots}
    validate_document(doc)
    normalized = []
    for snap in snapshots:
        accepted = normalize_saved(chain, snap["region"], snap["payload"])
        accepted_ids = [row["store_id"] for row in accepted]
        for row in snap["payload"]["stores"]:
            code = str(row.get("storeCode") or row.get("code") or "").strip()
            if code not in accepted_ids:
                rejected.append({"code": code, "reasons": ["adapter_rejected"]})
        normalized.extend(accepted)
    statuses = review(root, normalized)["counts"]
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
