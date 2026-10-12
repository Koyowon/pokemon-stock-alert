"""Integrate the conservative Asan GS25 guard into the existing monitor.
Run from repository root: python3 integrate_gs25_guard.py
Idempotent; creates .bak and does not touch stock state.
"""
from pathlib import Path
import ast
import shutil

path = Path('gs25_independent/gs25_auto_monitor.py')
original = path.read_text(encoding='utf-8')
import_line = 'from gs25_asan_guard import filter_asan_seen\n'
anchor = "ROOT = Path(__file__).resolve().parent\n"
block_anchor = "        positives = {sid: item for sid, item in seen.items() if item['quantity'] > 0}\n"
filter_block = ("        if rid == 'asan' and not failed:\n"
                "            prior_asan = previous.get('regions', {}).get('asan')\n"
                "            before_guard = len(seen)\n"
                "            seen = filter_asan_seen(seen, prior_asan)\n"
                "            print(f'ASAN_GUARD kept={len(seen)} excluded={before_guard - len(seen)}', flush=True)\n")
if import_line not in original:
    if original.count(anchor) != 1:
        raise RuntimeError('Cannot locate unique ROOT anchor; no changes made')
    changed = original.replace(anchor, anchor + import_line, 1)
else:
    changed = original
if filter_block not in changed:
    if changed.count(block_anchor) != 1:
        raise RuntimeError('Cannot locate unique positives anchor; no changes made')
    changed = changed.replace(block_anchor, filter_block + block_anchor, 1)
ast.parse(changed, filename=str(path))
if changed != original:
    backup = path.with_suffix('.py.bak')
    shutil.copy2(path, backup)
    path.write_text(changed, encoding='utf-8')
    print(f'PATCHED {path}; backup={backup}')
else:
    print('ALREADY_PATCHED')
