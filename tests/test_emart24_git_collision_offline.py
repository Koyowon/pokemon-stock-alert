"""Local-only Git collision regression tests. No network, Telegram, or production git pushes."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

FILES = {
    "cu": "cu_stock_state.json",
    "emart24": "state.json",
    "gs25": "gs25_independent/gs25_stock_state.json",
}

class LocalGitCollisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.remote = self.root / "remote.git"
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1",
                        GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file")
        self.git(self.root, "init", "--bare", str(self.remote))
        self.seed = self.root / "seed"
        self.git(self.root, "init", "-b", "main", str(self.seed))
        self.git(self.seed, "config", "user.name", "Offline Test")
        self.git(self.seed, "config", "user.email", "offline@example.invalid")
        for path in FILES.values():
            p = self.seed / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"baseline": 1}), encoding="utf-8")
        self.git(self.seed, "add", ".")
        self.git(self.seed, "commit", "-m", "seed")
        self.git(self.seed, "remote", "add", "origin", str(self.remote))
        self.git(self.seed, "push", "origin", "main")
        self.git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")

    def git(self, cwd, *args, check=True):
        return subprocess.run(["git", *args], cwd=cwd, env=self.env,
                              text=True, capture_output=True, check=check)

    def clone(self, name):
        target = self.root / name
        self.git(self.root, "clone", str(self.remote), str(target))
        self.git(target, "config", "user.name", "Offline Test")
        self.git(target, "config", "user.email", "offline@example.invalid")
        return target

    def write(self, repo, chain, value):
        path = repo / FILES[chain]
        path.write_text(json.dumps({chain: value}), encoding="utf-8")
        self.git(repo, "add", FILES[chain])
        self.git(repo, "commit", "-m", f"{chain} update")

    def retry_push(self, repo, chain, value, attempts=3):
        """Candidate bounded retry algorithm: reapply only this chain's file."""
        for attempt in range(attempts):
            self.git(repo, "fetch", "origin", "main")
            self.git(repo, "reset", "--hard", "origin/main")
            self.write(repo, chain, value)
            result = self.git(repo, "push", "origin", "HEAD:main", check=False)
            if result.returncode == 0:
                return attempt + 1
        raise RuntimeError("bounded push retry exhausted")

    def snapshot(self):
        verifier = self.clone("verify")
        return {chain: json.loads((verifier / path).read_text(encoding="utf-8"))
                for chain, path in FILES.items()}

    def test_01_three_stale_writers_trigger_non_fast_forward(self):
        writers = {chain: self.clone(chain) for chain in FILES}
        for i, (chain, repo) in enumerate(writers.items(), 1):
            self.write(repo, chain, i)
        self.git(writers["cu"], "push", "origin", "HEAD:main")
        for chain in ("emart24", "gs25"):
            result = self.git(writers[chain], "push", "origin", "HEAD:main", check=False)
            self.assertNotEqual(result.returncode, 0, chain)

    def test_02_bounded_retry_preserves_all_three_chains(self):
        writers = {chain: self.clone(chain) for chain in FILES}
        for i, (chain, repo) in enumerate(writers.items(), 1):
            self.write(repo, chain, i)
        self.git(writers["cu"], "push", "origin", "HEAD:main")
        for chain, value in (("emart24", 2), ("gs25", 3)):
            self.assertNotEqual(
                self.git(writers[chain], "push", "origin", "HEAD:main", check=False).returncode, 0)
            self.assertLessEqual(self.retry_push(writers[chain], chain, value), 3)
        result = self.snapshot()
        self.assertEqual(result["cu"], {"cu": 1})
        self.assertEqual(result["emart24"], {"emart24": 2})
        self.assertEqual(result["gs25"], {"gs25": 3})

    def test_03_retry_updates_only_own_state_file(self):
        writer = self.clone("only_emart24")
        self.assertEqual(self.retry_push(writer, "emart24", 99), 1)
        result = self.snapshot()
        self.assertEqual(result["emart24"], {"emart24": 99})
        self.assertEqual(result["cu"], {"baseline": 1})
        self.assertEqual(result["gs25"], {"baseline": 1})

    def test_04_bounded_retry_failure_is_visible(self):
        writer = self.clone("failed_writer")
        original_git = self.git
        def reject_push(cwd, *args, **kwargs):
            if args and args[0] == "push":
                return subprocess.CompletedProcess(["git", *args], 1, "", "simulated rejection")
            return original_git(cwd, *args, **kwargs)
        self.git = reject_push
        with self.assertRaisesRegex(RuntimeError, "retry exhausted"):
            self.retry_push(writer, "emart24", 42, attempts=3)
        self.git = original_git
        self.assertEqual(self.snapshot()["emart24"], {"baseline": 1})

if __name__ == "__main__":
    unittest.main()
