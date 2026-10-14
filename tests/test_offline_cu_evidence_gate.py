import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('cu_gate', Path(__file__).with_name('offline_cu_evidence_gate.py'))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.c = {'name': '씨유 아산중앙점', 'address': '충청남도 아산시 테스트로 1'}
        self.o = {'code': '12345', 'name': 'CU아산중앙점', 'address': '충청남도 아산시 테스트로 1',
                  'source': 'offline-fixture', 'observed_at': '2026-10-14'}

    def test_matching_requires_manual_review(self):
        self.assertEqual(gate.review(self.c, self.o), 'MANUAL_REVIEW_REQUIRED')

    def test_missing_code(self):
        self.o['code'] = ''
        self.assertEqual(gate.review(self.c, self.o), 'REJECT_INVALID_CODE')

    def test_existing_code(self):
        self.assertEqual(gate.review(self.c, self.o, ['12345']), 'REJECT_ALREADY_ASSIGNED')

    def test_missing_provenance(self):
        self.o.pop('source')
        self.assertEqual(gate.review(self.c, self.o), 'REJECT_NO_PROVENANCE')

    def test_missing_date(self):
        self.o.pop('observed_at')
        self.assertEqual(gate.review(self.c, self.o), 'REJECT_NO_PROVENANCE')

    def test_wrong_name(self):
        self.o['name'] = '다른점'
        self.assertEqual(gate.review(self.c, self.o), 'REJECT_NAME_MISMATCH')

    def test_wrong_address(self):
        self.o['address'] = '제주시 다른로 2'
        self.assertEqual(gate.review(self.c, self.o), 'REJECT_ADDRESS_MISMATCH')


if __name__ == '__main__':
    unittest.main()
