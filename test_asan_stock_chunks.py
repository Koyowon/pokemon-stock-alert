"""Offline-only tests for Telegram-safe chunking and preview."""
import copy
import unittest
from asan_stock_chunks import split_telegram_text, preview_asan_stock_messages
from asan_stock_message import format_asan_stock_message
from asan_stock_snapshot import build_snapshot


class ChunkTests(unittest.TestCase):
    def test_all_123_unknown_fit_and_preserve_order(self):
        snap = build_snapshot({}, query_succeeded=True)
        pages = preview_asan_stock_messages(snap)
        self.assertTrue(all(len(page) <= 4096 for page in pages))
        self.assertEqual(len(pages), 2)
        ids = [row["registry_id"] for row in snap["candidates"]]
        combined = "\n".join(page.split("\n", 1)[1] for page in pages)
        self.assertEqual([combined.index(id) for id in ids], sorted(combined.index(id) for id in ids))
        self.assertEqual(combined, format_asan_stock_message(snap))

    def test_positive_zero_and_unknown_preserved(self):
        snap = build_snapshot({"40059": {"stock": 0}, "53982": {"stock": 8}}, query_succeeded=True)
        text = "\n".join(page.split("\n", 1)[1] for page in preview_asan_stock_messages(snap))
        self.assertIn("— 8개", text)
        self.assertIn("— 0개", text)
        self.assertIn("미확인 (NOT_OBSERVED)", text)

    def test_short_message_unchanged(self):
        self.assertEqual(split_telegram_text("short"), ["short"])

    def test_reject_overlong_line(self):
        with self.assertRaises(ValueError):
            split_telegram_text("x" * 4100)

    def test_small_limit_and_page_numbering(self):
        pages = split_telegram_text("a\n" * 70 + "end", limit=48)
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(page) <= 48 for page in pages))
        self.assertEqual("\n".join(page.split("\n", 1)[1] for page in pages), "a\n" * 70 + "end")

    def test_pure_does_not_mutate_snapshot(self):
        snap = build_snapshot({})
        before = copy.deepcopy(snap)
        preview_asan_stock_messages(snap)
        self.assertEqual(snap, before)


if __name__ == "__main__":
    unittest.main()
