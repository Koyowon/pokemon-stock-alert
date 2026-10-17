import unittest
from cu_coordinate_plan import validate_candidates

OFFICIAL = {'04766': {'name': '전주효자점', 'address': '전북특별자치도 전주시 완산구 거마평로 203'}}
BASE = {'cu_store_code': '04766', 'name': '전주효자점', 'address': OFFICIAL['04766']['address'],
        'city': '전주', 'lat': 35.8, 'lng': 127.1, 'source_url': 'https://maps.example.net/store/04766',
        'verified_at': '2026-10-17T17:00:00+09:00'}
BASE['evidence'] = {**{k: BASE[k] for k in ('cu_store_code', 'name', 'address', 'lat', 'lng', 'source_url', 'verified_at')},
                    'reviewed': True, 'snapshot_sha256': 'a' * 64}

class CoordinatePlanTests(unittest.TestCase):
    def check(self, changes, expected):
        row = {**BASE, **changes}
        good, held = validate_candidates(OFFICIAL, [row], {'전주': [(35.81, 127.11)]})
        self.assertEqual(bool(good), expected)
        self.assertEqual(bool(held), not expected)

    def test_reviewed_fixture(self): self.check({}, True)
    def test_missing_url(self): self.check({'source_url': ''}, False)
    def test_placeholder_url(self): self.check({'source_url': 'https://example.org/a'}, False)
    def test_http_url(self): self.check({'source_url': 'http://maps.example.net/a'}, False)
    def test_local_url(self): self.check({'source_url': 'https://localhost/a'}, False)
    def test_url_userinfo(self): self.check({'source_url': 'https://u:p@maps.example.net/a'}, False)
    def test_unreviewed(self): self.check({'evidence': {**BASE['evidence'], 'reviewed': False}}, False)
    def test_missing_snapshot(self): self.check({'evidence': None}, False)
    def test_bad_hash(self): self.check({'evidence': {**BASE['evidence'], 'snapshot_sha256': 'oops'}}, False)
    def test_evidence_coordinate_mismatch(self): self.check({'lat': 35.9}, False)
    def test_evidence_url_mismatch(self): self.check({'source_url': 'https://maps.example.net/other'}, False)
    def test_missing_timezone(self): self.check({'verified_at': '2026-10-17'}, False)
    def test_invalid_timestamp(self): self.check({'verified_at': 'not-a-date'}, False)
    def test_wrong_name(self): self.check({'name': '다른점'}, False)
    def test_wrong_address(self): self.check({'address': '전주시 다른 주소'}, False)
    def test_wrong_city(self): self.check({'city': '아산'}, False)
    def test_unknown_code(self): self.check({'cu_store_code': '00000'}, False)
    def test_invalid_latitude(self): self.check({'lat': 100.0}, False)
    def test_boolean_coordinate(self): self.check({'lat': True}, False)
    def test_existing_probe(self): self.check({'lat': 35.81, 'lng': 127.11}, False)
    def test_duplicate_code(self):
        good, held = validate_candidates(OFFICIAL, [BASE, BASE], {})
        self.assertEqual((len(good), len(held)), (1, 1))
    def test_no_candidates(self):
        self.assertEqual(validate_candidates(OFFICIAL, [], {}), ([], []))

if __name__ == '__main__': unittest.main()
