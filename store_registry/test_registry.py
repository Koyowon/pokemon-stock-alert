"""Offline tests: synthetic fixtures only, no HTTP/Telegram/filesystem writes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from store_registry.build_registry import build


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.put("gs25_independent/gs25_stock_state.json", {"regions": {
            "jeonju": {"stores": {"A": {"name": "Alpha", "quantity": 2}}},
            "asan": {"stores": {"A": {"name": "Alpha", "quantity": 0}}},
        }})
        self.put("cu_stock_state.json", {"stores": {
            "A": {"name": "CU Alpha", "city": "전주", "address": "전주시 1"}
        }})
        self.put("stores.json", {"stores": {
            "E": {"name": "Emart", "address": "전북특별자치도 전주시 완산구 1"}
        }})
        self.put("emart24_jeonju_seed.json", {"stores": {
            "E": {"name": "Emart", "address": "전북특별자치도 전주시 완산구 1"}
        }})

    def put(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")

    def test_deduplicate_within_chain_and_across_sources(self):
        result = build(self.root)
        self.assertEqual(result["report"]["total_unique"], 3)
        self.assertEqual(result["report"]["by_chain"], {"cu": 1, "emart24": 1, "gs25": 1})
        em = next(x for x in result["records"] if x["chain"] == "emart24")
        self.assertEqual(len(em["sources"]), 2)

    def test_conflicting_region_is_reported_not_silently_merged(self):
        result = build(self.root)
        self.assertTrue(any(x["key"] == "gs25:A" and x["field"] == "region"
                            for x in result["report"]["conflicts"]))

    def test_missing_address_is_flagged(self):
        result = build(self.root)
        self.assertTrue(any(x["reason"] == "missing_address" and x["source"].startswith("gs25")
                            for x in result["report"]["issues"]))

    def test_no_network_or_mutation_of_input(self):
        paths = list(self.root.rglob("*.json"))
        before = {str(p): p.read_bytes() for p in paths}
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            build(self.root)
        self.assertEqual(before, {str(p): p.read_bytes() for p in paths})


if __name__ == "__main__":
    unittest.main()
