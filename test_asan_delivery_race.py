"""Offline race, partial-send and retry guards for Asan Telegram status."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from asan_status_delivery import send_status
from asan_stock_snapshot import build_snapshot
from asan_stock_chunks import preview_asan_stock_messages

class DeliveryRaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.marker = Path(self.temp.name) / "status.json"
        self.snapshot = build_snapshot({"53982": {"stock": 2}}, query_succeeded=True)
        self.pages = preview_asan_stock_messages(self.snapshot)
        self.env = {"ASAN_CU_STATUS_TELEGRAM_ENABLED": "true"}

    def send(self, sender, pages=None):
        return send_status(self.snapshot, self.pages if pages is None else pages,
                           sender, marker_path=self.marker, environ=self.env)

    def test_parallel_call_is_locked(self):
        started, release = threading.Event(), threading.Event()
        sent, results = [], []
        def slow(page):
            sent.append(page)
            started.set()
            self.assertTrue(release.wait(5))
            return True
        worker = threading.Thread(target=lambda: results.append(self.send(slow)))
        worker.start()
        self.assertTrue(started.wait(5))
        self.assertEqual(self.send(lambda p: self.fail("duplicate send")), "LOCKED")
        release.set()
        worker.join(5)
        self.assertEqual(results, ["SENT"])
        self.assertEqual(len(sent), len(self.pages))

    def test_second_page_failure_does_not_resend_first(self):
        sent = []
        def sender(page):
            sent.append(page)
            return len(sent) == 1
        self.assertEqual(self.send(sender, ["page one", "page two"]), "NEEDS_RECONCILIATION")
        self.assertEqual(sent, ["page one", "page two"])
        self.assertEqual(self.send(lambda p: self.fail("must not resend"), ["page one", "page two"]), "NEEDS_RECONCILIATION")
        self.assertEqual(json.loads(self.marker.read_text())["page_index"], 1)

    def test_exception_blocks_retry(self):
        def bad(page):
            raise TimeoutError("uncertain delivery")
        self.assertEqual(self.send(bad), "NEEDS_RECONCILIATION")
        self.assertEqual(self.send(lambda p: self.fail("must not resend")), "NEEDS_RECONCILIATION")

    def test_first_page_false_blocks_retry(self):
        self.assertEqual(self.send(lambda p: False), "SEND_FAILED")
        self.assertEqual(self.send(lambda p: self.fail("must not resend")), "NEEDS_RECONCILIATION")

    def test_completed_run_deduplicated(self):
        self.assertEqual(self.send(lambda p: True), "SENT")
        self.assertEqual(self.send(lambda p: self.fail("duplicate")), "UNCHANGED")

    def test_marker_write_failure_prevents_sender(self):
        with patch("asan_status_delivery._atomic_marker", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.send(lambda p: self.fail("must not send"))

if __name__ == "__main__":
    unittest.main()
