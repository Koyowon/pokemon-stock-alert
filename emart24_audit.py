import json
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://mcp.aka.page/api/emart24"
PRODUCT = "8800286275732"
REGIONS = {
    "남원": ("남원시", ["남원", "남원시"]),
    "아산": ("아산시", ["아산", "아산시"]),
}

saved = json.loads(Path("stores.json").read_text(encoding="utf-8"))
registered = saved.get("stores", {})
found = {}
errors = []

def request(path, params):
    url = BASE + "/" + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"User-Agent": "PokemonStockAudit/1.0", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        body = json.load(response)
    if body.get("success") is not True or not isinstance(body.get("data"), dict):
        raise ValueError("Invalid API response")
    return body["data"]

print("=== EMART24 STORE DIRECTORY AUDIT ===")
print("Registered stores:", len(registered))

for region, (city, keywords) in REGIONS.items():
    for keyword in keywords:
        try:
            data = request("stores", {"keyword": keyword, "limit": 100})
            rows = data.get("stores", [])
            if not isinstance(rows, list):
                raise ValueError("Missing stores list")
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
            print(f"{region} / {keyword}: returned={len(rows)}, matched={matched}")
            if len(rows) >= 100:
                print("WARNING: Result limit reached; pagination may be needed")
        except Exception as exc:
            errors.append(f"{region}/{keyword}: {type(exc).__name__}: {exc}")
            print("ERROR:", errors[-1])

missing = {code: item for code, item in found.items() if code not in registered}
unverified = {code: item for code, item in registered.items() if code not in found}

print("\n=== NEW STORE CANDIDATES ===")
for code, item in sorted(missing.items()):
    print(f"NEW | {code} | {item['name']} | {item['address']}")
print("New candidates:", len(missing))

print("\n=== REGISTERED BUT NOT FOUND ===")
for code, item in sorted(unverified.items()):
    print(f"UNVERIFIED | {code} | {item.get('name')} | {item.get('address')}")
print("Unverified registered stores:", len(unverified))

print("\n=== SUMMARY ===")
print("Unique stores discovered:", len(found))
print("Registered stores:", len(registered))
print("Search errors:", len(errors))
print("No inventory state was changed. No Telegram messages were sent.")
