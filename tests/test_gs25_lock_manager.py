"""POSIX-only offline GS25 session manager contract tests.

No network, real credentials, GitHub Actions, or production imports.
Run: python -m unittest -v test_gs25_lock_manager.py
This is a test model, not production authentication code.
"""
import fcntl
import json
import multiprocessing as mp
import os
import signal
import stat
import tempfile
import time
import unittest
from pathlib import Path


class SessionError(Exception):
    pass


class LockTimeout(SessionError):
    pass


class SaveFailed(SessionError):
    pass


def private_write(path, data, replace=os.replace):
    path = Path(path)
    tmp = path.with_name(f'{path.name}.{os.getpid()}.tmp')
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        replace(tmp, path)
        # Parent-directory fsync is needed for durability on supported filesystems.
        dirfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except OSError as exc:
        raise SaveFailed('session persist failed') from exc
    finally:
        tmp.unlink(missing_ok=True)


def locked_rotate(path, lock_path, timeout=2.0, replace=os.replace, on_lock=None):
    """Exclusive flock on a STABLE lock file; reload token only after lock."""
    lockfd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LockTimeout('lock acquisition timeout')
                time.sleep(0.01)
        if on_lock:
            on_lock()
        current = json.loads(Path(path).read_text())
        old = current['refreshToken']
        if not isinstance(old, str):
            raise SessionError('invalid session')
        current['refreshToken'] = old + '-rotated'
        private_write(path, current, replace=replace)
        return old, current['refreshToken']
    finally:
        os.close(lockfd)  # releases flock even on failure or process death


def rotate_worker(path, lock_path, queue, start=None, timeout=2.0):
    try:
        if start is not None:
            start.wait(timeout=5)
        old, new = locked_rotate(path, lock_path, timeout=timeout)
        queue.put(('ok', old, new))
    except Exception as exc:
        queue.put((type(exc).__name__, '', ''))


def holder_worker(lock_path, ready):
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    ready.set()
    while True:
        time.sleep(1)


class POSIXLockManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'session.json'
        self.lock_path = Path(self.temp.name) / 'session.lock'
        private_write(self.path, {'refreshToken': 'seed'})
        self.ctx = mp.get_context('spawn')

    def run_workers(self, count):
        start = self.ctx.Event()
        queue = self.ctx.Queue()
        processes = [self.ctx.Process(target=rotate_worker, args=(str(self.path), str(self.lock_path), queue, start)) for _ in range(count)]
        try:
            for proc in processes:
                proc.start()
            start.set()
            for proc in processes:
                proc.join(timeout=8)
            self.assertTrue(all(proc.exitcode == 0 for proc in processes), [p.exitcode for p in processes])
            return [queue.get(timeout=2) for _ in processes]
        finally:
            for proc in processes:
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=3)

    def test_two_processes_rotate_sequentially_without_lost_update(self):
        outcomes = self.run_workers(2)
        self.assertTrue(all(row[0] == 'ok' for row in outcomes), outcomes)
        self.assertEqual({row[1] for row in outcomes}, {'seed', 'seed-rotated'})
        self.assertEqual(json.loads(self.path.read_text())['refreshToken'], 'seed-rotated-rotated')

    def test_single_manager_serializes_eight_processes(self):
        outcomes = self.run_workers(8)
        self.assertEqual(len(outcomes), 8)
        self.assertTrue(all(row[0] == 'ok' for row in outcomes), outcomes)
        self.assertEqual(json.loads(self.path.read_text())['refreshToken'], 'seed' + '-rotated' * 8)

    def test_lock_timeout_does_not_change_token(self):
        ready = self.ctx.Event()
        holder = self.ctx.Process(target=holder_worker, args=(str(self.lock_path), ready))
        try:
            holder.start()
            self.assertTrue(ready.wait(timeout=5))
            with self.assertRaises(LockTimeout):
                locked_rotate(self.path, self.lock_path, timeout=0.03)
            self.assertEqual(json.loads(self.path.read_text())['refreshToken'], 'seed')
        finally:
            if holder.is_alive():
                holder.terminate()
            holder.join(timeout=3)

    def test_forced_termination_releases_lock(self):
        ready = self.ctx.Event()
        holder = self.ctx.Process(target=holder_worker, args=(str(self.lock_path), ready))
        try:
            holder.start()
            self.assertTrue(ready.wait(timeout=5))
            holder.terminate()
            holder.join(timeout=3)
            self.assertFalse(holder.is_alive())
            old, new = locked_rotate(self.path, self.lock_path, timeout=1)
            self.assertEqual((old, new), ('seed', 'seed-rotated'))
        finally:
            if holder.is_alive():
                holder.kill()
                holder.join(timeout=3)

    def test_failed_replace_preserves_session_and_releases_lock(self):
        before = self.path.read_bytes()
        def fail(_src, _dst):
            raise OSError('simulated storage failure')
        with self.assertRaises(SaveFailed):
            locked_rotate(self.path, self.lock_path, replace=fail)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        self.assertEqual(locked_rotate(self.path, self.lock_path), ('seed', 'seed-rotated'))

    def test_private_file_permissions_at_creation(self):
        observed = []
        def inspect(src, dst):
            observed.append(stat.S_IMODE(os.stat(src).st_mode))
            return os.replace(src, dst)
        locked_rotate(self.path, self.lock_path, replace=inspect)
        self.assertEqual(observed, [0o600])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.lock_path.stat().st_mode), 0o600)


if __name__ == '__main__':
    unittest.main()
