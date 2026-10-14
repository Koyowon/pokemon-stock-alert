"""Offline snapshot cross-check; no network or operational writes."""
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = '8800286275732'

def read_json(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))

def read_csv(name):
    with (ROOT / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

class RegistryPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = read_json('asan_cu_watch_registry.json')['stores']
        cls.state = read_json('cu_stock_state.json')['stores']
        cls.emart = read_json('stores.json')['stores']
        cls.control = read_json('unified_control.json')
        cls.queue = read_csv('docs/asan_cu_91_manual_approval_queue_20261014.csv')
        cls.review = read_csv('docs/asan_cu_91_evidence_review_20261014.csv')
        cls.unresolved = {x['registry_id']: x for x in cls.registry if not x.get('cu_store_code')}

    def test_candidate_count(self):
        self.assertEqual(len(self.registry), 119)
        self.assertEqual(len(self.unresolved), 91)

    def test_queue_ids_exactly_cover_unresolved(self):
        self.assertEqual({x['registry_id'] for x in self.queue}, set(self.unresolved))
        self.assertEqual(len(self.queue), len(self.unresolved))

    def test_review_ids_exactly_cover_unresolved(self):
        self.assertEqual({x['registry_id'] for x in self.review}, set(self.unresolved))
        self.assertEqual(len(self.review), len(self.unresolved))

    def test_queue_identity_matches_registry(self):
        for row in self.queue:
            ref = self.unresolved[row['registry_id']]
            self.assertEqual((row['name'], row['address']), (ref['name'], ref['address']))

    def test_no_unverified_approval_or_fabricated_evidence(self):
        for row in self.queue:
            self.assertEqual(row['approval_status'], 'BLOCKED_NO_CODE')
            self.assertFalse(row['store_code'])
            self.assertFalse(row['source_url'])
            self.assertFalse(row['observed_at'])
            self.assertEqual(row['barcode'], TARGET)

    def test_review_status_and_identity(self):
        for row in self.review:
            ref = self.unresolved[row['registry_id']]
            self.assertEqual(row['review_status'], 'UNRESOLVED_NO_CODE')
            self.assertFalse(row['cu_store_code'])
            self.assertEqual((row['name'], row['address']), (ref['name'], ref['address']))

    def test_saved_cu_codes_already_assigned(self):
        known = {str(x['cu_store_code']) for x in self.registry if x.get('cu_store_code')}
        saved = {str(k) for k, v in self.state.items() if v.get('city') == '아산'}
        self.assertEqual(len(known), 28)
        self.assertEqual(saved - known, set())

    def test_jeju_fail_closed(self):
        self.assertFalse(self.control['chains']['emart24']['jeju'])
        self.assertFalse(any('제주' in str(v.get('address', '')) for v in self.emart.values()))

    def test_same_address_conflicts_preserved(self):
        for first, second in [('ASAN-CU-008', 'ASAN-CU-089'), ('ASAN-CU-078', 'ASAN-CU-079')]:
            self.assertEqual(self.unresolved[first]['address'], self.unresolved[second]['address'])
            self.assertNotEqual(self.unresolved[first]['name'], self.unresolved[second]['name'])

if __name__ == '__main__':
    unittest.main()
