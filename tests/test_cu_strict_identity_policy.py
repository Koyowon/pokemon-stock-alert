"""Synthetic tests for proposed identity quarantine; no production imports or network."""
import unittest
from cu_strict_identity_policy import canonical, reconcile_strict


def store(code="12345", stock=2, city="아산", name="CU 테스트점", address="충청남도 아산시 온천동 1"):
    return dict(code=code, stock=stock, city=city, name=name, address=address)


class StrictIdentityTests(unittest.TestCase):
    def test_identical_duplicate(self):
        accepted, q = reconcile_strict([[store()], [store()]])
        self.assertEqual(len(accepted), 1)
        self.assertFalse(q)

    def test_stock_conflict(self):
        accepted, q = reconcile_strict([[store()], [store(stock=0)]])
        self.assertNotIn("12345", accepted)
        self.assertEqual(q["12345"], {"STOCK_CONFLICT"})

    def test_name_conflict_even_when_stock_same(self):
        accepted, q = reconcile_strict([[store()], [store(name="CU 다른점")]])
        self.assertNotIn("12345", accepted)
        self.assertEqual(q["12345"], {"NAME_CONFLICT"})

    def test_address_conflict_even_when_stock_same(self):
        accepted, q = reconcile_strict([[store()], [store(address="충청남도 아산시 온천동 2")]])
        self.assertNotIn("12345", accepted)
        self.assertEqual(q["12345"], {"ADDRESS_CONFLICT"})

    def test_city_conflict(self):
        accepted, q = reconcile_strict([[store()], [store(city="전주")]])
        self.assertNotIn("12345", accepted)
        self.assertEqual(q["12345"], {"CITY_CONFLICT"})

    def test_combined_conflict_reasons(self):
        _, q = reconcile_strict([[store()], [store(stock=0, name="B", address="B")]])
        self.assertEqual(q["12345"], {"STOCK_CONFLICT", "NAME_CONFLICT", "ADDRESS_CONFLICT"})

    def test_whitespace_nfkc_normalized(self):
        self.assertEqual(canonical(" CU  테스트점  "), "CU 테스트점")
        accepted, q = reconcile_strict([[store()], [store(name="CU   테스트점")]])
        self.assertEqual(len(accepted), 1)
        self.assertFalse(q)

    def test_conflict_sticky(self):
        accepted, q = reconcile_strict([[store()], [store(name="B")], [store()]])
        self.assertNotIn("12345", accepted)
        self.assertIn("12345", q)

    def test_missing_identity_quarantined(self):
        accepted, q = reconcile_strict([[store(name="")]])
        self.assertEqual(accepted, {})
        self.assertEqual(q["12345"], {"MISSING_IDENTITY"})

    def test_invalid_stock_quarantined(self):
        accepted, q = reconcile_strict([[store(stock=-1)]])
        self.assertEqual(accepted, {})
        self.assertEqual(q["12345"], {"INVALID_STOCK"})

    def test_unobserved_not_zero(self):
        accepted, q = reconcile_strict([[], [store(code="99999", stock=0)]])
        self.assertNotIn("12345", accepted)
        self.assertEqual(accepted["99999"]["stock"], 0)
        self.assertFalse(q)

    def test_distinct_codes(self):
        accepted, q = reconcile_strict([[store(), store(code="99999")]])
        self.assertEqual(len(accepted), 2)
        self.assertFalse(q)


if __name__ == "__main__":
    unittest.main()
