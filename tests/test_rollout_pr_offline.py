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

if __name__ == "__main__":
    unittest.main()
