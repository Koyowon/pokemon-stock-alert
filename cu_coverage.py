"""Pure CU official-directory identity and coverage helpers (no I/O)."""
import re


def normalize_name(value):
    return re.sub(r"\s+", "", re.sub(r"^(?:CU|씨유)\s*", "", str(value or ""), flags=re.I)).lower()


def road_key(value):
    match = re.search(r"([가-힣A-Za-z0-9·]+(?:대로|로|길)(?:\d+번길)?)\s+(\d+(?:-\d+)?)", str(value or ""))
    return match.groups() if match else None


def directory_identity_status(official, observed):
    if normalize_name(official.get("name")) != normalize_name(observed.get("name")):
        return "CONFLICT"
    old_road = road_key(official.get("address"))
    new_road = road_key(observed.get("address"))
    if old_road is None or new_road is None:
        return "UNCERTAIN"
    return "MATCH" if old_road == new_road else "CONFLICT"


def coverage_summary(directory, observed, enabled_cities):
    active = {code: item for code, item in directory.items()
              if any(city in item.get("address", "") for city in enabled_cities)}
    covered = set(active) & set(observed)
    return {"eligible": len(active), "observed": len(covered),
            "missing": len(active) - len(covered),
            "missing_codes": sorted(set(active) - set(observed))}
