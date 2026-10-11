"""One-time, fail-closed migration of existing monitor region selection."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def change(path, old, new):
    p=ROOT/path
    s=p.read_text(encoding='utf-8')
    if new in s:
        print('ALREADY_PATCHED',path);return
    if s.count(old)!=1:
        raise RuntimeError(f'Expected exactly one patch location in {path}; found {s.count(old)}')
    p.write_text(s.replace(old,new),encoding='utf-8')
    print('PATCHED',path)

change('monitor.py',
       '    enabled_regions = load_enabled_regions()\n',
       '    from unified_settings import enabled as unified_enabled\n    enabled_regions = unified_enabled("emart24", load_enabled_regions())\n')
change('cu_stock_monitor.py',
       '    enabled_regions = load_enabled_regions()\n',
       '    from unified_settings import enabled as unified_enabled\n    enabled_regions = unified_enabled("cu", load_enabled_regions())\n')
change('gs25_independent/gs25_auto_monitor.py',
       "    enabled = [r for r in config['regions'] if r.get('enabled')]\n    assert enabled and all(r['id'] in KEYWORDS for r in enabled)\n",
       "    sys.path.insert(0, str(ROOT.parent))\n    from unified_settings import enabled as unified_enabled\n    active = unified_enabled('gs25', {r['id'] for r in config['regions'] if r.get('enabled')})\n    enabled = [r for r in config['regions'] if r['id'] in active]\n    assert all(r['id'] in KEYWORDS for r in enabled)\n    if not enabled:\n        print('GS25_ALL_REGIONS_OFF'); return 0\n")
