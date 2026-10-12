import unittest
from gs25_asan_guard import filter_asan_seen, approved_codes

class GuardTests(unittest.TestCase):
    def test_known_retained(self):
        seen={'A': {'quantity': 2}, 'OTHER': {'quantity': 14}}
        self.assertEqual(filter_asan_seen(seen, {'stores': {'A': {'quantity': 1}}}), {'A': {'quantity': 2}})
    def test_unverified_not_approved(self):
        self.assertFalse(approved_codes())
    def test_absent_prior(self):
        self.assertEqual(filter_asan_seen({'OTHER': {'quantity': 2}}, None), {})

if __name__ == '__main__': unittest.main()
