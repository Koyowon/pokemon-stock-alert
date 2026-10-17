"""Inventory request health overlay. No network or notification capability."""
import argparse
import json
import os
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGIONS = {'남원': 'namwon', '아산': 'asan', '전주': 'jeonju', '제주': 'jeju'}


def region_of(address):
    return next((rid for name, rid in REGIONS.items() if name + '시' in address), None)


class Health:
    def __init__(self, chain, root=ROOT, clock=time.time):
        self.chain, self.root, self.clock = chain, Path(root), clock
        self.path = self.root / (chain + '_inventory_health.json')
        self.errors = []
        try:
            self.previous = json.loads(self.path.read_text()) if self.path.exists() else {}
            if not isinstance(self.previous, dict) or not isinstance(self.previous.get('stores', {}), dict):
                raise ValueError('Invalid health state')
        except (OSError, ValueError):
            self.previous = {}; self.errors.append('PREVIOUS_HEALTH_INVALID')
        self.targets = {}; self.observed = {}; self.reasons = {}

    def expect(self, code, name, address='', region=None):
        self.targets[str(code)] = {'name': name, 'address': address, 'region': region or region_of(address)}

    def observe(self, code, quantity, name, address='', region=None):
        code = str(code)
        self.expect(code, name, address, region)
        if type(quantity) is int and quantity >= 0:
            self.observed[code] = quantity
        else:
            self.unknown(code, 'INVALID_QUANTITY')

    def unknown(self, code, reason):
        self.observed.pop(str(code), None)
        self.reasons[str(code)] = reason

    def finish(self, error=None):
        now = int(self.clock()); records = {}
        if error:
            self.errors.append(type(error).__name__)
        for code in set(self.previous.get('stores', {})) | set(self.targets):
            old = self.previous.get('stores', {}).get(code, {})
            record = dict(old)
            record.update(self.targets.get(code, {}))
            active = code in self.targets or (error is not None and old.get('status') != 'DISABLED')
            qty = self.observed.get(code) if active else None
            record.update(status=('OK' if qty is not None else 'UNKNOWN') if active else 'DISABLED',
                          quantity=qty, checked_at=now,
                          reason='OBSERVED' if qty is not None else self.reasons.get(code,
                          'RUN_FAILED' if error and active else 'MISSING_IN_RESPONSE' if active else 'NOT_ACTIVE'))
            if qty is not None:
                record.update(last_known_quantity=qty, last_success_at=now, unknown_runs=0)
            elif active:
                record['unknown_runs'] = old.get('unknown_runs', 0) + 1
                record.setdefault('first_unknown_at', now)
            if qty is not None:
                record.pop('first_unknown_at', None)
            records[code] = record
        counts = {s: sum(r['status'] == s for r in records.values()) for s in ('OK', 'UNKNOWN', 'DISABLED')}
        data = {'version': 1, 'chain': self.chain, 'product': '8800286275732',
                'updated_at': now, 'stores': records, 'summary': counts, 'errors': self.errors}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name + '.', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2);handle.write('\n')
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        print('INVENTORY_HEALTH', self.chain, json.dumps(counts))
        return data


def monitor_with_health(chain, run):
    health = Health(chain)
    error = None
    try:
        return run(health)
    except BaseException as exc:
        error = exc
        raise
    finally:
        # Health persistence must never replace a monitor exception or stock baseline.
        try:
            health.finish(error)
        except Exception as exc:
            print('HEALTH_SAVE_FAILED', type(exc).__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('chain', choices=('cu', 'emart24', 'gs25'))
    args = parser.parse_args()
    data = json.loads((ROOT / (args.chain + '_inventory_health.json')).read_text())
    lines = ['## ' + args.chain + ' inventory health', '',
             'UNKNOWN is not zero. This overlay does not change alert baselines.',
             'Snapshot Unix timestamp: ' + str(data['updated_at']), '',
             '| Confirmed quantity | Unknown | Disabled |', '|---:|---:|---:|',
             '| {OK} | {UNKNOWN} | {DISABLED} |'.format(**data['summary']), '',
             'Unknown codes: ' + ', '.join(c for c,r in sorted(data['stores'].items()) if r['status']=='UNKNOWN')]
    summary = '\n'.join(lines) + '\n'
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as handle:handle.write(summary)
    print(summary)


if __name__ == '__main__':main()
