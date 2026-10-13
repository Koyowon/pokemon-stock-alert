"""Offline fault injection tests for manifest-last preview generations."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from asan_stock_snapshot import build_snapshot
from asan_generation_preview import save_generation, read_generation


class GenerationPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = build_snapshot({})

    def test_valid_generation(self):
        folder = save_generation(self.snapshot, self.root, run_id="run-001")
        report = read_generation(folder)
        self.assertEqual(report["candidate_count"], 123)
        self.assertEqual(report["page_count"], len(report["pages"]))
        self.assertTrue((folder / "manifest.json").is_file())

    def test_unique_runs_preserve_prior(self):
        first = save_generation(self.snapshot, self.root, run_id="one")
        before = (first / "manifest.json").read_bytes()
        second = save_generation(self.snapshot, self.root, run_id="two")
        self.assertNotEqual(first, second)
        self.assertEqual((first / "manifest.json").read_bytes(), before)
        self.assertEqual(read_generation(second)["candidate_count"], 123)

    def test_run_collision_no_overwrite(self):
        first = save_generation(self.snapshot, self.root, run_id="same")
        before = (first / "preview.txt").read_bytes()
        with self.assertRaises(FileExistsError):
            save_generation(self.snapshot, self.root, run_id="same")
        self.assertEqual((first / "preview.txt").read_bytes(), before)

    def test_reject_traversal_id(self):
        with self.assertRaises(ValueError):
            save_generation(self.snapshot, self.root, run_id="../state")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_partial_file_write_never_valid(self):
        with patch("asan_generation_preview._write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                save_generation(self.snapshot, self.root, run_id="partial")
        with self.assertRaises(ValueError):
            read_generation(self.root / "partial")

    def test_manifest_commit_interrupted_never_valid(self):
        with patch("asan_generation_preview.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                save_generation(self.snapshot, self.root, run_id="interrupted")
        folder = self.root / "interrupted"
        self.assertFalse((folder / "manifest.json").exists())
        with self.assertRaises(ValueError):
            read_generation(folder)

    def test_missing_manifest_rejected(self):
        folder = save_generation(self.snapshot, self.root, run_id="missing")
        (folder / "manifest.json").unlink()
        with self.assertRaises(ValueError):
            read_generation(folder)

    def test_tamper_txt_rejected(self):
        folder = save_generation(self.snapshot, self.root, run_id="tamper")
        (folder / "preview.txt").write_text("corrupted")
        with self.assertRaises(ValueError):
            read_generation(folder)

    def test_tamper_json_rejected(self):
        folder = save_generation(self.snapshot, self.root, run_id="tamper-json")
        (folder / "preview.json").write_text("{}")
        with self.assertRaises(ValueError):
            read_generation(folder)

    def test_input_inside_root_rejected(self):
        log = self.root / "monitor.log"
        log.write_text("protected")
        with self.assertRaises(ValueError):
            save_generation(self.snapshot, self.root, run_id="bad", input_path=log)
        self.assertEqual(log.read_text(), "protected")

    def test_symlink_root_rejected(self):
        link = self.root.parent / (self.root.name + "-link")
        link.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(link.unlink)
        with self.assertRaises(ValueError):
            save_generation(self.snapshot, link, run_id="bad")

    def test_manifest_symlink_rejected(self):
        folder = save_generation(self.snapshot, self.root, run_id="linked")
        marker = folder / "manifest.json"
        marker.unlink()
        marker.symlink_to(folder / "preview.json")
        with self.assertRaises(ValueError):
            read_generation(folder)


if __name__ == "__main__":
    unittest.main()
