"""Offline tests for Asan snapshot; never invoke network, state, or Telegram."""
import unittest
from asan_stock_snapshot import build_snapshot


class SnapshotTests(unittest.TestCase):
    def test_all_candidates_unknown_without_query(self):
        result = build_snapshot({})
        self.assertEqual(result["candidate_count"], 123)
        self.assertEqual(result["status_counts"], {"NOT_QUERIED": 123})
        self.assertTrue(all(row["stock"] is None for row in result["candidates"]))

    def test_unobserved_is_not_zero(self):
        result = build_snapshot({}, query_succeeded=True)
        self.assertEqual(result["status_counts"], {"NOT_OBSERVED": 123})
        self.assertTrue(all(row["stock"] is None for row in result["candidates"]))

    def test_registered_codes_match_and_preserve_zero(self):
        result = build_snapshot({
            "40059": {"name": "아산온양힐스테이트점", "address": "API 상세주소", "stock": 0},
            "53982": {"name": "아산온천타운점", "address": "API 상세주소", "stock": 3},
        }, query_succeeded=True)
        rows = {r["registry_id"]: r for r in result["candidates"]}
        self.assertEqual((rows["ASAN-CU-076"]["stock"], rows["ASAN-CU-076"]["status"]), (0, "ZERO_STOCK"))
        self.assertEqual((rows["ASAN-CU-046"]["stock"], rows["ASAN-CU-046"]["status"]), (3, "IN_STOCK"))
        self.assertEqual(rows["ASAN-CU-076"]["match_method"], "REGISTERED_CODE")
        self.assertEqual(rows["ASAN-CU-046"]["match_method"], "REGISTERED_CODE")

    def test_four_new_store_codes_match(self):
        codes = ["43799", "46004", "49877", "50619"]
        result = build_snapshot({code: {"stock": i + 1} for i, code in enumerate(codes)}, query_succeeded=True)
        rows = {r["cu_store_code"]: r for r in result["candidates"]}
        self.assertEqual([rows[code]["stock"] for code in codes], [1, 2, 3, 4])
        self.assertEqual(result["status_counts"]["IN_STOCK"], 4)


if __name__ == "__main__":
    unittest.main()
