"""Fail-closed Emart24 inventory transport. No network activity on import.

Only the documented existing proxy endpoint is enabled. An alternate URL must be
explicitly configured AND explicitly approved in code before it can be used.
"""
import os
import urllib.error
import urllib.parse
import urllib.request
import json
import time

PRIMARY = "https://mcp.aka.page/api/emart24"
OFFICIAL_V3 = "https://everse.emart24.co.kr/api/stock/v3/stock-search/store"
ALLOWED_ROUTES = {"primary": PRIMARY, "official_v3": OFFICIAL_V3}


def normalize_quantity(raw):
    if raw is None or raw == "":
        return None
    if type(raw) is int and raw >= 0:
        return raw
    if isinstance(raw, str) and raw.isascii() and raw.isdecimal():
        return int(raw)
    raise InventoryUnavailable("Invalid official quantity")


class InventoryUnavailable(RuntimeError):
    """An upstream failure; never interpret as zero inventory."""


def configured_route(environ=None):
    env = os.environ if environ is None else environ
    name = env.get("EMART24_INVENTORY_ROUTE", "primary").strip()
    if name not in ALLOWED_ROUTES:
        raise InventoryUnavailable("Unapproved Emart24 inventory route: " + name)
    return ALLOWED_ROUTES[name]


def request_inventory(params, *, environ=None, opener=None, sleeper=None,
                      attempts=2, timeout=15):
    """Return validated proxy data or raise InventoryUnavailable.

    The injected opener/sleeper allow entirely offline fixture testing.
    """
    base = configured_route(environ)
    if attempts < 1 or attempts > 2:
        raise ValueError("attempts must be 1 or 2")
    if set(params) != {"pluCd", "bizNoArr"} or not params["pluCd"] or not params["bizNoArr"]:
        raise ValueError("Missing or unexpected inventory query parameters")
    if base == OFFICIAL_V3:
        url = base + "?" + urllib.parse.urlencode({
            "searchPluCode": params["pluCd"], "bizNoArr": params["bizNoArr"]
        })
    else:
        url = base + "/inventory?" + urllib.parse.urlencode(params)
    open_request = urllib.request.urlopen if opener is None else opener
    sleep = time.sleep if sleeper is None else sleeper
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "PokemonStockMonitor/1.1",
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            })
            with open_request(req, timeout=timeout) as response:
                payload = json.load(response)
            if base == OFFICIAL_V3:
                if not isinstance(payload, dict) or not isinstance(payload.get("storeGoodsQty"), list):
                    raise InventoryUnavailable("Invalid official inventory response")
                expected = set(params["bizNoArr"].split(","))
                quantities = {}
                for row in payload["storeGoodsQty"]:
                    if not isinstance(row, dict):
                        raise InventoryUnavailable("Invalid official store row")
                    code = str(row.get("BIZNO") or "").strip()
                    if code not in expected:
                        continue
                    qty = normalize_quantity(row.get("BIZQTY"))
                    if code in quantities and quantities[code] != qty:
                        raise InventoryUnavailable("Conflicting store quantity: " + code)
                    quantities[code] = qty
                return {"stores": [
                    {"bizNo": code, "bizQty": qty}
                    for code, qty in quantities.items()
                ]}
            if not isinstance(payload, dict) or payload.get("success") is not True:
                raise InventoryUnavailable("Proxy returned unsuccessful response")
            data = payload.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("stores"), list):
                raise InventoryUnavailable("Proxy returned invalid inventory structure")
            for row in data["stores"]:
                if not isinstance(row, dict):
                    raise InventoryUnavailable("Invalid store row")
                qty = row.get("bizQty")
                if qty is not None and (type(qty) is not int or qty < 0):
                    raise InventoryUnavailable("Invalid quantity (not a confirmed zero)")
            return data
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                OSError, ValueError, InventoryUnavailable) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (400, 401, 403, 404, 429):
                break
            if attempt + 1 < attempts:
                sleep(3 * (attempt + 1))
    raise InventoryUnavailable("Emart24 inventory unavailable; quantity UNKNOWN") from None
