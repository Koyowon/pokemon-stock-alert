import unittest
from cu_coordinate_plan import validate_candidates

OFFICIAL = {'04766': {'name': '전주효자점', 'address': '전북특별자치도 전주시 완산구 거마평로 203'}}
BASE = {'cu_store_code': '04766', 'name': '전주효자점', 'address': OFFICIAL['04766']['address'],
        'city': '전주', 'lat': 35.8, 'lng': 127.1, 'source_url': 'https://example.org/verified',
        'verified_at': '2026-10-17'}

class CoordinatePlanTests(unittest.TestCase):
    def check(self, change, expected):
        row = {**BASE, **change}
        good, held = validate_candidates(OFFICIAL, [row], {'전주': [(35.81, 127.11)]})
        self.assertEqual(bool(good), expected)
        self.assertEqual(bool(held), not expected)

    def test_valid_record(self): self.check({}, True)
    def test_no_provenance(self): self.check({'source_url': ''}, False)
    def test_wrong_name(self): self.check({'name': '다른점'}, False)
    def test_wrong_city(self): self.check({'city': '아산'}, False)
    def test_unknown_code(self): self.check({'cu_store_code': '00000'}, False)
    def test_invalid_latitude(self): self.check({'lat': 100.0}, False)
    def test_existing_probe(self): self.check({'lat': 35.81, 'lng': 127.11}, False)
    def test_duplicate_code(self):
        good, held = validate_candidates(OFFICIAL, [BASE, BASE], {})
        self.assertEqual(len(good), 1)
        self.assertEqual(len(held), 1)

if __name__ == '__main__': unittest.main()
