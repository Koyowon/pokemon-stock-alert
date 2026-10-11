"""Initialize Jeonju numeric inventory baseline without Telegram or monitor imports.
Preserves every pre-existing state key. Must run while Jeonju region is OFF.
"""
import json
import os
import sys
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEED = ROOT / 'emart24_jeonju_seed.json'
SETTINGS = ROOT / 'region_settings.json'
STATE = ROOT / 'state.json'
PLU = '8800286275732'
URL = 'https://mcp.aka.page/api/emart24/inventory'
BATCH_SIZE = 3


def load_json(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path.name} must be a JSON object')
    return data


def validate():
    settings = load_json(SETTINGS)
    rows = settings.get('regions', [])
    flags = {r['id']: r['enabled'] for r in rows}
    if flags.get('namwon') is not True or flags.get('asan') is not True or flags.get('jeonju') is not False:
        raise ValueError('Safety gate: Namwon/Asan must be ON and Jeonju must be OFF')
    seed = load_json(SEED)
    stores = seed.get('stores')
    if seed.get('version') != 1 or seed.get('region_id') != 'jeonju' or not isinstance(stores, dict) or len(stores) != 63:
        raise ValueError('Invalid Jeonju 63-store seed')
    districts = Counter()
    for code, item in stores.items():
        if not (isinstance(code, str) and code.isdigit() and isinstance(item, dict) and
                isinstance(item.get('name'), str) and item['name'].strip() and
                isinstance(item.get('address'), str)):
            raise ValueError(f'Invalid seed store: {code}')
        address = item['address']
        match = [d for d in ('완산구', '덕진구') if address.startswith(f'전북특별자치도 전주시 {d} ')]
        if len(match) != 1:
            raise ValueError(f'Invalid district: {code}')
        districts[match[0]] += 1
    if districts != {'완산구': 27, '덕진구': 36}:
        raise ValueError(f'Unexpected district totals: {districts}')
    old = load_json(STATE)
    for key, value in old.items():
        if not isinstance(key, str) or type(value) is not int or value < 0:
            raise ValueError('Existing state has invalid key/value; refusing to change it')
    if len(old) == 0:
        raise ValueError('Existing state is empty; refusing to initialize')
    if any(f'이마트24|{code}|{PLU}' in old for code in stores):
        raise ValueError('Jeonju baseline already exists: refusing to overwrite any Jeonju record')
    return sorted(stores), old


def request_batch(codes):
    query = urllib.parse.urlencode({'pluCd': PLU, 'bizNoArr': ','.join(codes)})
    req = urllib.request.Request(URL + '?' + query, headers={
        'User-Agent': 'PokemonStockMonitor/1.1', 'Accept': 'application/json'
    })
    with urllib.request.urlopen(req, timeout=15) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get('success') is not True:
        raise ValueError('Unsuccessful inventory response')
    data = payload.get('data')
    if not isinstance(data, dict) or not isinstance(data.get('stores'), list):
        raise ValueError('Invalid inventory response structure')
    found = {}
    for row in data['stores']:
        if not isinstance(row, dict):
            continue
        code = str(row.get('bizNo') or '').strip()
        if code in codes:
            qty = row.get('bizQty')
            if type(qty) is int and qty >= 0:
                found[code] = qty
    return found


def main():
    codes, original = validate()
    print(f'JEONJU_BASELINE_START STORES={len(codes)} PREEXISTING_KEYS={len(original)}', flush=True)
    numbers = {}
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i:i+BATCH_SIZE]
        try:
            found = request_batch(batch)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise RuntimeError(f'Batch {i//BATCH_SIZE+1} failed: {type(exc).__name__}: {exc}') from exc
        numbers.update(found)
        print(f'BATCH={i//BATCH_SIZE+1}/21 NUMERIC={len(found)} UNKNOWN={len(batch)-len(found)}', flush=True)
        if i+BATCH_SIZE < len(codes):
            time.sleep(2)
    if not numbers:
        raise RuntimeError('No numeric results; state will not be modified')
    # Fail closed on unexpectedly low coverage; unknown stores remain uninitialized.
    if len(numbers) < 40:
        raise RuntimeError(f'Only {len(numbers)}/63 numeric results (minimum 40); no state changes')
    # Recheck settings and state immediately before writing.
    codes_again, current = validate()
    if codes_again != codes or current != original:
        raise RuntimeError('State or seed changed during run; refusing to overwrite')
    updated = dict(original)
    for code, qty in numbers.items():
        updated[f'이마트24|{code}|{PLU}'] = qty
    if any(updated.get(key) != value for key, value in original.items()):
        raise RuntimeError('Existing state changed unexpectedly')
    fd, temp_name = tempfile.mkstemp(prefix='.jeonju-baseline-', suffix='.json', dir=ROOT)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(updated, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temp_name, STATE)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    print(f'JEONJU_BASELINE_SUCCESS PRESERVED={len(original)} INITIALIZED={len(numbers)} UNKNOWN={63-len(numbers)}', flush=True)
    print('UNKNOWN stores are not zero; first positive result there may still trigger a first-stock alert.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'JEONJU_BASELINE_FAILED: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
