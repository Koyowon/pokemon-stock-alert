"""True offline integration of the PR publisher against disposable local bare Git only."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from state_push_publisher import publish_bundle

FILES = ["state.json", "stores.json", "cu_stock_state.json",
         "gs25_independent/gs25_stock_state.json"]
CHAINS = {"cu": ["cu_stock_state.json"],
          "gs25": ["gs25_independent/gs25_stock_state.json"],
          "emart24": ["state.json", "stores.json"]}


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-C", str(cwd), *args], check=check,
                          capture_output=True, text=True)


class BareGitPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(self.remote)],
                       check=True, capture_output=True)
        self.seed = self.root / "seed"
        git(self.root, "init", "-b", "main", str(self.seed))
        git(self.seed, "config", "user.name", "Offline Test")
        git(self.seed, "config", "user.email", "offline@example.invalid")
        for p in FILES:
            f = self.seed / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text('{"initial":1}', encoding="utf-8")
        git(self.seed, "add", "--", *FILES)
        git(self.seed, "commit", "-m", "seed")
        git(self.seed, "remote", "add", "origin", self.remote.as_uri())
        git(self.seed, "push", "origin", "HEAD:refs/heads/main")
        self.base = git(self.seed, "rev-parse", "HEAD").stdout.strip()
        self.env = patch.dict(os.environ, {
            "STATE_PUBLISH_APPROVED": "1",
            "STATE_PUBLISH_OFFLINE_TEST": "1",
            "GIT_ALLOW_PROTOCOL": "file",
            "GIT_TERMINAL_PROMPT": "0",
            "GITHUB_REPOSITORY": "Koyowon/pokemon-stock-alert",
            "GITHUB_REF": "refs/heads/main",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.count = 0

    def clone(self):
        self.count += 1
        p = self.root / ("clone" + str(self.count))
        git(self.root, "clone", self.remote.as_uri(), str(p))
        git(p, "config", "user.name", "Offline Test")
        git(p, "config", "user.email", "offline@example.invalid")
        return p

    def artifacts(self, chain, qty=7):
        folder = self.root / ("artifact" + str(self.count) + str(qty))
        folder.mkdir(exist_ok=True)
        out = {}
        for name in CHAINS[chain]:
            p = folder / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"qty": qty}), encoding="utf-8")
            out[name] = p
        return out

    def advance(self, name, qty):
        p = self.clone()
        f = p / name
        f.write_text(json.dumps({"qty": qty}), encoding="utf-8")
        git(p, "add", "--", name)
        git(p, "commit", "-m", "other writer")
        git(p, "push", "origin", "HEAD:refs/heads/main")

    def remote_json(self, name):
        p = self.clone()
        return json.loads((p / name).read_text(encoding="utf-8"))

    def test_all_chains_publish_only_allowlisted_files(self):
        for chain in ("cu", "gs25", "emart24"):
            p = self.clone()
            count = publish_bundle(p, self.artifacts(chain), self.base)
            self.assertEqual(count, 1)
            for name in CHAINS[chain]:
                self.assertEqual(self.remote_json(name), {"qty": 7})

    def test_same_chain_stale_update_rejected(self):
        p = self.clone()
        self.advance("cu_stock_state.json", 88)
        with self.assertRaisesRegex(RuntimeError, "stale overwrite"):
            publish_bundle(p, self.artifacts("cu"), self.base)
        self.assertEqual(self.remote_json("cu_stock_state.json"), {"qty": 88})

    def test_unrelated_chain_update_preserved(self):
        p = self.clone()
        self.advance("cu_stock_state.json", 88)
        publish_bundle(p, self.artifacts("gs25"), self.base)
        self.assertEqual(self.remote_json("cu_stock_state.json"), {"qty": 88})
        self.assertEqual(self.remote_json("gs25_independent/gs25_stock_state.json"), {"qty": 7})

    def test_noop_keeps_commit(self):
        p = self.clone()
        before = git(p, "rev-parse", "HEAD").stdout.strip()
        files = {}
        for name in CHAINS["cu"]:
            f = self.root / "noop.json"
            f.write_text('{"initial":1}', encoding="utf-8")
            files[name] = f
        publish_bundle(p, files, self.base)
        self.assertEqual(git(self.clone(), "rev-parse", "HEAD").stdout.strip(), before)

    def test_non_fast_forward_retry_then_success(self):
        p = self.clone()
        def collision(attempt):
            if attempt == 1:
                self.advance("cu_stock_state.json", 55)
        attempts = publish_bundle(p, self.artifacts("gs25"), self.base, before_push=collision)
        self.assertEqual(attempts, 2)
        self.assertEqual(self.remote_json("cu_stock_state.json"), {"qty": 55})

    def test_same_chain_collision_fails_closed(self):
        p = self.clone()
        def collision(attempt):
            if attempt == 1:
                self.advance("gs25_independent/gs25_stock_state.json", 99)
        with self.assertRaisesRegex(RuntimeError, "stale overwrite"):
            publish_bundle(p, self.artifacts("gs25"), self.base, before_push=collision)
        self.assertEqual(self.remote_json("gs25_independent/gs25_stock_state.json"), {"qty": 99})

    def test_rollback_preserves_newest_state(self):
        p = self.clone()
        publish_bundle(p, self.artifacts("emart24"), self.base)
        self.advance("state.json", 99)
        stale = self.clone()
        with self.assertRaisesRegex(RuntimeError, "stale overwrite"):
            publish_bundle(stale, self.artifacts("emart24", 4), self.base)
        self.assertEqual(self.remote_json("state.json"), {"qty": 99})
        self.assertEqual(self.remote_json("stores.json"), {"qty": 7})


if __name__ == "__main__":
    unittest.main()
