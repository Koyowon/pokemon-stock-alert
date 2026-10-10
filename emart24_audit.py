import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

BASE = "https://mcp.aka.page/api/emart24"
PLU = "8800286275732"
REGIONS = {"남원": "남원시", "아산": "아산시"}

def api(path, params):
    url = BASE + "/" + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "PokemonStockAudit/1.1",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("Unsuccessful API response")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Invalid API data")
    return data

saved = json.loads(Path("stores.json").read_text(encoding="utf-8"))
registered = saved.get("stores", {})
if not isinstance(registered, dict):
    raise ValueError("Invalid stores.json")
found = {}
errors = []

print("=== STORE DIRECTORY AUDIT ===", flush=True)
for keyword, city in REGIONS.items():
    try:
        rows = api("stores", {"keyword": keyword, "limit": 100}).get("stores")
        if not isinstance(rows, list):
            raise ValueError("Missing store list")
        matched = 0
        for item in rows:
            if not isinstance(item, dict):
                continue
            code = str(item.get("storeCode") or "").strip()
            address = str(item.get("address") or "")
            if code and city in address:
                found[code] = {
                    "name": str(item.get("storeName") or code),
                    "address": address,
                }
                matched += 1
        print(f"{city}: returned={len(rows)}, matched={matched}", flush=True)
        if len(rows) >= 100:
            print("WARNING: Search result limit reached", flush=True)
    except Exception as exc:
        errors.append(f"directory {city}: {type(exc).__name__}: {exc}")
        print("ERROR:", errors[-1], flush=True)
    time.sleep(1)

new = {k: v for k, v in found.items() if k not in registered}
print("New store candidates:", len(new), flush=True)
for code, item in sorted(new.items()):
    print(f"NEW | {code} | {item['name']} | {item['address']}", flush=True)

stores = dict(registered)
stores.update(found)
print("Total stores to inspect:", len(stores), flush=True)

print("\n=== 30TH ANNIVERSARY INVENTORY AUDIT ===", flush=True)
codes = list(stores)
statuses = {code: "NOT_CHECKED" for code in codes}
quantities = {}
batch_failures = 0

for offset in range(0, len(codes), 3):
    batch = codes[offset:offset + 3]
    try:
        rows = api("inventory", {
            "pluCd": PLU,
            "bizNoArr": ",".join(batch),
        }).get("stores")
        if not isinstance(rows, list):
            raise ValueError("Missing inventory stores list")
        returned = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("bizNo") or "").strip()
            if code not in batch:
                continue
            returned.add(code)
            qty = row.get("bizQty")
            if type(qty) is int and qty >= 0:
                statuses[code] = "NUMERIC"
                quantities[code] = qty
            elif qty is None:
                statuses[code] = "NULL"
            else:
                statuses[code] = "INVALID_QTY"
        for code in batch:
            if code not in returned:
                statuses[code] = "MISSING_IN_RESPONSE"
    except Exception as exc:
        batch_failures += 1
        for code in batch:
            statuses[code] = "BATCH_ERROR"
        print(f"BATCH_ERROR | {','.join(batch)} | {type(exc).__name__}: {exc}", flush=True)
        if batch_failures >= 3:
            print("WARNING: Three failed batches; remaining stores skipped", flush=True)
            break
    time.sleep(1.5)

for code, status in statuses.items():
    store = stores.get(code, {})
    qty = quantities.get(code)
    suffix = f" | qty={qty}" if qty is not None else ""
    print(f"STORE | {code} | {store.get('name', code)} | {status}{suffix}", flush=True)

print("\n=== SUMMARY ===", flush=True)
for status, count in sorted(Counter(statuses.values()).items()):
    print(f"{status}: {count}", flush=True)
print("New store candidates:", len(new), flush=True)
print("Directory errors:", len(errors), flush=True)
print("Inventory failed batches:", batch_failures, flush=True)
print("Read-only diagnostic. No files changed. No Telegram sent.", flush=True)
