import urllib.request
import urllib.error
import urllib.parse

BASE = "https://mcp.aka.page/api/seveneleven"

TESTS = [
    ("인페르노X 상품검색", "/products", {"query": "인페르노X", "format": "html"}),
    ("30주년 상품검색", "/products", {"query": "비전)포켓몬확장팩(30주년)_H", "format": "html"}),
    ("남원 재고조회", "/inventory", {"keyword": "인페르노X", "storeKeyword": "남원", "storeLimit": "10", "format": "html"}),
    ("아산 재고조회", "/inventory", {"keyword": "인페르노X", "storeKeyword": "아산", "storeLimit": "10", "format": "html"}),
]

for name, path, params in TESTS:
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    print("\n" + "=" * 50)
    print("TEST:", name)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(3000).decode("utf-8", errors="replace")
            print("HTTP:", response.status)
            print("BODY:", body[:1500])
    except urllib.error.HTTPError as error:
        print("HTTP:", error.code)
        print("ERROR:", error.read(1500).decode("utf-8", errors="replace"))
    except Exception as error:
        print("ERROR:", type(error).__name__, str(error))

print("\n진단 완료. HTTP 502는 품절을 의미하지 않습니다.")
