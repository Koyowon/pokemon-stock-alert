"""Offline fault-injection tests for paired preview writes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from asan_stock_snapshot import build_snapshot
from asan_preview_export import write_preview

class AtomicPreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.txt = self.root / "preview.txt"
        self.js = self.root / "preview.json"
        self.snapshot = build_snapshot({})

    def assert_no_temp(self):
        self.assertFalse(list(self.root.glob(".asan-*")))

    def test_same_path_rejected(self):
        with self.assertRaises(ValueError):
            write_preview(self.snapshot, self.txt, self.txt)
        self.assertFalse(self.txt.exists())
        self.assert_no_temp()

    def test_symlink_alias_rejected(self):
        self.txt.write_text("old")
        self.js.symlink_to(self.txt)
        with self.assertRaises(ValueError):
            write_preview(self.snapshot, self.txt, self.js)
        self.assertEqual(self.txt.read_text(), "old")
        self.assert_no_temp()

    def test_stage_write_failure_preserves_both(self):
        self.txt.write_text("old txt")
        self.js.write_text("old json")
        with patch("asan_preview_export.os.fsync", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                write_preview(self.snapshot, self.txt, self.js)
        self.assertEqual(self.txt.read_text(), "old txt")
        self.assertEqual(self.js.read_text(), "old json")
        self.assert_no_temp()

    def test_second_replace_failure_rolls_back_existing(self):
        import os
        self.txt.write_text("old txt")
        self.js.write_text("old json")
        real_replace = os.replace
        counter = [0]
        def fail_second(src, dst):
            counter[0] += 1
            if counter[0] == 2:
                raise OSError("second commit failed")
            return real_replace(src, dst)
        with patch("asan_preview_export.os.replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                write_preview(self.snapshot, self.txt, self.js)
        self.assertEqual(self.txt.read_text(), "old txt")
        self.assertEqual(self.js.read_text(), "old json")
        self.assert_no_temp()

    def test_second_replace_failure_removes_new_first(self):
        import os
        real_replace = os.replace
        counter = [0]
        def fail_second(src, dst):
            counter[0] += 1
            if counter[0] == 2:
                raise OSError("second commit failed")
            return real_replace(src, dst)
        with patch("asan_preview_export.os.replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                write_preview(self.snapshot, self.txt, self.js)
        self.assertFalse(self.txt.exists())
        self.assertFalse(self.js.exists())
        self.assert_no_temp()

    def test_success_cleans_temps(self):
        report = write_preview(self.snapshot, self.txt, self.js)
        self.assertEqual(report["candidate_count"], 123)
        self.assertTrue(self.txt.exists() and self.js.exists())
        self.assert_no_temp()

if __name__ == "__main__":
    unittest.main()
