"""Offline guard tests for the opt-in Git CAS wiring; no live calls."""
import ast
import unittest
from pathlib import Path
from unittest.mock import patch

class AsanMonitorGitWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).with_name("cu_stock_monitor.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_git_cas_wired_not_local_marker(self):
        self.assertIn("GitBranchCAS(Path(__file__).resolve().parent)", self.source)
        self.assertIn("result = deliver_persistent(", self.source)
        self.assertNotIn("result = send_status(", self.source)

    def test_explicit_flag_guard_and_coverage(self):
        self.assertIn("asan_status_enabled() and", self.source)
        self.assertIn('asan_successful_queries == len(POINTS["아산"])', self.source)
        self.assertIn("and not conflicts", self.source)

    def test_legacy_save_precedes_status(self):
        self.assertLess(self.source.index("    save_state(state)"), self.source.index("    # Independent Asan status channel"))

    def test_persistent_path_is_fail_closed(self):
        from asan_github_status_persistence import deliver_persistent
        from asan_stock_snapshot import build_snapshot
        snap = build_snapshot({}, query_succeeded=True)
        class Missing:
            def read(self):
                raise OSError("missing branch")
        sent = []
        self.assertEqual(deliver_persistent(snap, ["page"], lambda p: sent.append(p),
                                            Missing(), enabled=True), "STATE_UNAVAILABLE")
        self.assertFalse(sent)

if __name__ == "__main__":
    unittest.main()
