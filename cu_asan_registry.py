"""Asan CU candidate observation classifier. No network or notification calls."""
import json
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


def classify_observations(observed_by_code, *, query_succeeded=False):
    """An absent store is NOT_OBSERVED, never ZERO_STOCK.

    Only explicitly returned nonnegative integer stock values count as
    observed. Successful geographic queries do not establish that every
    registered store was within API coverage.
    """
    result = []
    for store in load_registry():
        code = str(store.get("cu_store_code") or "").strip()
        stock = None
        status = "NOT_OBSERVED" if query_succeeded else "NOT_QUERIED"
        if code and code in observed_by_code:
            stock = observed_by_code[code]
            if type(stock) is int and stock >= 0:
                status = "ZERO_STOCK" if stock == 0 else "IN_STOCK"
            else:
                status = "NO_VALID_STOCK_VALUE"
        result.append({
            "registry_id": store["registry_id"],
            "name": store["name"],
            "cu_store_code": code,
            "status": status,
            "stock": stock,
        })
    return result


def summarize_observations(observed_by_code, *, query_succeeded=False):
    """Print an audit summary without changing alert or persisted stock state."""
    rows = classify_observations(
        observed_by_code, query_succeeded=query_succeeded
    )
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print("ASAN_CU_REGISTRY_CANDIDATES:", len(rows), flush=True)
    print("ASAN_CU_REGISTRY_STATUS:", json.dumps(
        counts, ensure_ascii=False, sort_keys=True
    ), flush=True)
    return rows
