"""Offline tests: synthetic data only; no network or writes."""
import unittest
from asan_registry_quality import audit, baseline_ok, normalized_address, BARCODE

def fixture():
    stores = []
    for n in range(123):
        stores.append({'registry_id': f'ASAN-CU-{n+1:03}', 'name': f'CU 테스트{n}',
                       'address': f'충청남도 아산시 테스트로 {n}',
                       'area': '주소 미확인' if n < 17 else ('' if n < 23 else '배방읍'),
                       'cu_store_code': str(20000+n) if n < 34 else '',
                       'latitude': '36.7' if n < 3 else '',
                       'longitude': '127.0' if n < 3 else '',
                       'product_barcode': BARCODE})
    stores[121]['address'] = stores[120]['address']
    stores[122]['address'] = stores[119]['address']
    return {'product_barcode': BARCODE, 'stores': stores}

class RegistryQualityTests(unittest.TestCase):
    def test_baseline(self): self.assertTrue(baseline_ok(audit(fixture())))
    def test_total_and_ids(self):
        r = audit(fixture()); self.assertEqual((r['total'], r['unique_ids']), (123,123))
    def test_codes(self):
        r = audit(fixture()); self.assertEqual((r['coded'],r['uncoded']), (34,89))
    def test_coordinates(self):
        r = audit(fixture()); self.assertEqual((r['coordinates_present'],r['coordinates_missing']), (3,120))
    def test_duplicate_addresses(self): self.assertEqual(len(audit(fixture())['duplicate_addresses']),2)
    def test_unknown_area(self): self.assertEqual(audit(fixture())['unknown_area'],23)
    def test_normalization(self):
        self.assertEqual(normalized_address('충남 아산시 테스트로 1'), normalized_address('충청남도 아산시 테스트로 1'))
    def test_duplicate_code_rejected(self):
        d=fixture(); d['stores'][1]['cu_store_code']=d['stores'][0]['cu_store_code']; self.assertFalse(baseline_ok(audit(d)))
    def test_duplicate_id_rejected(self):
        d=fixture(); d['stores'][1]['registry_id']=d['stores'][0]['registry_id']; self.assertFalse(baseline_ok(audit(d)))
    def test_invalid_coordinates_rejected(self):
        d=fixture(); d['stores'][3]['latitude']='999'; d['stores'][3]['longitude']='127'; self.assertFalse(baseline_ok(audit(d)))
    def test_partial_coordinates_rejected(self):
        d=fixture(); d['stores'][3]['latitude']='36'; self.assertFalse(baseline_ok(audit(d)))
    def test_wrong_barcode_rejected(self):
        d=fixture(); d['stores'][0]['product_barcode']='wrong'; self.assertFalse(baseline_ok(audit(d)))

if __name__=='__main__': unittest.main()
