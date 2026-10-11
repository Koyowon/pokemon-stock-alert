"""Offline contract tests. No GS25 network access or secret usage."""
import unittest
from provider import Status, StockResult, query_stock

class ProviderTests(unittest.TestCase):
    def test_unconfigured_does_not_claim_zero(self):
        result = query_stock(item_code='8800286275732', store_id='TEST_STORE')
        self.assertEqual(result.status, Status.NOT_CONFIGURED)
        self.assertIsNone(result.quantity)

    def test_unknown_cannot_claim_quantity(self):
        with self.assertRaises(ValueError):
            StockResult(status=Status.UNKNOWN, quantity=0)

    def test_verified_quantity_requires_store(self):
        with self.assertRaises(ValueError):
            StockResult(status=Status.AVAILABLE, quantity=3)

    def test_verified_zero_is_valid_only_when_verified(self):
        self.assertEqual(StockResult(status=Status.AVAILABLE, quantity=0, store_id='S1').quantity, 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
