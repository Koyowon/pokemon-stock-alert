"""Offline-only safety tests for the proposed separate state-branch architecture."""
import copy
import unittest
from experiments.isolated_state_outbox import (
    queue_transition, claim_event, dispatch_once, state_branch_policy,
)


class FakeStore:
    def __init__(self, state):
        self.version = 0
        self.state = copy.deepcopy(state)
        self.reject = False

    def load(self):
        return self.version, copy.deepcopy(self.state)

    def commit(self, candidate, expected):
        if self.reject or expected != self.version:
            return False
        self.state = copy.deepcopy(candidate)
        self.version += 1
        return True


class OutboxIsolationTests(unittest.TestCase):
    def test_cu_claim_before_send_and_no_duplicate(self):
        state, eid = queue_transition({}, "cu", "CU synthetic change")
        store = FakeStore(state)
        sends = []
        self.assertTrue(dispatch_once(store.load, store.commit, sends.append, eid))
        self.assertEqual(sends, ["CU synthetic change"])
        with self.assertRaises(ValueError):
            dispatch_once(store.load, store.commit, sends.append, eid)
        self.assertEqual(len(sends), 1)

    def test_emart24_claim_before_send(self):
        state, eid = queue_transition({}, "emart24", "emart24 synthetic change")
        store = FakeStore(state)
        sent = []
        self.assertTrue(dispatch_once(store.load, store.commit, sent.append, eid))
        self.assertEqual(sent, ["emart24 synthetic change"])
        self.assertEqual(store.state["pending_alerts"][eid]["status"], "claimed")

    def test_failed_git_claim_blocks_send(self):
        state, eid = queue_transition({}, "cu", "synthetic")
        store = FakeStore(state)
        store.reject = True
        sent = []
        self.assertFalse(dispatch_once(store.load, store.commit, sent.append, eid))
        self.assertEqual(sent, [])
        self.assertEqual(store.state["pending_alerts"][eid]["status"], "pending")

    def test_race_only_one_claim_wins(self):
        state, eid = queue_transition({}, "emart24", "synthetic")
        store = FakeStore(state)
        v1, s1 = store.load()
        v2, s2 = store.load()
        self.assertTrue(store.commit(claim_event(s1, eid), v1))
        self.assertFalse(store.commit(claim_event(s2, eid), v2))
        self.assertEqual(store.state["pending_alerts"][eid]["status"], "claimed")

    def test_crash_after_claim_means_no_auto_retry(self):
        state, eid = queue_transition({}, "cu", "synthetic")
        store = FakeStore(state)
        version, snapshot = store.load()
        self.assertTrue(store.commit(claim_event(snapshot, eid), version))
        with self.assertRaises(ValueError):
            dispatch_once(store.load, store.commit, lambda _: None, eid)

    def test_sequence_distinguishes_repeated_transition(self):
        a, e1 = queue_transition({}, "cu", "same transition")
        b, e2 = queue_transition(a, "cu", "same transition")
        self.assertNotEqual(e1, e2)
        self.assertEqual(len(b["pending_alerts"]), 2)

    def test_state_branch_path_isolation(self):
        self.assertTrue(state_branch_policy("stock-state-isolated", ["state.json", "stores.json"]))
        for branch, paths in [
            ("main", ["state.json"]),
            ("stock-state-isolated", ["monitor.py"]),
            ("stock-state-isolated", ["state.json", ".github/workflows/x.yml"]),
            ("stock-state-isolated", []),
        ]:
            with self.assertRaises(ValueError):
                state_branch_policy(branch, paths)

    def test_capacity_fails_closed(self):
        state = {"pending_alerts": {str(i): {"status": "pending", "message": "x"} for i in range(1000)}}
        with self.assertRaises(ValueError):
            queue_transition(state, "cu", "another")


if __name__ == "__main__":
    unittest.main()
