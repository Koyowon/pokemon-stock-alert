"""Deterministic offline reproduction of refresh-token rotation lost update.

No external HTTP, GS25 credentials, production code, or Actions involved.
Run: python -m unittest -v test_gs25_multiprocess_race.py
"""
import json
import multiprocessing as mp
import os
import tempfile
import unittest
from pathlib import Path


def competing_refresh(file, barrier, queue, label):
    try:
        path = Path(file)
        old = json.loads(path.read_text())['refreshToken']
        barrier.wait(timeout=5)  # both workers read the SAME token
        next_token = f'rotated-{label}'
        tmp = path.with_name(path.name + f'.{label}.tmp')
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump({'refreshToken': next_token}, stream)
        os.replace(tmp, path)  # atomic replacement but no cross-process CAS
        queue.put((label, old, next_token, 'ok'))
    except Exception as exc:
        queue.put((label, '', '', type(exc).__name__))


class MultiprocessRotationRaceTests(unittest.TestCase):
    def test_two_processes_can_overwrite_each_others_rotated_token(self):
        ctx = mp.get_context('spawn')
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / 'session.json'
            file.write_text(json.dumps({'refreshToken': 'initial-token'}))
            os.chmod(file, 0o600)
            barrier = ctx.Barrier(2)
            queue = ctx.Queue()
            workers = [ctx.Process(target=competing_refresh, args=(str(file), barrier, queue, name)) for name in ('A', 'B')]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=10)
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                    worker.join()
            self.assertTrue(all(worker.exitcode == 0 for worker in workers))
            outcomes = [queue.get(timeout=2) for _ in workers]
            self.assertTrue(all(item[3] == 'ok' for item in outcomes), outcomes)
            self.assertEqual({item[1] for item in outcomes}, {'initial-token'})
            rotated = {item[2] for item in outcomes}
            self.assertEqual(rotated, {'rotated-A', 'rotated-B'})
            self.assertIn(json.loads(file.read_text())['refreshToken'], rotated)
            # One acknowledged rotation has been overwritten: real cross-process lost update.
            self.assertEqual(len(rotated), 2)


if __name__ == '__main__':
    unittest.main()
