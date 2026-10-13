"""Network-free, state-free formatter tests."""
import copy
import unittest
from asan_stock_snapshot import build_snapshot
from asan_stock_message import format_asan_stock_message


class AsanStockMessageTests(unittest.TestCase):
    def test_all_not_queried(self):
        text = format_asan_stock_message(build_snapshot({}))
        self.assertIn("재고 미확인: 123개 점포", text)
        self.assertIn("확인 불가 (NOT_QUERIED)", text)
        self.assertNotIn("— 0개", text)

    def test_all_not_observed(self):
        text = format_asan_stock_message(build_snapshot({}, query_succeeded=True))
        self.assertIn("재고 미확인: 123개 점포", text)
        self.assertIn("확인 불가 (NOT_OBSERVED)", text)

    def test_positive_zero_unknown_separate(self):
        snap = build_snapshot({"40059": {"stock": 0}, "53982": {"stock": 3}}, query_succeeded=True)
        text = format_asan_stock_message(snap)
        self.assertIn("재고 있음: 1개 점포", text)
        self.assertIn("재고 0개: 1개 점포", text)
        self.assertIn("재고 미확인: 121개 점포", text)
        self.assertIn("아산온천타운점 [ASAN-CU-046] — 3개", text)
        self.assertIn("아산온양힐스테이트점 [ASAN-CU-076] — 0개", text)

    def test_invalid_status_rejected(self):
        snap = build_snapshot({})
        snap["candidates"][0]["status"] = "OTHER"
        with self.assertRaises(ValueError):
            format_asan_stock_message(snap)

    def test_invalid_quantity_rejected(self):
        snap = build_snapshot({"40059": {"stock": 1}}, query_succeeded=True)
        snap["candidates"][75]["stock"] = None
        with self.assertRaises(ValueError):
            format_asan_stock_message(snap)

    def test_does_not_mutate_snapshot(self):
        snap = build_snapshot({})
        before = copy.deepcopy(snap)
        format_asan_stock_message(snap)
        self.assertEqual(snap, before)


if __name__ == "__main__":
    unittest.main()
