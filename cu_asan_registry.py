"""Asan CU candidate observation classifier. No network or notification calls."""
import json
import re
from collections import Counter
from pathlib import Path

REGISTRY_FILE = Path(__file__).with_name("asan_cu_watch_registry.json")
PRODUCT_BARCODE = "8800286275732"


def load_registry(path=REGISTRY_FILE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("product_barcode") != PRODUCT_BARCODE:
        raise ValueError("Unexpected CU product barcode")
    stores = data.get("stores")
    if not isinstance(stores, list) or len(stores) != 119:
        raise ValueError("Expected exactly 119 Asan CU candidates")
    ids = [s["registry_id"] for s in stores]
    if len(set(ids)) != 119:
        raise ValueError("Duplicate Asan CU registry IDs")
    return stores


def normalize_name(value):
    value = re.sub(r"^(?:씨유|CU)\s*", "", str(value or "").strip(), flags=re.I)
    return re.sub(r"[^0-9a-z가-힣]", "", value.lower())


def normalize_address(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"^(?:충남|충청남도)\s+", "", value)
    return re.sub(r"\s+", "", value)


def classify_observations(observed_by_code, *, query_succeeded=False):
    """Match by verified code, or uniquely exact name AND address.

    Never infer zero stock from absence. Never persist an inferred store code.
    observed_by_code accepts API store dicts; legacy numeric-only values remain
    supported for code matches.
    """
    stores = load_registry()
    api = {}
    for code, value in observed_by_code.items():
        code = str(code).strip()
        if isinstance(value, dict):
            api[code] = value
        else:
            api[code] = {"stock": value}

    by_identity = {}
    for code, item in api.items():
        name = normalize_name(item.get("name"))
        address = normalize_address(item.get("address"))
        if name and address:
            by_identity.setdefault((name, address), []).append(code)

    registry_keys = [
        (normalize_name(s.get("name")), normalize_address(s.get("address")))
        for s in stores
    ]
    key_counts = Counter(k for k in registry_keys if all(k))
    claimed_codes = set()
    result = []
    for store, key in zip(stores, registry_keys):
        configured_code = str(store.get("cu_store_code") or "").strip()
        status = "NOT_OBSERVED" if query_succeeded else "NOT_QUERIED"
        matched_code = ""
        method = ""
        if configured_code and configured_code in api:
            matched_code = configured_code
            method = "REGISTERED_CODE"
        elif not configured_code and all(key) and key_counts[key] == 1:
            candidates = by_identity.get(key, [])
            if len(candidates) == 1:
                matched_code = candidates[0]
                method = "EXACT_NAME_ADDRESS"

        stock = None
        if matched_code and matched_code not in claimed_codes:
            claimed_codes.add(matched_code)
            stock = api[matched_code].get("stock")
            if type(stock) is int and stock >= 0:
                status = "ZERO_STOCK" if stock == 0 else "IN_STOCK"
            else:
                status = "NO_VALID_STOCK_VALUE"
        elif matched_code:
            matched_code = ""
            method = ""
        result.append({
            "registry_id": store["registry_id"],
            "name": store["name"],
            "cu_store_code": configured_code,
            "observed_store_code": matched_code,
            "match_method": method,
            "status": status,
            "stock": stock,
        })
    return result


def summarize_observations(observed_by_code, *, query_succeeded=False):
    """Print audit summary without changing alert or persisted stock state."""
    rows = classify_observations(
        observed_by_code, query_succeeded=query_succeeded
    )
    counts = Counter(row["status"] for row in rows)
    methods = Counter(row["match_method"] for row in rows if row["match_method"])
    print("ASAN_CU_REGISTRY_CANDIDATES:", len(rows), flush=True)
    print("ASAN_CU_REGISTRY_STATUS:", json.dumps(
        dict(counts), ensure_ascii=False, sort_keys=True
    ), flush=True)
    print("ASAN_CU_MATCH_METHODS:", json.dumps(
        dict(methods), ensure_ascii=False, sort_keys=True
    ), flush=True)
    for row in rows:
        if row["match_method"] == "EXACT_NAME_ADDRESS":
            print("ASAN_CU_AUTO_MATCH:", row["registry_id"],
                  row["observed_store_code"], flush=True)
    return rows
