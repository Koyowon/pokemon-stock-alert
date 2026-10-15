"""Integration tests for proposed GitHub Actions state-push helper; local bare remote only."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from state_push_retry_candidate import publish

FILES = {
    "cu": "cu_stock_state.json",
    "emart24": "state.json",
    "gs25": "gs25_independent/gs25_stock_state.json",
}


class CandidatePatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, GIT_ALLOW_PROTOCOL="file", GIT_TERMINAL_PROMPT="0",
                        GIT_CONFIG_NOSYSTEM="1")
        self.remote = self.root / "remote.git"
        self.g(self.root, "init", "--bare", str(self.remote))
        self.seed = self.root / "seed"
        self.g(self.root, "init", "-b", "main", str(self.seed))
        for path in FILES.values():
            p = self.seed / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('{"initial": 1}', encoding="utf-8")
        self.configure(self.seed)
        self.g(self.seed, "add", ".")
        self.g(self.seed, "commit", "-m", "initial")
        self.base = self.g(self.seed, "rev-parse", "HEAD").stdout.strip()
        self.g(self.seed, "remote", "add", "origin", str(self.remote))
        self.g(self.seed, "push", "origin", "main")
        self.g(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")

    def g(self, cwd, *args, check=True):
        return subprocess.run(["git", *args], cwd=cwd, env=self.env,
                              text=True, capture_output=True, check=check)

    def configure(self, cwd):
        self.g(cwd, "config", "user.name", "Offline Test")
        self.g(cwd, "config", "user.email", "offline@example.invalid")

    def clone(self, name):
        path = self.root / name
        self.g(self.root, "clone", str(self.remote), str(path))
        self.configure(path)
        return path

    def artifact(self, name, payload):
        p = self.root / (name + ".json")
        p.write_text(json.dumps(payload), encoding="utf-8")
        return p

    def push_chain(self, name, value):
        writer = self.clone("writer_" + name)
        path = writer / FILES[name]
        path.write_text(json.dumps({name: value}), encoding="utf-8")
        self.g(writer, "add", FILES[name])
        self.g(writer, "commit", "-m", name)
        self.g(writer, "push", "origin", "HEAD:main")

    def snapshot(self):
        clone = self.clone("verify")
        return {name: json.loads((clone / path).read_text(encoding="utf-8"))
                for name, path in FILES.items()}

    def test_01_three_chain_updates_preserved(self):
        clients = {name: self.clone("client_" + name) for name in FILES}
        for name, value in (("cu", 10), ("emart24", 20), ("gs25", 30)):
            publish(clients[name], FILES[name],
                    self.artifact(name, {name: value}), self.base)
        self.assertEqual(self.snapshot(), {
            "cu": {"cu": 10}, "emart24": {"emart24": 20}, "gs25": {"gs25": 30}
        })

    def test_02_non_fast_forward_retry_preserves_other_chains(self):
        client = self.clone("retry_client")
        def competitor(attempt):
            if attempt == 1:
                self.push_chain("cu", 99)
        count = publish(client, FILES["emart24"],
                        self.artifact("emart24", {"emart24": 25}),
                        self.base, before_push=competitor)
        self.assertEqual(count, 2)
        result = self.snapshot()
        self.assertEqual(result["cu"], {"cu": 99})
        self.assertEqual(result["emart24"], {"emart24": 25})
        self.assertEqual(result["gs25"], {"initial": 1})

    def test_03_same_chain_conflict_fails_closed(self):
        client = self.clone("stale_client")
        self.push_chain("emart24", 99)
        with self.assertRaisesRegex(RuntimeError, "stale overwrite"):
            publish(client, FILES["emart24"],
                    self.artifact("emart24", {"emart24": 20}), self.base)
        self.assertEqual(self.snapshot()["emart24"], {"emart24": 99})

    def test_04_retry_exhaustion_preserves_remote(self):
        client = self.clone("rejected_client")
        import state_push_retry_candidate as candidate
        original = candidate.git
        def blocked_push(repo, *args, **kwargs):
            if args and args[0] == "push":
                return subprocess.CompletedProcess(args, 1, "", "simulated push rejection")
            return original(repo, *args, **kwargs)
        with patch.object(candidate, "git", side_effect=blocked_push):
            with self.assertRaisesRegex(RuntimeError, "retry exhausted after 3"):
                publish(client, FILES["gs25"],
                        self.artifact("gs25", {"gs25": 30}), self.base)
        self.assertEqual(self.snapshot()["gs25"], {"initial": 1})


if __name__ == "__main__":
    unittest.main()
