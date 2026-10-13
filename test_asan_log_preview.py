"""Offline tests for safe monitor log conversion."""
import json
import tempfile
import unittest
from pathlib import Path
from asan_stock_snapshot import build_snapshot
from asan_log_preview import parse_monitor_log, convert_monitor_log

def log_for(snapshot=None, *, ok=7, failed=0, finished=True, duplicate=False):
    snapshot = snapshot if snapshot is not None else build_snapshot({}, query_succeeded=True)
    lines = ["QUERY_OK: 아산 36.790 127.000 VALID_STORES: 0"] * ok
    lines += ["QUERY_ERROR: 아산 36.790 127.000 TimeoutError"] * failed
    line = "ASAN_CU_STOCK_SNAPSHOT: " + json.dumps(snapshot, ensure_ascii=False)
    lines.append(line)
    if duplicate:
        lines.append(line)
    if finished:
        lines.append("CU STOCK MONITOR FINISHED")
    return "\n".join(lines)

class AsanLogPreviewTests(unittest.TestCase):
    def test_valid_complete_log(self):
        self.assertEqual(parse_monitor_log(log_for())["candidate_count"], 123)

    def test_missing_snapshot(self):
        with self.assertRaises(ValueError):
            parse_monitor_log("QUERY_OK: 아산 1 1\nCU STOCK MONITOR FINISHED")

    def test_duplicate_snapshot(self):
        with self.assertRaises(ValueError):
            parse_monitor_log(log_for(duplicate=True))

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            parse_monitor_log(log_for().replace("ASAN_CU_STOCK_SNAPSHOT: {", "ASAN_CU_STOCK_SNAPSHOT: {broken"))

    def test_partial_query(self):
        for text in (log_for(ok=6), log_for(failed=1), log_for(finished=False)):
            with self.subTest(text=text[-40:]), self.assertRaises(ValueError):
                parse_monitor_log(text)

    def test_wrong_id_set(self):
        snap = build_snapshot({}, query_succeeded=True)
        snap["candidates"][0]["registry_id"] = "ASAN-CU-999"
        with self.assertRaises(ValueError):
            parse_monitor_log(log_for(snap))

    def test_not_queried_rejected(self):
        with self.assertRaises(ValueError):
            parse_monitor_log(log_for(build_snapshot({})))

    def test_invalid_barcode(self):
        snap = build_snapshot({}, query_succeeded=True)
        snap["barcode"] = "wrong"
        with self.assertRaises(ValueError):
            parse_monitor_log(log_for(snap))

    def test_failed_input_creates_no_files(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p/"log.txt").write_text(log_for(ok=6), encoding="utf-8")
            with self.assertRaises(ValueError):
                convert_monitor_log(p/"log.txt", p/"preview.txt", p/"preview.json")
            self.assertFalse((p/"preview.txt").exists())
            self.assertFalse((p/"preview.json").exists())

    def test_valid_files(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p/"log.txt").write_text(log_for(), encoding="utf-8")
            report = convert_monitor_log(p/"log.txt", p/"preview.txt", p/"preview.json")
            self.assertEqual(json.loads((p/"preview.json").read_text(encoding="utf-8")), report)
            self.assertTrue((p/"preview.txt").exists())

if __name__ == "__main__":
    unittest.main()
