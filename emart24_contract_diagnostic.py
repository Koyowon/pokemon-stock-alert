"""Offline Emart24 request/response contract checks; no network or state I/O."""
import json
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit, parse_qs

BASE_URL = "https://mcp.aka.page/api/emart24/inventory"
PRODUCT_PLU = "8800286275732"

class Outcome(str, Enum):
    HTTP_502 = "HTTP_502"
    REQUEST_MISMATCH = "REQUEST_MISMATCH"
    INVALID_JSON = "INVALID_JSON"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    ZERO_STOCK = "ZERO_STOCK"
    OK = "OK"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True)
class ContractResult:
    outcome: Outcome
    verified: int = 0
    unknown: int = 0
    zero_stock: int = 0

def check_request(url, expected_stores, method="GET"):
    """Validate locally constructed URL; never fetch it."""
    if not isinstance(url, str) or not isinstance(expected_stores, (list, tuple)):
        return ContractResult(Outcome.REQUEST_MISMATCH)
    parts, expected = urlsplit(url), urlsplit(BASE_URL)
    query = parse_qs(parts.query, keep_blank_values=True)
    if (method != "GET" or
        (parts.scheme, parts.netloc, parts.path) != (expected.scheme, expected.netloc, expected.path) or
        parts.fragment or set(query) != {"pluCd", "bizNoArr"} or
        query.get("pluCd") != [PRODUCT_PLU] or len(query.get("bizNoArr", [])) != 1 or
        not 1 <= len(expected_stores) <= 3 or
        any(not isinstance(code, str) or not code.isdigit() for code in expected_stores) or
        query["bizNoArr"][0].split(",") != list(expected_stores) or
        len(set(expected_stores)) != len(expected_stores)):
        return ContractResult(Outcome.REQUEST_MISMATCH)
    return ContractResult(Outcome.OK)

def check_response(status_code, raw_json, expected_stores):
    """Classify supplied HTTP status and synthetic JSON; no live requests."""
    if status_code == 502:
        return ContractResult(Outcome.HTTP_502, unknown=len(expected_stores))
    if status_code != 200:
        return ContractResult(Outcome.UNKNOWN, unknown=len(expected_stores))
    try:
        payload = json.loads(raw_json)
    except (TypeError, ValueError):
        return ContractResult(Outcome.INVALID_JSON, unknown=len(expected_stores))
    if (not isinstance(payload, dict) or payload.get("success") is not True or
        not isinstance(payload.get("data"), dict) or
        not isinstance(payload["data"].get("stores"), list)):
        return ContractResult(Outcome.INVALID_RESPONSE, unknown=len(expected_stores))
    if (not isinstance(expected_stores, (list, tuple)) or not expected_stores or
        len(set(expected_stores)) != len(expected_stores)):
        return ContractResult(Outcome.REQUEST_MISMATCH)
    verified = {}
    for row in payload["data"]["stores"]:
        if not isinstance(row, dict):
            continue
        code = str(row.get("bizNo") or "").strip()
        qty = row.get("bizQty")
        if code in expected_stores and type(qty) is int and qty >= 0:
            verified[code] = qty
    count = len(verified)
    missing = len(expected_stores) - count
    zero = sum(qty == 0 for qty in verified.values())
    outcome = (Outcome.UNKNOWN if count == 0 else
               Outcome.PARTIAL if missing else
               Outcome.ZERO_STOCK if zero == count else Outcome.OK)
    return ContractResult(outcome, count, missing, zero)
