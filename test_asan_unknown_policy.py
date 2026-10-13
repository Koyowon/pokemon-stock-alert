"""Offline Asan unknown-stock delivery policy regression."""
import unittest
from asan_stock_snapshot import build_snapshot
from asan_status_delivery import delivery_key
from asan_github_status_persistence import deliver_persistent

class UnknownPolicyTests(unittest.TestCase):
    def test_unknown_is_not_zero(self):
        s=build_snapshot({},query_succeeded=True)
        self.assertEqual(s['status_counts'], {'NOT_OBSERVED':123})
        self.assertTrue(all(row['stock'] is None for row in s['candidates']))
        self.assertEqual(len(delivery_key(s)),64)
    def test_not_queried_blocks(self):
        s=build_snapshot({},query_succeeded=False)
        with self.assertRaises(ValueError): delivery_key(s)
    def test_duplicate_registry_blocks(self):
        s=build_snapshot({},query_succeeded=True)
        s['candidates'][1]['registry_id']=s['candidates'][0]['registry_id']
        with self.assertRaises(ValueError): delivery_key(s)
    def test_missing_state_blocks_unknown_snapshot(self):
        s=build_snapshot({},query_succeeded=True)
        class Missing:
            def read(self): raise OSError('missing')
        self.assertEqual(deliver_persistent(s,['unknown'],lambda p:self.fail('sent'),Missing(),enabled=True),'STATE_UNAVAILABLE')
    def test_default_off(self):
        self.assertEqual(deliver_persistent({},[],lambda p:self.fail('sent'),object()),'DISABLED')
