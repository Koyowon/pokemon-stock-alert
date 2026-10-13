"""Offline-only opt-in status delivery tests: no actual Telegram/API calls."""
import json
import tempfile
import unittest
from pathlib import Path
from asan_stock_snapshot import build_snapshot
from asan_stock_chunks import preview_asan_stock_messages
from asan_status_delivery import send_status, enabled, delivery_key


class AsanStatusDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.marker = Path(self.tmp.name) / "asan-status-marker.json"
        self.snapshot = build_snapshot({"53982": {"stock": 3}}, query_succeeded=True)
        self.pages = preview_asan_stock_messages(self.snapshot)
        self.env = {"ASAN_CU_STATUS_TELEGRAM_ENABLED": "true"}

    def send(self, snapshot=None, pages=None, sender=None, env=None):
        return send_status(snapshot or self.snapshot, pages or self.pages,
                           sender or (lambda page: True),
                           marker_path=self.marker,
                           environ=self.env if env is None else env)

    def test_disabled_by_default(self):
        sent = []
        self.assertEqual(self.send(sender=lambda p: sent.append(p), env={}), "DISABLED")
        self.assertEqual(sent, [])
        self.assertFalse(self.marker.exists())

    def test_explicit_opt_in_only(self):
        self.assertFalse(enabled({"ASAN_CU_STATUS_TELEGRAM_ENABLED": "1"}))
        self.assertTrue(enabled(self.env))

    def test_initial_send_and_marker(self):
        sent = []
        self.assertEqual(self.send(sender=lambda p: sent.append(p) or True), "SENT")
        self.assertEqual(sent, self.pages)
        self.assertEqual(json.loads(self.marker.read_text())["key"], delivery_key(self.snapshot))

    def test_same_snapshot_not_resent(self):
        self.assertEqual(self.send(), "SENT")
        sent = []
        self.assertEqual(self.send(sender=lambda p: sent.append(p) or True), "UNCHANGED")
        self.assertEqual(sent, [])

    def test_changed_stock_sends_again(self):
        self.assertEqual(self.send(), "SENT")
        updated = build_snapshot({"53982": {"stock": 4}}, query_succeeded=True)
        sent = []
        self.assertEqual(self.send(snapshot=updated, pages=preview_asan_stock_messages(updated),
                                   sender=lambda p: sent.append(p) or True), "SENT")
        self.assertTrue(sent)

    def test_failed_send_no_marker(self):
        self.assertEqual(self.send(sender=lambda p: False), "SEND_FAILED")
        self.assertFalse(self.marker.exists())

    def test_partial_query_rejected(self):
        partial = build_snapshot({}, query_succeeded=False)
        with self.assertRaises(ValueError):
            self.send(snapshot=partial)

    def test_invalid_marker_blocks_send(self):
        self.marker.write_text("{broken")
        sent = []
        self.assertEqual(self.send(sender=lambda p: sent.append(p)), "INVALID_MARKER")
        self.assertFalse(sent)

    def test_no_marker_path_blocks_send(self):
        sent = []
        self.assertEqual(send_status(self.snapshot, self.pages,
                         lambda p: sent.append(p), environ=self.env), "NO_MARKER_PATH")
        self.assertFalse(sent)

    def test_oversized_page_rejected(self):
        with self.assertRaises(ValueError):
            self.send(pages=["x" * 4097])

    def test_marker_cannot_be_legacy_state(self):
        from cu_stock_monitor import STATE_FILE
        sent = []
        self.assertEqual(send_status(self.snapshot, self.pages,
                         lambda p: sent.append(p), marker_path=STATE_FILE,
                         environ=self.env), "INVALID_MARKER_PATH")
        self.assertFalse(sent)


if __name__ == "__main__":
    unittest.main()
