"""Offline tests: artifact upload/download simulation, recovery and rollback safety."""
import json
import shutil
from pathlib import Path
from unittest.mock import patch

from test_state_push_retry_candidate import CandidatePatchTests
from state_artifact_recovery_candidate import prepare, verify, recover
from state_push_retry_candidate import publish_bundle


class ArtifactRecoveryTests(CandidatePatchTests):
    def source(self, chain="cu"):
        folder = self.root / ("source_" + chain)
        folder.mkdir()
        names = {
            "cu": ("cu_stock_state.json",),
            "gs25": ("gs25_independent/gs25_stock_state.json",),
            "emart24": ("state.json", "stores.json"),
        }[chain]
        for name in names:
            p = folder / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({chain: 11}), encoding="utf-8")
        return folder

    def package(self, chain="cu"):
        folder = self.root / ("download_" + chain)
        prepare(self.source(chain), folder, chain, 1234, 1, self.base)
        return folder

    def test_05_upload_missing_file_fails_and_cleans_partial(self):
        source = self.source("emart24")
        (source / "stores.json").unlink()
        destination = self.root / "failed_upload"
        with self.assertRaises(ValueError):
            prepare(source, destination, "emart24", 1234, 1, self.base)
        self.assertFalse(destination.exists())

    def test_06_download_missing_manifest_fails_closed(self):
        folder = self.package()
        (folder / "manifest.json").unlink()
        with self.assertRaises(ValueError):
            verify(folder, "cu", 1234, 1, self.base)
        with self.assertRaises(ValueError):
            recover(self.clone("missing_manifest"), folder, "cu", 1234, 1, self.base)
        self.assertEqual(self.snapshot()["cu"], {"initial": 1})

    def test_07_checksum_tampering_rejected(self):
        folder = self.package()
        (folder / "cu_stock_state.json").write_text('{"tampered":1}')
        with self.assertRaisesRegex(ValueError, "checksum"):
            verify(folder, "cu", 1234, 1, self.base)

    def test_08_metadata_run_attempt_chain_sha_rejected(self):
        folder = self.package()
        for chain, run, attempt, sha in (
            ("gs25", 1234, 1, self.base), ("cu", 9, 1, self.base),
            ("cu", 1234, 2, self.base), ("cu", 1234, 1, "f" * 40)
        ):
            with self.assertRaises(ValueError):
                verify(folder, chain, run, attempt, sha)

    def test_09_failed_publish_recovery_only_replays_state(self):
        folder = self.package()
        client = self.clone("recover_client")
        import state_push_retry_candidate as candidate
        original = candidate.git
        def reject(repo, *args, **kwargs):
            if args and args[0] == "push":
                import subprocess
                return subprocess.CompletedProcess(args, 1, "", "rejected")
            return original(repo, *args, **kwargs)
        with patch.object(candidate, "git", side_effect=reject):
            with self.assertRaisesRegex(RuntimeError, "retry exhausted"):
                recover(client, folder, "cu", 1234, 1, self.base)
        self.assertEqual(self.snapshot()["cu"], {"initial": 1})
        # Fresh disposable checkout and identical run artifact; no API or Telegram.
        self.assertLessEqual(recover(self.clone("recovered"), folder, "cu", 1234, 1, self.base), 3)
        verifier = self.clone("recovery_verifier")
        self.assertEqual(json.loads((verifier / "cu_stock_state.json").read_text()), {"cu": 11})

    def test_10_rollback_never_overwrites_newer_valid_state(self):
        folder = self.package()
        self.push_chain("cu", 99)
        with self.assertRaisesRegex(RuntimeError, "stale overwrite"):
            recover(self.clone("rollback_guard"), folder, "cu", 1234, 1, self.base)
        self.assertEqual(self.snapshot()["cu"], {"cu": 99})

    def test_11_emart24_bundle_recovery(self):
        folder = self.package("emart24")
        recover(self.clone("em_recovery"), folder, "emart24", 1234, 1, self.base)
        v = self.clone("em_verifier")
        self.assertEqual(json.loads((v / "state.json").read_text()), {"emart24": 11})
        self.assertEqual(json.loads((v / "stores.json").read_text()), {"emart24": 11})

    def test_12_corrupt_manifest_rejected(self):
        folder = self.package()
        (folder / "manifest.json").write_text("{")
        with self.assertRaisesRegex(ValueError, "manifest"):
            verify(folder, "cu", 1234, 1, self.base)
