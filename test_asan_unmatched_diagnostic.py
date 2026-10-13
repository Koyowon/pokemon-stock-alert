import unittest
from asan_unmatched_diagnostic import audit_unmatched
from cu_asan_registry import load_registry, classify_observations

class DiagnosticTests(unittest.TestCase):
    def test_unmatched_api_stores_reported_without_linking(self):
        api={'90001':{'name':'CU 이름만같은점','address':'충청남도 아산시 가짜로 1','stock':3}}
        rows=classify_observations(api,query_succeeded=True)
        result=audit_unmatched(api,rows)
        self.assertEqual(result['unmatched_api_store_count'],1)
        self.assertEqual(result['unmatched_api_stores'][0]['code'],'90001')
        self.assertTrue(result['unmatched_api_stores'][0]['diagnostic_only'])
        self.assertEqual(sum(x['not_observed'] for x in result['area_priorities']),123)
    def test_exact_unique_match_excluded(self):
        s=next(x for x in load_registry() if x['registry_id']=='ASAN-CU-066')
        api={'90002':{'name':s['name'],'address':s['address'],'stock':0}}
        rows=classify_observations(api,query_succeeded=True)
        result=audit_unmatched(api,rows)
        self.assertEqual(result['unmatched_api_store_count'],0)
        self.assertEqual(result['matched_registry_count'],1)
    def test_name_only_never_autolinks(self):
        s=next(x for x in load_registry() if x['registry_id']=='ASAN-CU-066')
        api={'90003':{'name':s['name'],'address':'충청남도 아산시 다른로 123','stock':1}}
        rows=classify_observations(api,query_succeeded=True)
        result=audit_unmatched(api,rows)
        self.assertEqual(rows[65]['status'],'NOT_OBSERVED')
        self.assertIn('ASAN-CU-066',result['unmatched_api_stores'][0]['name_only_candidate_ids'])
    def test_address_only_never_autolinks(self):
        s=next(x for x in load_registry() if x['registry_id']=='ASAN-CU-066')
        api={'90004':{'name':'CU 전혀다른점','address':s['address'],'stock':1}}
        rows=classify_observations(api,query_succeeded=True)
        result=audit_unmatched(api,rows)
        self.assertEqual(rows[65]['status'],'NOT_OBSERVED')
        self.assertIn('ASAN-CU-066',result['unmatched_api_stores'][0]['address_only_candidate_ids'])
    def test_invalid_registry_rows_rejected(self):
        with self.assertRaises(ValueError):
            audit_unmatched({},[])
    def test_conflicts_separately_reported(self):
        rows=classify_observations({},query_succeeded=False)
        result=audit_unmatched({},rows,conflicts={'90005'})
        self.assertEqual(result['conflicting_codes'],['90005'])
        self.assertEqual(sum(x['not_queried'] for x in result['area_priorities']),123)
    def test_duplicate_code_not_automatched(self):
        rows=classify_observations({},query_succeeded=True)
        rows[1]['registry_id']=rows[0]['registry_id']
        with self.assertRaises(ValueError):
            audit_unmatched({},rows)

if __name__=='__main__': unittest.main()
