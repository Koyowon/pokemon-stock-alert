"""Conservative Asan expansion: existing 7 + registry coordinate probes.

Registry coordinates are unverified; never silently activate them.
No geocoding, external calls, state writes, or Telegram in this module.
"""
from collections import Counter
from cu_asan_registry import load_registry
from cu_stock_monitor import POINTS

def build_points(*, include_provisional=False, stores=None):
    existing = list(POINTS["아산"])
    if not include_provisional:
        return existing
    stores = load_registry() if stores is None else stores
    result = list(existing)
    for store in stores:
        if not store.get("monitor_candidate", False):
            continue
        lat, lng = store.get("latitude"), store.get("longitude")
        if lat in ("", None) or lng in ("", None):
            continue
        try:
            pair = (float(lat), float(lng))
        except (TypeError, ValueError):
            continue
        if not (36.0 <= pair[0] <= 37.5 and 126.0 <= pair[1] <= 128.0):
            continue
        if pair not in result:
            result.append(pair)
    return result

def expansion_audit(stores=None):
    stores = load_registry() if stores is None else stores
    areas = Counter(s.get("area") or "주소 미확인" for s in stores)
    return {"candidates": len(stores), "existing_points": len(POINTS["아산"]),
            "provisional_coordinate_candidates": [
                {"registry_id": s["registry_id"], "address": s["address"],
                 "latitude": s["latitude"], "longitude": s["longitude"],
                 "verified": False}
                for s in stores if s.get("latitude") not in ("", None)
                and s.get("longitude") not in ("", None)
            ],
            "areas": dict(areas)}
