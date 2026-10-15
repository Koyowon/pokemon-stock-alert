"""Tests for read-only candidate intake, using synthetic snapshots only."""
import json
import tempfile
import unittest
from pathlib import Path

from store_registry.review_candidates import review


class CandidateReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        files = {
            "gs25_independent/gs25_stock_state.json": {"regions": {"namwon": {"stores": {"G1": {"name": "남원점"}}}}},
            "cu_stock_state.json": {"stores": {"C1": {"name": "기존CU", "city": "남원", "address": "남원시 1"}}},
            "stores.json": {"stores": {"E1": {"name": "기존이마트", "address": "전주시 2"}}},
            "emart24_jeonju_seed.json": {"stores": {"E1": {"name": "기존이마트", "address": "전주시 2"}}},
        }
        for name, value in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_new_and_duplicate_candidates(self):
        rows = [
            {"chain": "cu", "store_id": "C2", "name": "신규", "address": "남원시 도통동 2", "region": "namwon"},
            {"chain": "cu", "store_id": "C2", "name": "신규", "address": "남원시 도통동 2", "region": "namwon"},
            {"chain": "cu", "store_id": "C1", "name": "기존CU", "address": "남원시 1", "region": "namwon"},
        ]
        report = review(self.root, rows)
        self.assertEqual([x["status"] for x in report["candidates"]],
                         ["pending_approval", "duplicate_in_submission", "already_registered"])
        self.assertEqual(report["approved_for_production"], 0)

    def test_region_mismatch_and_existing_conflict(self):
        rows = [
            {"chain": "gs25", "store_id": "G2", "name": "진해점", "address": "창원시 진해구 1", "region": "namwon"},
            {"chain": "emart24", "store_id": "E1", "name": "변경점", "address": "전주시 2", "region": "jeonju"},
        ]
        self.assertEqual([x["status"] for x in review(self.root, rows)["candidates"]],
                         ["needs_region_review", "existing_conflict"])

    def test_invalid_and_no_file_mutation(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob("*.json")}
        result = review(self.root, [None, {"chain": "cu", "store_id": "X"}])
        self.assertEqual(result["counts"], {"invalid": 2})
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*.json")})


if __name__ == "__main__":
    unittest.main()
