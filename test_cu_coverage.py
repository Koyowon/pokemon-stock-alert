"""Offline, deterministic CU coverage tests; no API, Telegram, or state writes."""
import unittest
from cu_coverage import directory_identity_status, coverage_summary


class Tests(unittest.TestCase):
    def test_match(self):
        self.assertEqual(directory_identity_status(
            {"name": "CU 남원금동점", "address": "전북특별자치도 남원시 서문로 67 (금동)"},
            {"name": "남원금동점", "address": "전라북도 남원시 서문로 67"}), "MATCH")

    def test_wrong_address(self):
        self.assertEqual(directory_identity_status(
            {"name": "남원금동점", "address": "남원시 서문로 67"},
            {"name": "남원금동점", "address": "남원시 서문로 69"}), "CONFLICT")

    def test_unknown_address(self):
        self.assertEqual(directory_identity_status(
            {"name": "남원금동점", "address": "남원시 지번"},
            {"name": "남원금동점", "address": "남원시 서문로 67"}), "UNCERTAIN")

    def test_wrong_name(self):
        self.assertEqual(directory_identity_status(
            {"name": "남원금동점", "address": "남원시 서문로 67"},
            {"name": "남원중앙점", "address": "남원시 서문로 67"}), "CONFLICT")

    def test_missing_is_not_zero(self):
        result = coverage_summary(
            {"1": {"address": "남원시"}, "2": {"address": "아산시"}, "3": {"address": "전주시"}},
            {"1": {"stock": 3}}, ["남원시", "아산시"])
        self.assertEqual(result, {"eligible": 2, "observed": 1, "missing": 1, "missing_codes": ["2"]})


if __name__ == "__main__":
    unittest.main()
