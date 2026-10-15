"""Review-only tests. No production API, Telegram or Git pushes."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from state_artifact_contract import prepare, verify
from state_push_publisher import publish_bundle

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = {
    "cu": ".github/workflows/cu-stock-monitor.yml",
    "gs25": ".github/workflows/gs25-stock-monitor.yml",
    "emart24": ".github/workflows/stock-monitor.yml",
}

class RolloutReviewTests(unittest.TestCase):
    def test_workflow_least_privilege_and_artifact_handoff(self):
        for chain, path in WORKFLOWS.items():
            text = (ROOT / path).read_text()
            self.assertIn("contents: read", text)
            self.assertIn("contents: write", text)
            self.assertIn("persist-credentials: false", text)
            self.assertIn("needs: scan", text)
            self.assertIn("actions/upload-artifact@v4", text)
            self.assertIn("actions/download-artifact@v4", text)
            self.assertIn("TRUSTED_MANIFEST_SHA256", text)
            self.assertIn("TRUSTED_ARTIFACT_ID", text)
            self.assertIn("artifact-ids: ${{ needs.scan.outputs.artifact_id }}", text)
            self.assertIn("if: success()", text)
            self.assertIn("if: always() && needs.scan.outputs.artifact_ok == 'success'", text)
            self.assertIn("group: state-publisher-main", text)
            self.assertIn("state-publisher-main", text)
            self.assertIn("--chain '" + chain + "'", text)

    def test_emart24_paired_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "source"
            src.mkdir()
            (src / "state.json").write_text('{"stock":1}')
            (src / "stores.json").write_text('{"stores":{}}')
            sha = "a" * 40
            dest = root / "artifact"
            prepare(src, dest, "emart24", 100, 1, sha)
            trusted = hashlib.sha256((dest / "manifest.json").read_bytes()).hexdigest()
            files, hashes = verify(dest, "emart24", 100, 1, sha, trusted)
            self.assertEqual(set(files), {"state.json", "stores.json"})
            self.assertEqual(len(hashes), 2)
            (dest / "state.json").write_text('{"stock":2}')
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify(dest, "emart24", 100, 1, sha, trusted)

    def test_manifest_and_payload_forgery_fails_trusted_digest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "source"
            src.mkdir()
            (src / "cu_stock_state.json").write_text('{"stock":1}')
            dest = root / "artifact"
            prepare(src, dest, "cu", 100, 1, "a" * 40)
            trusted = hashlib.sha256((dest / "manifest.json").read_bytes()).hexdigest()
            (dest / "cu_stock_state.json").write_text('{"stock":999}')
            manifest = json.loads((dest / "manifest.json").read_text())
            manifest["files"]["cu_stock_state.json"] = hashlib.sha256(
                (dest / "cu_stock_state.json").read_bytes()).hexdigest()
            (dest / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "trusted manifest digest mismatch"):
                verify(dest, "cu", 100, 1, "a" * 40, trusted)

    def test_publisher_denies_unapproved_invocation(self):
        with patch.dict(os.environ, {"STATE_PUBLISH_APPROVED": "0"}):
            with self.assertRaisesRegex(RuntimeError, "not authorized"):
                publish_bundle("/tmp/nonexistent", {"cu_stock_state.json": "/tmp/no"},
                               "a" * 40)

    def test_missing_or_wrong_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaisesRegex(ValueError, "missing download artifact"):
                verify(root / "missing", "cu", 100, 1, "a" * 40, "0" * 64)
            src = root / "source"
            src.mkdir()
            (src / "cu_stock_state.json").write_text('{"stock":1}')
            dest = root / "artifact"
            prepare(src, dest, "cu", 100, 1, "a" * 40)
            digest = hashlib.sha256((dest / "manifest.json").read_bytes()).hexdigest()
            for chain, run, attempt in [("gs25", 100, 1), ("cu", 101, 1), ("cu", 100, 2)]:
                with self.assertRaisesRegex(ValueError, "metadata mismatch"):
                    verify(dest, chain, run, attempt, "a" * 40, digest)

    def test_monitor_all_unknown_fails_before_state_save(self):
        text = (ROOT / "monitor.py").read_text()
        error = 'raise RuntimeError("EMART24_ALL_INVENTORY_UNKNOWN: state unchanged")'
        self.assertIn(error, text)
        self.assertLess(text.index(error), text.index("save_json(STATE_FILE, updated)"))

    def test_publisher_blocks_wrong_ref_and_repo(self):
        with patch.dict(os.environ, {"STATE_PUBLISH_APPROVED": "1", "GITHUB_REPOSITORY": "attacker/repo", "GITHUB_REF": "refs/heads/main"}):
            with self.assertRaisesRegex(RuntimeError, "not authorized"):
                publish_bundle("/tmp/nonexistent", {"cu_stock_state.json": "/tmp/no"}, "a" * 40)
        with patch.dict(os.environ, {"STATE_PUBLISH_APPROVED": "1", "GITHUB_REPOSITORY": "Koyowon/pokemon-stock-alert", "GITHUB_REF": "refs/heads/evil"}):
            with self.assertRaisesRegex(RuntimeError, "only supports main"):
                publish_bundle("/tmp/nonexistent", {"cu_stock_state.json": "/tmp/no"}, "a" * 40)

    def test_rollback_and_stale_write_controls_exist(self):
        text = (ROOT / "state_push_publisher.py").read_text()
        self.assertIn("same-chain state changed remotely; refusing stale overwrite", text)
        self.assertIn("push retry exhausted", text)
        self.assertIn('"push", "origin", "HEAD:refs/heads/main"', text)
        self.assertNotIn("push --force", text)
        self.assertIn("'merge-base', '--is-ancestor'", text)

if __name__ == "__main__":
    unittest.main()
