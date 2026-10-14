"""Offline-only Emart24 Jeju store seed validator; no network or monitor imports."""
import json
import re
from pathlib import Path

REGION_ID = "jeju"
TARGET_BARCODE = "8800286275732"
ADDRESS_PREFIXES = ("제주특별자치도 제주시 ", "제주도 제주시 ", "제주시 ")


def validate_seed(payload):
    if not isinstance(payload, dict) or payload.get("version") != 1 or payload.get("region_id") != REGION_ID:
        raise ValueError("Jeju seed metadata missing or invalid")
    if payload.get("product_barcode") != TARGET_BARCODE:
        raise ValueError("Only 30th anniversary product is allowed")
    stores = payload.get("stores")
    if not isinstance(stores, dict) or not stores:
        raise ValueError("No verified Jeju stores: cannot activate monitoring")
    normalized = {}
    for code, row in stores.items():
        if not isinstance(code, str) or re.fullmatch(r"[0-9]{5}", code) is None:
            raise ValueError("Invalid store code")
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"].strip():
            raise ValueError("Invalid store name")
        if not isinstance(row.get("address"), str) or not row["address"].startswith(ADDRESS_PREFIXES):
            raise ValueError("Invalid Jeju address")
        if not isinstance(row.get("evidence"), str) or not row["evidence"].strip():
            raise ValueError("Missing store-code provenance")
        normalized[code] = {"name": row["name"].strip(), "address": row["address"], "evidence": row["evidence"]}
    return normalized


def readiness(seed_path, config_path):
    """Dry-run only; never enable chain or query inventory."""
    control = json.loads(Path(config_path).read_text(encoding="utf-8"))
    enabled = control["chains"]["emart24"]["jeju"]
    if type(enabled) is not bool:
        raise ValueError("Invalid Jeju feature flag")
    if not Path(seed_path).exists():
        return {"ready": False, "reason": "NO_VERIFIED_SEED", "enabled": enabled, "store_count": 0}
    try:
        stores = validate_seed(json.loads(Path(seed_path).read_text(encoding="utf-8")))
    except (ValueError, OSError, TypeError):
        return {"ready": False, "reason": "INVALID_OR_EMPTY_SEED", "enabled": enabled, "store_count": 0}
    return {"ready": True, "reason": "OFFLINE_SEED_VALID_ONLY", "enabled": enabled, "store_count": len(stores)}
