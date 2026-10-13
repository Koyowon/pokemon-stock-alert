"""Offline tests for conservative generation cleanup."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from asan_generation_cleanup import cleanup, inspect
from asan_generation_preview import save_generation
from asan_stock_snapshot import build_snapshot


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = 2000000000

    def old(self, folder):
        for path in folder.iterdir():
            os.utime(path, (self.now - 90000, self.now - 90000))
        os.utime(folder, (self.now - 90000, self.now - 90000))

    def candidate(self, name="unfinished"):
        folder = self.root / name
        folder.mkdir()
        (folder / "preview.txt").write_text("x")
        self.old(folder)
        return folder

    def test_dry_run(self):
        folder = self.candidate()
        report = cleanup(self.root, now=self.now)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["deleted"], [])
        self.assertTrue(folder.exists())

    def test_apply(self):
        folder = self.candidate()
        report = cleanup(self.root, apply=True, now=self.now)
        self.assertEqual(report["deleted"], [str(folder)])
        self.assertFalse(folder.exists())

    def test_complete_preserved(self):
        folder = save_generation(build_snapshot({}), self.root, run_id="complete")
        self.old(folder)
        cleanup(self.root, apply=True, now=self.now)
        self.assertTrue((folder / "manifest.json").exists())

    def test_invalid_manifest_preserved(self):
        folder = self.root / "badmanifest"
        folder.mkdir()
        (folder / "manifest.json").write_text("invalid")
        self.old(folder)
        cleanup(self.root, apply=True, now=self.now)
        self.assertTrue(folder.exists())

    def test_unknown_file_preserved(self):
        folder = self.root / "unknown"
        folder.mkdir()
        (folder / "state.json").write_text("important")
        self.old(folder)
        cleanup(self.root, apply=True, now=self.now)
        self.assertTrue(folder.exists())

    def test_recent_preserved(self):
        folder = self.root / "recent"
        folder.mkdir()
        (folder / "preview.txt").write_text("x")
        cleanup(self.root, apply=True, now=time.time())
        self.assertTrue(folder.exists())

    def test_symlink_preserved(self):
        target = self.root / "important"
        target.write_text("safe")
        folder = self.root / "linked"
        folder.mkdir()
        (folder / "preview.txt").symlink_to(target)
        self.old(folder)
        cleanup(self.root, apply=True, now=self.now)
        self.assertEqual(target.read_text(), "safe")
        self.assertTrue(folder.exists())

    def test_hardlink_preserved(self):
        target = self.root / "important"
        target.write_text("safe")
        folder = self.root / "hardlink"
        folder.mkdir()
        os.link(target, folder / "preview.txt")
        self.old(folder)
        cleanup(self.root, apply=True, now=self.now)
        self.assertTrue(folder.exists())

    def test_empty_folder_preserved(self):
        folder = self.root / "empty"
        folder.mkdir()
        self.old(folder)
        cleanup(self.root, apply=True, now=self.now)
        self.assertTrue(folder.exists())

    def test_bad_id_preserved(self):
        folder = self.root / ".hidden"
        folder.mkdir()
        (folder / "preview.txt").write_text("x")
        self.old(folder)
        cleanup(self.root, apply=True, now=self.now)
        self.assertTrue(folder.exists())

    def test_min_age_enforced(self):
        with self.assertRaises(ValueError):
            inspect(self.root, min_age_seconds=0)

    def test_root_symlink_rejected(self):
        link = self.root.parent / (self.root.name + "-link")
        link.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(link.unlink)
        with self.assertRaises(ValueError):
            cleanup(link, apply=True)


if __name__ == "__main__":
    unittest.main()
