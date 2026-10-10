"""Read-only GS25 access diagnostic. Does not request, store, or print login credentials."""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://b2c-bff.woodongs.com'
LOCATION = (35.4164, 127.3904)  # Namwon city-center reference, not a personal address
PRODUCTS = [('KNOWN_INFERNO_X', '8800286278535'), ('TARGET_30TH', '8800286275732')]

def probe(name, path, params=None):
    url = BASE + path + ('?' + urllib.parse.urlencode(params) if params else '')
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'GS25-readonly-diagnostic/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read(30000)
            status = r.status
            content_type = r.headers.get('Content-Type', '')
    except urllib.error.HTTPError as e:
        status = e.code
        content_type = e.headers.get('Content-Type', '')
        body = b''  # Never expose error bodies or possible credentials.
    except Exception as e:
        print(f'{name}: NETWORK_ERROR={type(e).__name__}')
        return
    print(f'{name}: HTTP={status} CONTENT_TYPE={content_type.split(";")[0]}')
    if status != 200:
        return
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        print(f'{name}: RESPONSE=NON_JSON')
        return
    if isinstance(data, dict):
        stores = data.get('stores')
        if isinstance(stores, list):
            print(f'{name}: STORES={len(stores)}')
            # Do not equate an empty list with sold out.
        else:
            print(f'{name}: JSON_KEYS={sorted(data.keys())[:8]}')
    else:
        print(f'{name}: JSON_TYPE={type(data).__name__}')

print('GS25 read-only access diagnostic; no account session or secrets used.')
probe('HEALTH', '/api/alive')
lat, lng = LOCATION
for label, barcode in PRODUCTS:
    probe(label, '/api/bff/v2/store/stock', {
        'serviceCode': '01', 'itemCode': barcode,
        'myPositionXCoordination': lng, 'myPositionYCoordination': lat,
        'centerPositionXCoordination': lng, 'centerPositionYCoordination': lat,
        'radiusCondition': 500, 'pickupStoreYn': 'N',
        'realTimeStockYn': 'Y', 'pageNumber': 0, 'pageCount': 100,
    })
