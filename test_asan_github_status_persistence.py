"""Mock-only CAS persistence tests; no GitHub, CU or Telegram requests."""
import unittest
from asan_github_status_persistence import deliver_persistent


class MemoryCAS:
    def __init__(self, state=None):
        self.revision = 1
        self.state = {"state": "READY"} if state is None else state
        self.fail_read = False
        self.fail_write = False

    def read(self):
        if self.fail_read:
            raise OSError("offline read failure")
        return self.revision, dict(self.state)

    def cas(self, expected, state):
        if self.fail_write:
            raise OSError("offline write failure")
        if expected != self.revision:
            raise RuntimeError("CAS conflict")
        self.revision += 1
        self.state = dict(state)
        return self.revision


class PersistentStatusTests(unittest.TestCase):
    def setUp(self):
        from asan_stock_snapshot import build_snapshot
        self.snapshot = build_snapshot({"53982": {"stock": 3}}, query_succeeded=True)
        self.pages = ["page 1", "page 2"]
        self.adapter = MemoryCAS()
        self.sent = []

    def send(self, adapter=None, sender=None, enabled=True):
        return deliver_persistent(self.snapshot, self.pages,
                                  sender or (lambda p: self.sent.append(p) or True),
                                  adapter or self.adapter, enabled=enabled)

    def test_default_disabled(self):
        self.assertEqual(self.send(enabled=False), "DISABLED")
        self.assertEqual(self.sent, [])

    def test_complete_and_dedup(self):
        self.assertEqual(self.send(), "SENT")
        self.assertEqual(self.sent, self.pages)
        self.assertEqual(self.adapter.state["state"], "DONE")
        self.assertEqual(self.send(), "UNCHANGED")
        self.assertEqual(self.sent, self.pages)

    def test_restore_failure_no_send(self):
        self.adapter.fail_read = True
        self.assertEqual(self.send(), "STATE_UNAVAILABLE")
        self.assertFalse(self.sent)

    def test_cas_failure_no_send(self):
        self.adapter.fail_write = True
        self.assertEqual(self.send(), "STATE_UNAVAILABLE")
        self.assertFalse(self.sent)

    def test_partial_failure_blocks_retry(self):
        count = [0]
        def fail_second(page):
            count[0] += 1
            return count[0] == 1
        self.assertEqual(self.send(sender=fail_second), "NEEDS_RECONCILIATION")
        self.assertEqual(self.adapter.state["state"], "IN_FLIGHT")
        self.assertEqual(self.send(), "NEEDS_RECONCILIATION")
        self.assertEqual(self.sent, [])

    def test_inflight_preexisting_blocks_send(self):
        self.adapter.state = {"state": "IN_FLIGHT"}
        self.assertEqual(self.send(), "NEEDS_RECONCILIATION")
        self.assertFalse(self.sent)

    def test_conflict_from_other_run_blocks_send(self):
        class Conflict(MemoryCAS):
            def cas(self, expected, state):
                self.revision += 1
                return super().cas(expected, state)
        self.assertEqual(self.send(adapter=Conflict()), "STATE_UNAVAILABLE")
        self.assertFalse(self.sent)

    def test_commit_done_failure_remains_inflight(self):
        class FailDone(MemoryCAS):
            def cas(self, expected, state):
                if state["state"] == "DONE":
                    raise OSError("offline write failure")
                return super().cas(expected, state)
        adapter = FailDone()
        self.assertEqual(self.send(adapter=adapter), "NEEDS_RECONCILIATION")
        self.assertEqual(adapter.state["state"], "IN_FLIGHT")

    def test_invalid_initial_state_blocks_send(self):
        self.assertEqual(self.send(adapter=MemoryCAS({"state": "BAD"})), "INVALID_STATE")
        self.assertFalse(self.sent)

    def test_absent_revision_blocks_send(self):
        self.adapter.revision = None
        self.assertEqual(self.send(), "STATE_UNAVAILABLE")
        self.assertFalse(self.sent)


if __name__ == "__main__":
    unittest.main()
