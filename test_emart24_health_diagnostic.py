"""Run: python -m unittest -v test_emart24_health_diagnostic.py"""
import unittest
from emart24_health_diagnostic import Health, diagnose


class HealthDiagnosticTests(unittest.TestCase):
    def test_http_502(self):
        result = diagnose({"a": "HTTP_502", "b": "NOT_CHECKED"}, {})
        self.assertEqual((result.health, result.checked, result.unknown, result.http_502),
                         (Health.UNKNOWN, 0, 2, 1))

    def test_verified_zero(self):
        result = diagnose({"a": "OK"}, {"a": 0})
        self.assertEqual((result.health, result.checked, result.unknown), (Health.OK, 1, 0))

    def test_partial_success(self):
        result = diagnose({"a": "OK", "b": "HTTP_502"}, {"a": 0})
        self.assertEqual((result.health, result.checked, result.unknown),
                         (Health.PARTIAL, 1, 1))

    def test_recovery(self):
        result = diagnose({"a": "OK"}, {"a": 0}, previous_health=Health.UNKNOWN)
        self.assertTrue(result.recovered)
        self.assertEqual(result.health, Health.OK)

    def test_partial_is_not_full_recovery(self):
        result = diagnose({"a": "OK", "b": "NOT_CHECKED"}, {"a": 2},
                          previous_health=Health.UNKNOWN)
        self.assertFalse(result.recovered)

    def test_invalid_values_never_count_as_stock(self):
        for invalid in (True, -1, "0", None, 1.5):
            with self.subTest(invalid=invalid):
                self.assertEqual(diagnose({"a": "OK"}, {"a": invalid}).health,
                                 Health.UNKNOWN)

    def test_generic_error_not_mislabeled_502(self):
        result = diagnose({"a": "SINGLE_ERROR"}, {})
        self.assertEqual(result.http_502, 0)

    def test_unregistered_store_rejected(self):
        with self.assertRaises(ValueError):
            diagnose({}, {"a": 1})


if __name__ == "__main__":
    unittest.main()
