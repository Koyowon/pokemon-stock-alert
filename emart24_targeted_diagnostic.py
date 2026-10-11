"""Read-only Emart24 targeted store search diagnostic.
No Telegram, inventory calls, state writes, or cache writes.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://mcp.aka.page/api/emart24/stores"
# Small, specific terms help distinguish a broad-query server error
# from a complete search-service outage.
SEARCHES = {
    "전주 덕진구": [
        "덕진구", "송천", "인후", "금암", "우아", "팔복",
    ],
    "제주시": [
        "제주시", "연동", "노형", "이도", "애월읍", "조천읍",
    ],
}
PREFIXES = {
    "전주 덕진구": (
        "전북특별자치도 전주시 덕진구",
        "전라북도 전주시 덕진구",
        "전북 전주시 덕진구",
    ),
    "제주시": (
        "제주특별자치도 제주시",
        "제주도 제주시",
        "제주시 ",
    ),
}
LIMIT = 30


def search(keyword):
    url = BASE + "?" + urllib.parse.urlencode({
        "keyword": keyword, "limit": LIMIT,
    })
    request = urllib.request.Request(url, headers={
        "User-Agent": "PokemonRegionDiagnostic/1.1",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(request, timeout=18) as response:
        data = json.load(response)
    if not isinstance(data, dict) or data.get("success") is not True:
        raise ValueError("API success was not true")
    body = data.get("data")
    if not isinstance(body, dict) or not isinstance(body.get("stores"), list):
        raise ValueError("Invalid store response")
    return body["stores"]


def run():
    print("EMART24_TARGETED_DIAGNOSTIC_START", flush=True)
    for region, keywords in SEARCHES.items():
        stores = {}
        successes = 0
        errors = 0
        for keyword in keywords:
            try:
                rows = search(keyword)
                matched = 0
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    code = str(row.get("storeCode") or "").strip()
                    address = " ".join(str(row.get("address") or "").split())
                    if code and any(
                        address.startswith(prefix) for prefix in PREFIXES[region]
                    ):
                        stores[code] = {
                            "name": str(row.get("storeName") or code),
                            "address": address,
                        }
                        matched += 1
                successes += 1
                print(
                    f"QUERY_OK region={region} keyword={keyword} "
                    f"returned={len(rows)} matched={matched} "
                    f"at_limit={len(rows) >= LIMIT}",
                    flush=True,
                )
            except urllib.error.HTTPError as exc:
                errors += 1
                print(
                    f"QUERY_HTTP_ERROR region={region} keyword={keyword} "
                    f"status={exc.code}", flush=True,
                )
                if exc.code in (403, 429):
                    print("RATE_OR_ACCESS_LIMIT_STOP", flush=True)
                    break
            except (OSError, ValueError, TimeoutError) as exc:
                errors += 1
                print(
                    f"QUERY_ERROR region={region} keyword={keyword} "
                    f"type={type(exc).__name__} detail={str(exc)[:100]}",
                    flush=True,
                )
            time.sleep(1.5)

        print(
            f"REGION_SUMMARY region={region} ok={successes} "
            f"failed={errors} unique_stores={len(stores)}",
            flush=True,
        )
        for code, store in sorted(stores.items()):
            print(
                f"STORE region={region} code={code} "
                f"name={store['name']} address={store['address']}",
                flush=True,
            )
    print("EMART24_TARGETED_DIAGNOSTIC_FINISHED", flush=True)


if __name__ == "__main__":
    run()
