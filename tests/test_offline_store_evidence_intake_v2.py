"""Offline evidence intake regression: no store-code assignment or network."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
import csv
import json

spec = importlib.util.spec_from_file_location("intake", Path(__file__).with_name("offline_store_evidence_intake_v2.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {"name": "씨유아산둔포원룸점", "address": "충청남도 아산시 둔포면 둔포로 78"}
        self.row = dict(chain="cu", registry_id="ASAN-CU-001", store_code="12345",
                        name="CU아산둔포원룸점", address=self.candidate["address"],
                        source_url="https://example.org/fixture", observed_at="2026-10-14", barcode=m.TARGET)
        self.candidates = {"ASAN-CU-001": self.candidate}

    def test_manual_review_only(self):
        self.assertEqual(m.evaluate(self.row, candidates=self.candidates), "MANUAL_REVIEW_REQUIRED")

    def test_existing_code(self):
        self.assertEqual(m.evaluate(self.row, ["12345"], self.candidates), "REJECT_CODE_COLLISION")

    def test_wrong_barcode(self):
        self.row["barcode"] = "other"
        self.assertEqual(m.evaluate(self.row, candidates=self.candidates), "REJECT_BARCODE")

    def test_wrong_name(self):
        self.row["name"] = "다른점"
        self.assertEqual(m.evaluate(self.row, candidates=self.candidates), "REJECT_NAME_MISMATCH")

    def test_missing_provenance(self):
        self.row["source_url"] = ""
        self.assertEqual(m.evaluate(self.row, candidates=self.candidates), "REJECT_PROVENANCE")

    def test_unknown_registry(self):
        self.row["registry_id"] = "unknown"
        self.assertEqual(m.evaluate(self.row, candidates=self.candidates), "REJECT_UNKNOWN_REGISTRY_ID")

    def test_jeju_location(self):
        self.row.update(chain="emart24", address="충청남도 아산시 테스트로 1")
        self.assertEqual(m.evaluate(self.row), "REJECT_NOT_JEJU")

    def test_jeju_manual_only(self):
        self.row.update(chain="emart24", address="제주특별자치도 제주시 테스트로 1")
        self.assertEqual(m.evaluate(self.row), "MANUAL_REVIEW_REQUIRED")

    def test_batch_duplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "registry.json").write_text(json.dumps({"stores": [dict(self.candidate, registry_id="ASAN-CU-001", cu_store_code="")]}), encoding="utf-8")
            (root / "cu.json").write_text('{"stores":{}}', encoding="utf-8")
            (root / "emart.json").write_text('{"stores":{}}', encoding="utf-8")
            with (root / "evidence.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=sorted(m.FIELDS))
                writer.writeheader()
                writer.writerows([self.row, self.row])
            self.assertEqual([x["status"] for x in m.review_csv(root/"evidence.csv", root/"registry.json", root/"cu.json", root/"emart.json")], ["REJECT_BATCH_DUPLICATE"] * 2)

if __name__ == "__main__":
    unittest.main()
