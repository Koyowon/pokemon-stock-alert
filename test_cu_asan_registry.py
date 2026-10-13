"""Offline tests for the real Asan CU registry classifier.

Run: python -m unittest -v test_cu_asan_registry.py
No network, state writes, GitHub Actions, or Telegram calls.
"""
import unittest
from unittest.mock import patch

import cu_asan_registry as registry

ADDRESS = "충청남도 아산시 시민로 10"


def candidate(number, name="씨유 아산중앙점", address=ADDRESS, code=""):
    return {
        "registry_id": f"ASAN-CU-TEST-{number:03d}",
        "name": name,
        "address": address,
        "cu_store_code": code,
    }


def fixture(*selected):
    """Supply exactly 119 candidates without editing the real registry."""
    entries = list(selected)
    for index in range(len(entries), 119):
        entries.append(candidate(index + 1, name=f"씨유 테스트미조회{index}점",
                                 address=f"충청남도 아산시 테스트로 {index + 100}"))
    return entries


class AsanAutoMatchTests(unittest.TestCase):
    def classify(self, candidates, observations, success=True):
        with patch.object(registry, "load_registry", return_value=fixture(*candidates)):
            return registry.classify_observations(observations, query_succeeded=success)

    def test_exact_name_address_without_code(self):
        row = self.classify(
            [candidate(1)],
            {"12345": {"name": "CU아산중앙점", "address": ADDRESS, "stock": 4}},
        )[0]
        self.assertEqual((row["status"], row["stock"], row["match_method"],
                          row["observed_store_code"]),
                         ("IN_STOCK", 4, "EXACT_NAME_ADDRESS", "12345"))
        self.assertEqual(row["cu_store_code"], "")

    def test_address_mismatch_not_linked(self):
        row = self.classify(
            [candidate(1)],
            {"12345": {"name": "CU아산중앙점",
                       "address": "충청남도 아산시 시민로 11", "stock": 4}},
        )[0]
        self.assertEqual(row["status"], "NOT_OBSERVED")
        self.assertEqual(row["observed_store_code"], "")

    def test_api_duplicate_identity_not_linked(self):
        observations = {
            code: {"name": "CU아산중앙점", "address": ADDRESS, "stock": 3}
            for code in ("12345", "67890")
        }
        row = self.classify([candidate(1)], observations)[0]
        self.assertEqual(row["status"], "NOT_OBSERVED")

    def test_registry_duplicate_identity_not_linked(self):
        rows = self.classify(
            [candidate(1), candidate(2)],
            {"12345": {"name": "CU아산중앙점", "address": ADDRESS, "stock": 3}},
        )
        self.assertEqual([row["status"] for row in rows[:2]],
                         ["NOT_OBSERVED", "NOT_OBSERVED"])

    def test_unobserved_not_zero(self):
        row = self.classify([candidate(1)], {})[0]
        self.assertEqual(row["status"], "NOT_OBSERVED")
        self.assertIsNone(row["stock"])

    def test_not_queried_without_success(self):
        row = self.classify([candidate(1)], {}, success=False)[0]
        self.assertEqual(row["status"], "NOT_QUERIED")

    def test_registered_code_legacy_numeric_stock(self):
        row = self.classify([candidate(1, code="12345")], {"12345": 2})[0]
        self.assertEqual((row["status"], row["stock"], row["match_method"]),
                         ("IN_STOCK", 2, "REGISTERED_CODE"))

    def test_zero_stock(self):
        row = self.classify(
            [candidate(1)],
            {"12345": {"name": "CU아산중앙점", "address": ADDRESS, "stock": 0}},
        )[0]
        self.assertEqual((row["status"], row["stock"]), ("ZERO_STOCK", 0))

    def test_invalid_stock_is_not_zero(self):
        for value in (None, -1, "4", True):
            with self.subTest(stock=value):
                row = self.classify(
                    [candidate(1)],
                    {"12345": {"name": "CU아산중앙점",
                               "address": ADDRESS, "stock": value}},
                )[0]
                self.assertEqual(row["status"], "NO_VALID_STOCK_VALUE")

    def test_same_api_code_not_claimed_twice(self):
        rows = self.classify(
            [candidate(1, code="12345"), candidate(2)],
            {"12345": {"name": "CU아산중앙점", "address": ADDRESS, "stock": 2}},
        )
        self.assertEqual(rows[0]["status"], "IN_STOCK")
        self.assertEqual(rows[1]["status"], "NOT_OBSERVED")

    def test_normalization(self):
        self.assertEqual(registry.normalize_name("씨유 아산중앙점"),
                         registry.normalize_name("CU아산중앙점"))
        self.assertEqual(registry.normalize_address("충남 아산시 시민로 10"),
                         registry.normalize_address(ADDRESS))


if __name__ == "__main__":
    unittest.main()
