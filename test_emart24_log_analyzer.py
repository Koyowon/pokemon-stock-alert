"""Offline: python -m unittest -v test_emart24_log_analyzer.py"""
import unittest
from emart24_health_diagnostic import Health
from emart24_log_analyzer import analyze


class LogAnalyzerTests(unittest.TestCase):
    def test_502_and_unknown(self):
        log = ("WARNING: inventory batch failed (3 stores): inventory: HTTPError: HTTP Error 502: Bad Gateway\n"
               "STORE 001 | Store A | SINGLE_ERROR\n"
               "STORE 002 | Store B | NOT_CHECKED\n"
               "item: 0/2 numeric results\n")
        result = analyze(log)
        self.assertEqual((result.health, result.http_502_evidence, result.unknown_stores),
                         ("UNKNOWN", True, 2))

    def test_generic_error_not_502(self):
        result = analyze("WARNING: inventory batch failed (3 stores): timeout\n"
                         "STORE 001 | X | BATCH_ERROR\n")
        self.assertTrue(result.generic_error_evidence)
        self.assertFalse(result.http_502_evidence)

    def test_ok_does_not_claim_zero(self):
        result = analyze("STORE 001 | X | OK\nitem: 1/1 numeric results\n")
        self.assertEqual(result.health, "OK")
        self.assertIsNone(result.confirmed_zero_stores)

    def test_partial_success(self):
        result = analyze("STORE 001 | X | OK\nSTORE 002 | Y | SINGLE_ERROR\n"
                         "item: 1/2 numeric results\n")
        self.assertEqual((result.health, result.verified_numeric_stores), ("PARTIAL", 1))

    def test_recovery(self):
        result = analyze("STORE 001 | X | OK\nitem: 1/1 numeric results\n",
                         previous_health=Health.UNKNOWN)
        self.assertTrue(result.recovered)

    def test_partial_not_full_recovery(self):
        result = analyze("STORE 001 | X | OK\nSTORE 002 | Y | NOT_CHECKED\n",
                         previous_health=Health.UNKNOWN)
        self.assertFalse(result.recovered)

    def test_redaction(self):
        result = analyze("TOKEN=supersecret\nSTORE 001 | private store name | OK\n")
        self.assertNotIn("supersecret", str(result.safe_dict()))
        self.assertNotIn("private store name", str(result.safe_dict()))
        self.assertNotIn("001", str(result.safe_dict()))

    def test_incomplete_log_not_healthy(self):
        result = analyze("STORE 001 | X | OK\nitem: 2/2 numeric results\n")
        self.assertEqual(result.health, "UNKNOWN")

    def test_empty_log_not_healthy(self):
        self.assertEqual(analyze("").health, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
