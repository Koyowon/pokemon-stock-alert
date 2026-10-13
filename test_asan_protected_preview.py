"""Offline path-collision and rollback failure regression tests."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from asan_stock_snapshot import build_snapshot
from asan_preview_export import write_preview
from asan_log_preview import convert_monitor_log
from test_asan_log_preview import log_for

class ProtectedPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snap = build_snapshot({})
        self.txt = self.root / "out.txt"
        self.js = self.root / "out.json"

    def test_state_filename_forbidden(self):
        state = self.root / "cu_stock_state.json"
        state.write_text("state", encoding="utf-8")
        with self.assertRaises(ValueError):
            write_preview(self.snap, state, self.js)
        self.assertEqual(state.read_text(), "state")
        self.assertFalse(self.js.exists())

    def test_registry_filename_forbidden(self):
        registry = self.root / "asan_cu_watch_registry.json"
        with self.assertRaises(ValueError):
            write_preview(self.snap, self.txt, registry)
        self.assertFalse(self.txt.exists())

    def test_symlink_to_state_forbidden(self):
        state = self.root / "state.txt"
        state.write_text("protected")
        alias = self.root / "out.txt"
        alias.symlink_to(state)
        with self.assertRaises(ValueError):
            write_preview(self.snap, alias, self.js)
        self.assertEqual(state.read_text(), "protected")

    def test_relative_path_collision(self):
        with patch("os.getcwd", return_value=str(self.root)):
            pass
        import os as operating_system
        previous = Path.cwd()
        try:
            operating_system.chdir(self.root)
            with self.assertRaises(ValueError):
                write_preview(self.snap, "out.txt", "./out.txt")
        finally:
            operating_system.chdir(previous)

    def test_input_log_collision(self):
        log = self.root / "monitor.log"
        log.write_text(log_for(), encoding="utf-8")
        with self.assertRaises(ValueError):
            convert_monitor_log(log, log, self.js)
        self.assertIn("ASAN_CU_STOCK_SNAPSHOT", log.read_text())
        self.assertFalse(self.js.exists())

    def test_input_log_hardlink_collision(self):
        log = self.root / "monitor.log"
        log.write_text(log_for(), encoding="utf-8")
        alias = self.root / "alias.txt"
        os.link(log, alias)
        with self.assertRaises(ValueError):
            convert_monitor_log(log, alias, self.js)
        self.assertIn("ASAN_CU_STOCK_SNAPSHOT", log.read_text())

    def test_rollback_failure_preserves_backup(self):
        self.txt.write_text("original txt")
        self.js.write_text("original json")
        real_replace = os.replace
        calls = [0]
        def injected(src, dst):
            calls[0] += 1
            if calls[0] in (2, 3):
                raise OSError("injected commit/rollback failure")
            return real_replace(src, dst)
        with patch("asan_preview_export.os.replace", side_effect=injected):
            with self.assertRaises(RuntimeError):
                write_preview(self.snap, self.txt, self.js)
        backups = list(self.root.glob(".asan-backup-*"))
        self.assertTrue(any(p.read_text() == "original txt" for p in backups))
        self.assertEqual(self.js.read_text(), "original json")

if __name__ == "__main__":
    unittest.main()
