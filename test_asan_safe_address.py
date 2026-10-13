"""Offline-only regression tests for conservative CU address normalization."""
import unittest
from unittest.mock import patch
import cu_asan_registry as registry

API = {
 '11230': ('온양역점', '충청남도 아산시 시민로 364-33, (온천동)'),
 '33700': ('아산온중점', '충청남도 아산시 온중로 59 (용화동)'),
 '40059': ('아산온양힐스테이트점', '충청남도 아산시 남산로 120 현대홈타운아파트'),
 '53982': ('아산온천타운점', '충청남도 아산시 중앙로 27, (온천동, 가람빌) 1동 1층 101호, 102호'),
}
NEW = {
 '43799': ('아산온양점', '충청남도 아산시 남산로8번길 40-17 (용화동, 그린빌라트) 그린빌라트'),
 '46004': ('아산아람채점', '충청남도 아산시 온천대로 1323-25 (방축동, 아산KD아람채) 아산KD아람채'),
 '49877': ('아산온천동점', '충청남도 아산시 온화로11번길 14, (온천동)'),
 '50619': ('아산CGV점', '충청남도 아산시 온천대로 1538 (온천동)'),
}

class SafeAddressTests(unittest.TestCase):
 def observations(self, items):
  return {code: {'name': name, 'address': address, 'stock': 0} for code,(name,address) in items.items()}
 def test_two_safe_format_matches(self):
  rows=registry.classify_observations(self.observations(API),query_succeeded=True)
  by_id={r['registry_id']:r for r in rows}
  for rid,code in [('ASAN-CU-005','11230'),('ASAN-CU-110','33700')]:
   self.assertEqual(by_id[rid]['observed_store_code'],code)
   self.assertEqual(by_id[rid]['match_method'],'SAFE_FORMAT_NAME_ADDRESS')
 def test_building_details_remain_manual(self):
  rows=registry.classify_observations(self.observations(API),query_succeeded=True)
  by_id={r['registry_id']:r for r in rows}
  for rid in ('ASAN-CU-076','ASAN-CU-046'):
   self.assertEqual(by_id[rid]['status'],'ZERO_STOCK')
   self.assertEqual(by_id[rid]['stock'],0)
 def test_four_new_stores_not_inserted(self):
  rows=registry.classify_observations(self.observations(NEW),query_succeeded=True)
  self.assertEqual(len(rows),123)
  self.assertEqual(sum(bool(r['observed_store_code']) for r in rows),4)
 def test_road_number_difference_blocks(self):
  a=registry.conservative_address_key('충청남도 아산시 시민로 364-33 (온천동)')
  b=registry.conservative_address_key('충청남도 아산시 시민로 364-34, (온천동)')
  self.assertNotEqual(a,b)
 def test_unit_details_not_removed(self):
  a=registry.conservative_address_key('충청남도 아산시 중앙로 27 (온천동)')
  b=registry.conservative_address_key('충청남도 아산시 중앙로 27, (온천동, 가람빌) 1층 101호')
  self.assertNotEqual(a,b)
 def test_duplicate_registry_safe_identity_blocks(self):
  stores=registry.load_registry()
  a=next(s for s in stores if s['registry_id']=='ASAN-CU-005')
  b=next(s for s in stores if s['registry_id']=='ASAN-CU-046')
  b['name']=a['name'];b['address']=a['address']
  with patch.object(registry,'load_registry',return_value=stores):
   rows=registry.classify_observations(self.observations({'11230':API['11230']}),query_succeeded=True)
  self.assertEqual(rows[4]['status'],'NOT_OBSERVED')
 def test_duplicate_api_safe_identity_blocks(self):
  items={'11230':API['11230'],'99999':('온양역점','충청남도 아산시 시민로 364-33 (온천동)')}
  rows=registry.classify_observations(self.observations(items),query_succeeded=True)
  self.assertEqual(rows[4]['status'],'NOT_OBSERVED')
 def test_reserved_code_not_reassigned(self):
  stores=registry.load_registry()
  stores[10]['cu_store_code']='11230'
  with patch.object(registry,'load_registry',return_value=stores):
   rows=registry.classify_observations(self.observations({'11230':API['11230']}),query_succeeded=True)
  self.assertEqual(rows[4]['status'],'NOT_OBSERVED')
if __name__=='__main__':unittest.main()
