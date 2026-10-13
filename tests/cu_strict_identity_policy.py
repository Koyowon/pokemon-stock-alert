"""Offline proposal only: strict CU store identity reconciliation. Never imported by production."""
import re
import unicodedata

BARCODE = "8800286275732"


def canonical(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def reconcile_strict(batches):
    """Return (accepted, quarantined). Conflicts are sticky for this observation cycle."""
    accepted, quarantined = {}, {}
    for batch in batches:
        for item in batch:
            code = item.get("code")
            if not isinstance(code, str) or not re.fullmatch(r"[0-9]+", code):
                quarantined.setdefault(str(code), set()).add("INVALID_CODE")
                continue
            if code in quarantined:
                continue
            qty = item.get("stock")
            if type(qty) is not int or qty < 0:
                quarantined.setdefault(code, set()).add("INVALID_STOCK")
                accepted.pop(code, None)
                continue
            city = canonical(item.get("city"))
            name = canonical(item.get("name"))
            address = canonical(item.get("address"))
            if not city or not name or not address:
                quarantined.setdefault(code, set()).add("MISSING_IDENTITY")
                accepted.pop(code, None)
                continue
            record = dict(item, city=city, name=name, address=address)
            previous = accepted.get(code)
            if previous is None:
                accepted[code] = record
                continue
            reasons = set()
            if previous["stock"] != qty:
                reasons.add("STOCK_CONFLICT")
            if previous["city"] != city:
                reasons.add("CITY_CONFLICT")
            if previous["name"] != name:
                reasons.add("NAME_CONFLICT")
            if previous["address"] != address:
                reasons.add("ADDRESS_CONFLICT")
            if reasons:
                quarantined[code] = reasons
                accepted.pop(code, None)
    return accepted, quarantined
