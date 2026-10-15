"""Provenance and CLI guard tests. All files and Git remotes are local-only."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from test_state_artifact_recovery import ArtifactRecoveryTests
from state_artifact_recovery_candidate import verify, recover

class ProvenanceTests(ArtifactRecoveryTests):
    def test_13_forged_payload_and_manifest_fail_trusted_digest(self):
        folder = self.package()
        trusted = hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest()
        (folder / "cu_stock_state.json").write_text('{"forged":99}', encoding="utf-8")
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest["files"]["cu_stock_state.json"] = hashlib.sha256(
            (folder / "cu_stock_state.json").read_bytes()).hexdigest()
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        # Self-consistent forgery defeats self-reported file digests.
        verify(folder, "cu", 1234, 1, self.base)
        with self.assertRaisesRegex(ValueError, "trusted manifest digest mismatch"):
            verify(folder, "cu", 1234, 1, self.base, trusted)
        with self.assertRaisesRegex(ValueError, "trusted manifest digest mismatch"):
            recover(self.clone("forged_recovery"), folder, "cu", 1234, 1, self.base, trusted)
        self.assertEqual(self.snapshot()["cu"], {"initial": 1})

    def test_14_valid_trusted_digest_recovers(self):
        folder = self.package()
        trusted = hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest()
        recover(self.clone("trusted_recovery"), folder, "cu", 1234, 1, self.base, trusted)
        self.assertEqual(self.snapshot()["cu"], {"cu": 11})

    def test_15_emart24_cli_requires_pair(self):
        script = Path(__file__).with_name("state_push_retry_candidate.py")
        result = subprocess.run([sys.executable, str(script), "--repo", str(self.root),
                                 "--state-file", "state.json", "--artifact", str(self.root / "missing"),
                                 "--base-sha", self.base], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--stores-artifact", result.stderr)
        result = subprocess.run([sys.executable, str(script), "--repo", str(self.root),
                                 "--state-file", "stores.json", "--artifact", str(self.root / "missing"),
                                 "--base-sha", self.base], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def test_16_wrong_trusted_digest_rejected(self):
        folder = self.package()
        with self.assertRaisesRegex(ValueError, "trusted manifest digest mismatch"):
            verify(folder, "cu", 1234, 1, self.base, "0" * 64)
