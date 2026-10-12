"""Offline regression tests for GS25 guard integration; no API/Telegram calls."""
import ast
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent
REPO = pathlib.Path.cwd()
sys.path.insert(0, str(REPO / 'gs25_independent'))
from gs25_asan_guard import filter_asan_seen, approved_codes

class GuardIntegrationTests(unittest.TestCase):
    def test_existing_asan_store_retained_and_quantity_updated(self):
        prior = {'stores': {'EXISTING': {'name': 'Old', 'quantity': 1}}}
        result = filter_asan_seen({'EXISTING': {'name': 'Old', 'quantity': 3}, 'UNVERIFIED': {'name': 'Other', 'quantity': 14}}, prior)
        self.assertEqual(result, {'EXISTING': {'name': 'Old', 'quantity': 3}})

    def test_unknown_new_asan_store_excluded(self):
        self.assertEqual(filter_asan_seen({'NEW': {'quantity': 14}}, {'stores': {}}), {})

    def test_approved_code_can_be_included(self):
        with patch('gs25_asan_guard.approved_codes', return_value={'VERIFIED'}):
            self.assertEqual(filter_asan_seen({'VERIFIED': {'quantity': 2}, 'OTHER': {'quantity': 2}}, None), {'VERIFIED': {'quantity': 2}})

    def test_production_code_contains_filter_before_alerts(self):
        source = (REPO / 'gs25_independent/gs25_auto_monitor.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn("if rid == 'asan' and not failed:", source)
        self.assertIn('seen = filter_asan_seen(seen, prior_asan)', source)
        self.assertLess(source.index('seen = filter_asan_seen(seen, prior_asan)'), source.index('        positives = {sid: item'))

    def test_no_unapproved_codes(self):
        self.assertEqual(approved_codes(), set())

if __name__ == '__main__':
    unittest.main(verbosity=2)
