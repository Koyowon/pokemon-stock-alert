"""Per-chain overrides for Telegram controls; preserve legacy defaults."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CONTROL=ROOT/'unified_control.json'
IDS=('namwon','asan','jeonju','jeju')
CHAINS=('emart24','cu','gs25')

def load():
    if not CONTROL.exists():
        return None
    data=json.loads(CONTROL.read_text(encoding='utf-8'))
    if data.get('version')!=1 or set(data.get('chains',{}))!=set(CHAINS):
        raise ValueError('Invalid unified control')
    for chain in CHAINS:
        flags=data['chains'][chain]
        if set(flags)!=set(IDS) or any(type(flags[k]) is not bool for k in IDS):
            raise ValueError('Invalid flags for '+chain)
    return data

def enabled(chain, fallback):
    data=load()
    return {k for k,v in data['chains'][chain].items() if v} if data else set(fallback)
