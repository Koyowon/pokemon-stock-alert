import json
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://mcp.aka.page/api/gs25/products'
QUERIES = ['인페르노X', '8800286275732', '30주년', '셀레브레이션']

def fetch(query):
    url = BASE + '?' + urllib.parse.urlencode({'keyword': query, 'limit': 30})
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read(100000).decode('utf-8', errors='replace')
            print('HTTP:', resp.status)
            try:
                obj = json.loads(data)
                print(json.dumps(obj, ensure_ascii=False, indent=2)[:12000])
            except json.JSONDecodeError:
                print('Non-JSON response:', data[:500])
    except urllib.error.HTTPError as exc:
        print('HTTP ERROR:', exc.code)
        print(exc.read(400).decode('utf-8', errors='replace'))
    except Exception as exc:
        print('REQUEST ERROR:', type(exc).__name__, str(exc))

for q in QUERIES:
    print('\n' + '=' * 60)
    print('SEARCH:', q)
    fetch(q)
