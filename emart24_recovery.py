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
ALLOWED_ROUTES = {"primary": PRIMARY}


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
    url = base + "/inventory?" + urllib.parse.urlencode(params)
    open_request = urllib.request.urlopen if opener is None else opener
    sleep = time.sleep if sleeper is None else sleeper
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "PokemonStockMonitor/1.1",
                "Accept": "application/json",
            })
            with open_request(req, timeout=timeout) as response:
                payload = json.load(response)
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
