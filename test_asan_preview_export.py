"""Offline regression tests for the Asan preview exporter."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from asan_stock_snapshot import build_snapshot
from asan_preview_export import make_preview, write_preview

class PreviewExportTests(unittest.TestCase):
    def test_all_unknown(self):
        report = make_preview(build_snapshot({}))
        self.assertEqual(report["candidate_count"], 123)
        self.assertEqual(report["categories"]["not_queried"], 123)
        self.assertEqual(report["missing_registry_ids"], [])
        self.assertTrue(all(n <= 4096 for n in report["page_lengths"]))

    def test_positive_zero_unknown(self):
        snap = build_snapshot({"40059": {"stock": 0}, "53982": {"stock": 5}}, query_succeeded=True)
        report = make_preview(snap)
        self.assertEqual((report["categories"]["in_stock"], report["categories"]["zero_stock"], report["categories"]["not_observed"]), (1, 1, 121))
        self.assertIn("— 5개", "\n".join(report["pages"]))
        self.assertIn("— 0개", "\n".join(report["pages"]))

    def test_duplicate_id_rejected(self):
        snap = build_snapshot({})
        snap["candidates"][1]["registry_id"] = snap["candidates"][0]["registry_id"]
        with self.assertRaises(ValueError):
            make_preview(snap)

    def test_missing_candidate_rejected(self):
        snap = build_snapshot({})
        snap["candidates"].pop()
        with self.assertRaises(ValueError):
            make_preview(snap)

    def test_writes_valid_txt_json(self):
        snap = build_snapshot({})
        with tempfile.TemporaryDirectory() as directory:
            txt, js = Path(directory)/"preview.txt", Path(directory)/"preview.json"
            report = write_preview(snap, txt, js)
            self.assertEqual(json.loads(js.read_text(encoding="utf-8")), report)
            self.assertEqual(txt.read_text(encoding="utf-8"), "\n\n".join(report["pages"])+"\n")

    def test_no_mutation(self):
        snap = build_snapshot({})
        original = copy.deepcopy(snap)
        make_preview(snap)
        self.assertEqual(snap, original)

if __name__ == "__main__":
    unittest.main()
