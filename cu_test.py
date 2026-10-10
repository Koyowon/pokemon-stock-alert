
import json
import time
import urllib.request
import urllib.error

URL = "https://www.pocketcu.co.kr/api/search/rest/stock/main"

KEYWORDS = [
    "30주년",
    "셀레브레이션",
    "포켓몬카드",
    "포켓몬",
]

def search(keyword):
    payload = {
        "searchWord": keyword,
        "prevSearchWord": "",
        "spellModifyUseYn": "Y",
        "offset": 0,
        "limit": 30,
        "searchSort": "recom",
    }

    request = urllib.request.Request(
        URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main():
    print("=== CU 30주년 상품 검색 테스트 ===", flush=True)

    for keyword in KEYWORDS:
        print(f"\n검색어: {keyword}", flush=True)

        try:
            data = search(keyword)
            result = (
                data.get("data", {})
                .get("stockResult", {})
                .get("result", {})
            )

            rows = result.get("rows", [])
            total = result.get("total_count", "UNKNOWN")

            print(f"검색 결과 수: {total}", flush=True)

            if not isinstance(rows, list):
                print("응답 구조 확인 필요", flush=True)
                print("최상위 키:", list(data.keys()))
                continue

            for row in rows:
                fields = row.get("fields", {})
                print(
                    "상품명:", fields.get("item_nm"),
                    "| 상품코드:", fields.get("item_cd"),
                    flush=True,
                )

            if not rows:
                print("검색 결과 없음 또는 응답 구조 불일치")

        except Exception as exc:
            print(
                "조회 실패:",
                type(exc).__name__,
                str(exc)[:200],
                flush=True,
            )

        time.sleep(2)

    print("\n=== 테스트 종료 ===", flush=True)


if __name__ == "__main__":
    main()
