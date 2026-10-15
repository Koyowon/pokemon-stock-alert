"""Pure offline adapters for saved CU and emart24 discovery responses.

No network, Telegram, state mutation, or implicit verification of provider claims.
"""
import re
from store_registry.build_registry import normalize_text

CU_PREFIXES = {
    "namwon": ("전라북도 남원시", "전북특별자치도 남원시", "전북 남원시"),
    "asan": ("충청남도 아산시", "충남 아산시"),
    "jeonju": ("전라북도 전주시", "전북특별자치도 전주시", "전북 전주시"),
    "jeju": ("제주특별자치도 제주시", "제주도 제주시", "제주시 "),
}
EMART_MARKERS = {
    "namwon": ("남원시",), "asan": ("아산시",),
    "jeonju": ("전주시",), "jeju": ("제주시", "서귀포시"),
}


def _items(payload, chain):
    if not isinstance(payload, dict):
        raise ValueError("saved response must be a JSON object")
    if chain == "cu":
        # Parsed CU HTML tokens are converted into store dicts by the existing monitor.
        rows = payload.get("stores")
        if not isinstance(rows, list):
            raise ValueError("CU parsed stores must be a list")
        return rows
    rows = payload.get("stores")
    if isinstance(rows, dict):
        return [dict(value, storeCode=key) if isinstance(value, dict)
                else {"storeCode": key} for key, value in rows.items()]
    if isinstance(rows, list):
        return rows
    raise ValueError("emart24 stores must be a list or mapping")


def normalize_saved(chain, region, payload):
    """Convert previously captured provider results to review-only candidate rows."""
    if chain not in ("cu", "emart24") or region not in CU_PREFIXES:
        raise ValueError("unsupported chain or region")
    result = []
    for row in _items(payload, chain):
        if not isinstance(row, dict):
            continue
        code = normalize_text(row.get("storeCode") or row.get("code"))
        name = normalize_text(row.get("storeName") or row.get("name"))
        address = normalize_text(row.get("address"))
        if chain == "cu":
            # Mirror the existing CU monitor's conservative address validation.
            location_ok = address.startswith(CU_PREFIXES[region])
            code_ok = bool(re.fullmatch(r"[0-9]+", code))
            # No inferred stock quantity: candidate evidence is never fabricated.
        else:
            location_ok = any(marker in address for marker in EMART_MARKERS[region])
            code_ok = bool(re.fullmatch(r"[0-9]+", code))
        if not (code_ok and name and address and location_ok):
            continue
        result.append({"chain": chain, "store_id": code, "name": name,
                       "address": address, "region": region})
    return result


def compare_saved(root, chain, region, payload):
    """Review saved discovery data against the current offline main snapshot."""
    from store_registry.review_candidates import review
    candidates = normalize_saved(chain, region, payload)
    return review(root, candidates)
