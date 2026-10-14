"""Offline evidence intake: review only, never writes store codes or calls APIs."""
import csv
import json
import re
from collections import Counter
from pathlib import Path

TARGET = "8800286275732"
FIELDS = {"chain", "registry_id", "store_code", "name", "address", "source_url", "observed_at", "barcode"}

def norm(value):
    return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower()).removeprefix("씨유").removeprefix("cu")

def evaluate(row, existing=(), candidates=None):
    if row.get("chain") not in ("cu", "emart24"):
        return "REJECT_CHAIN"
    if row.get("barcode") != TARGET:
        return "REJECT_BARCODE"
    code = str(row.get("store_code") or "").strip()
    if not re.fullmatch(r"[0-9]+", code):
        return "REJECT_CODE"
    if code in set(map(str, existing)):
        return "REJECT_CODE_COLLISION"
    if not str(row.get("source_url") or "").startswith(("https://", "http://")) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(row.get("observed_at") or "")):
        return "REJECT_PROVENANCE"
    if not norm(row.get("name")) or not norm(row.get("address")):
        return "REJECT_IDENTITY"
    if row["chain"] == "cu":
        if not candidates or row.get("registry_id") not in candidates:
            return "REJECT_UNKNOWN_REGISTRY_ID"
        candidate = candidates[row["registry_id"]]
        if norm(row["name"]) != norm(candidate.get("name")):
            return "REJECT_NAME_MISMATCH"
        if norm(row["address"]) != norm(candidate.get("address")):
            return "REJECT_ADDRESS_MISMATCH"
    elif not str(row["address"]).strip().startswith(("제주특별자치도 제주시 ", "제주도 제주시 ", "제주시 ")):
        return "REJECT_NOT_JEJU"
    return "MANUAL_REVIEW_REQUIRED"

def review_csv(evidence_path, registry_path, cu_state_path, emart_cache_path):
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))["stores"]
    candidates = {r["registry_id"]: r for r in registry if not r.get("cu_store_code")}
    used_cu = {str(r["cu_store_code"]) for r in registry if r.get("cu_store_code")}
    used_cu.update(map(str, json.loads(Path(cu_state_path).read_text(encoding="utf-8"))["stores"]))
    used_emart = set(json.loads(Path(emart_cache_path).read_text(encoding="utf-8"))["stores"])
    with Path(evidence_path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or FIELDS - set(reader.fieldnames):
            raise ValueError("Missing evidence columns")
        rows = list(reader)
    counts = Counter((r.get("chain"), str(r.get("store_code") or "").strip()) for r in rows)
    output = []
    for row in rows:
        status = evaluate(row, used_cu if row.get("chain") == "cu" else used_emart, candidates)
        if status == "MANUAL_REVIEW_REQUIRED" and counts[(row["chain"], row["store_code"].strip())] > 1:
            status = "REJECT_BATCH_DUPLICATE"
        output.append({"chain": row.get("chain"), "registry_id": row.get("registry_id"),
                       "store_code": row.get("store_code"), "status": status})
    return output

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("evidence_csv")
    p.add_argument("--registry", default="asan_cu_watch_registry.json")
    p.add_argument("--cu-state", default="cu_stock_state.json")
    p.add_argument("--emart-cache", default="stores.json")
    args = p.parse_args()
    print(json.dumps(review_csv(args.evidence_csv, args.registry, args.cu_state, args.emart_cache), ensure_ascii=False, indent=2))
