"""Local-only Git CAS integration tests; never contact GitHub or Telegram."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import types
from asan_github_status_persistence import GitBranchCAS, PersistenceError, deliver_persistent, STATE_BRANCH

def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout.strip()

class GitBranchCASTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.remote, self.seed, self.a, self.b = [root / n for n in ("remote.git", "seed", "a", "b")]
        subprocess.run(["git", "init", "--bare", "-q", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", str(self.seed)], check=True)
        git(self.seed, "config", "user.name", "Offline Test")
        git(self.seed, "config", "user.email", "offline@example.invalid")
        (self.seed / "asan_status_delivery_state.json").write_text('{"state":"READY"}\n')
        git(self.seed, "add", "asan_status_delivery_state.json")
        git(self.seed, "commit", "-qm", "seed")
        git(self.seed, "branch", "-M", STATE_BRANCH)
        git(self.seed, "remote", "add", "origin", str(self.remote))
        git(self.seed, "push", "-q", "origin", STATE_BRANCH)
        for folder in (self.a, self.b):
            subprocess.run(["git", "clone", "-q", str(self.remote), str(folder)], check=True)
            git(folder, "config", "user.name", "Offline Test")
            git(folder, "config", "user.email", "offline@example.invalid")
        self.first, self.second = GitBranchCAS(self.a), GitBranchCAS(self.b)
        self.fake = types.ModuleType("asan_status_delivery")
        self.fake.delivery_key = lambda snapshot: snapshot["key"]

    def deliver(self, adapter, sender, enabled=True):
        with patch.dict(sys.modules, {"asan_status_delivery": self.fake}):
            return deliver_persistent({"key": "demo"}, ["page 1", "page 2"],
                                      sender, adapter, enabled=enabled)

    def test_restore(self):
        oid, state = self.first.read()
        self.assertEqual(len(oid), 40)
        self.assertEqual(state["state"], "READY")

    def test_two_clients_conflict(self):
        a, _ = self.first.read()
        b, _ = self.second.read()
        self.first.cas(a, {"state": "IN_FLIGHT"})
        with self.assertRaises(PersistenceError):
            self.second.cas(b, {"state": "IN_FLIGHT"})

    def test_complete_restart_dedup(self):
        sent = []
        self.assertEqual(self.deliver(self.first, lambda p: sent.append(p) or True), "SENT")
        self.assertEqual(self.deliver(self.second, lambda p: self.fail("duplicate")), "UNCHANGED")
        self.assertEqual(len(sent), 2)

    def test_partial_send_blocks_restart(self):
        count = [0]
        def fail_second(page):
            count[0] += 1
            return count[0] == 1
        self.assertEqual(self.deliver(self.first, fail_second), "NEEDS_RECONCILIATION")
        self.assertEqual(self.deliver(self.second, lambda p: self.fail("retry")), "NEEDS_RECONCILIATION")

    def test_missing_branch_no_send(self):
        with patch.object(self.first, "_remote_oid", side_effect=PersistenceError("missing")):
            self.assertEqual(self.deliver(self.first, lambda p: self.fail("send")), "STATE_UNAVAILABLE")

    def test_write_failure_no_send(self):
        with patch.object(self.first, "cas", side_effect=PersistenceError("rejected")):
            self.assertEqual(self.deliver(self.first, lambda p: self.fail("send")), "STATE_UNAVAILABLE")

    def test_default_off(self):
        self.assertEqual(self.deliver(self.first, lambda p: self.fail("send"), enabled=False), "DISABLED")

    def test_main_branch_rejected(self):
        with self.assertRaises(ValueError):
            GitBranchCAS(self.a, branch="main")

if __name__ == "__main__":
    unittest.main()
