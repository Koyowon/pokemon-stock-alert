import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from seveneleven_watch import run_watch, RelayFailure, save_atomic, main

ROOT=Path(__file__).resolve().parent
FIX=ROOT/'tests/fixtures/seveneleven_20261017'

class WatchTests(unittest.TestCase):
    def setUp(self):
        self.directories=json.loads((ROOT/'data/seveneleven_watch_directory.json').read_text())
        self.payloads={name:json.loads((FIX/file).read_text()) for name,file in {
            'namwon':'namwon_inventory.json','asan':'asan_inventory.json',
            'jeonju':'jeonju_inventory_100.json'}.items()}
        self.cities={'남원시':'namwon','아산시':'asan','전주시':'jeonju'}

    def run_watch(self, fetch, previous=None, now=10000):
        return run_watch(self.directories,previous,fetch,now,monotonic=lambda:0,pause=lambda _:None)

    def fetch(self, keyword):
        if keyword not in self.cities:
            raise RelayFailure('HTTP_502')
        return copy.deepcopy(self.payloads[self.cities[keyword]])

    def test_real_responses_keep_all_251_and_missing_unknown(self):
        result=self.run_watch(self.fetch)
        self.assertEqual(len(result['stores']),251)
        self.assertEqual(result['summary']['jeonju'],{'total':135,'known':6,'unknown':129})
        self.assertIsNone(result['stores']['12792']['quantity'])
        self.assertEqual(len(result['calls']),6)
        self.assertEqual(sum(c['target'] is not None for c in result['calls']),3)

    def test_outage_stops_after_two_and_preserves_registry(self):
        fetch=Mock(side_effect=RelayFailure('HTTP_502'))
        result=self.run_watch(fetch)
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(len(result['stores']),251)
        self.assertTrue(all(r['quantity'] is None for r in result['stores'].values()))
        self.assertTrue(result['halted'])

    def test_terminal_error_stops_after_one(self):
        fetch=Mock(side_effect=RelayFailure('HTTP_429',True))
        self.run_watch(fetch)
        self.assertEqual(fetch.call_count,1)

    def test_last_known_value_survives_failure_but_is_not_current(self):
        old=self.run_watch(self.fetch)
        old['stores']['59128'].update(quantity=7,status='OK',last_known_quantity=7,last_success_at=10000)
        old['cursor']=0
        result=self.run_watch(Mock(side_effect=RelayFailure('HTTP_502')),old,now=12000)
        row=result['stores']['59128']
        self.assertIsNone(row['quantity'])
        self.assertEqual(row['last_known_quantity'],7)
        self.assertEqual(row['last_success_at'],10000)
        self.assertEqual(row['status'],'UNKNOWN')

    def test_unknown_direct_attempts_rotate_and_back_off(self):
        first=self.run_watch(self.fetch)
        targets={r['region']:r['target'] for r in first['calls'] if r['target']}
        second=self.run_watch(self.fetch,first,now=10300)
        for call in second['calls']:
            if call['target']:
                self.assertNotEqual(call['target'],targets[call['region']])
        for code in targets.values():
            self.assertGreater(first['stores'][code]['next_direct_at'],10300)

    def test_single_target_response_does_not_reset_other_city_rows(self):
        def fetch(keyword):
            if keyword in self.cities:return self.fetch(keyword)
            # Return one known, verified row; a target mismatch must stay unknown.
            result=copy.deepcopy(self.payloads['jeonju'])
            result['data']['inventory']['stores']=[result['data']['inventory']['stores'][0]]
            result['data']['inventory']['totalStoreCount']=1
            return result
        state=self.run_watch(fetch)
        self.assertEqual(state['summary']['jeonju']['known'],6)

    def test_bad_product_cannot_create_quantities(self):
        def fetch(keyword):
            result=copy.deepcopy(self.payloads['namwon'])
            result['data']['product']['itemCode']='wrong'
            return result
        result=self.run_watch(fetch)
        self.assertTrue(all(row['quantity'] is None for row in result['stores'].values()))

    def test_elapsed_budget_prevents_calls(self):
        ticks=iter([0,160]);fetch=Mock()
        result=run_watch(self.directories,None,fetch,10000,monotonic=lambda:next(ticks),pause=lambda _:None)
        fetch.assert_not_called();self.assertEqual(result['calls'],[])

    def test_registry_identity_change_is_rejected_without_network(self):
        previous=self.run_watch(self.fetch)
        previous['stores']['59128']['name']='different'
        fetch=Mock()
        with self.assertRaises(ValueError):self.run_watch(fetch,previous)
        fetch.assert_not_called()

    def test_default_cli_never_calls_network_or_writes(self):
        with patch('sys.argv',['seveneleven_watch.py']),patch('seveneleven_watch.fetch_inventory') as fetch,patch('seveneleven_watch.save_atomic') as save,patch('builtins.print'):
            main()
        fetch.assert_not_called();save.assert_not_called()

    def test_atomic_failure_keeps_previous_file_and_removes_temp(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json';path.write_text('previous')
            with patch('seveneleven_watch.os.replace',side_effect=OSError('disk')):
                with self.assertRaises(OSError):save_atomic(path,{'version':1})
            self.assertEqual(path.read_text(),'previous')
            self.assertEqual(list(Path(tmp).iterdir()),[path])


    def test_verified_single_store_recovery_updates_only_that_store(self):
        recovered=[]
        def fetch(keyword):
            if keyword in self.cities:return self.fetch(keyword)
            row=next(r for d in self.directories.values() for r in d['data']['stores'] if r['storeName']==keyword)
            region=next(k for k,d in self.directories.items() if row in d['data']['stores'])
            result=copy.deepcopy(self.payloads[region])
            item=copy.deepcopy(row);item['stockQuantity']=3
            result['data']['inventory']['stores']=[item]
            result['data']['inventory']['totalStoreCount']=1
            recovered.append(row['storeCode'])
            return result
        result=self.run_watch(fetch)
        self.assertEqual(len(recovered),3)
        for code in recovered:
            self.assertEqual(result['stores'][code]['quantity'],3)
            self.assertEqual(result['stores'][code]['status'],'OK')
        self.assertEqual(result['summary']['jeonju']['known'],7)

    def test_stale_unattempted_region_is_unknown_and_region_start_rotates(self):
        previous=self.run_watch(self.fetch)
        previous['cursor']=0
        fetch=Mock(side_effect=RelayFailure('HTTP_429',True))
        result=self.run_watch(fetch,previous,now=12000)
        self.assertTrue(all(r['quantity'] is None for r in result['stores'].values()))
        self.assertEqual(result['cursor'],1)
        again=self.run_watch(fetch,result,now=12300)
        self.assertEqual(again['calls'][0]['region'],'asan')

if __name__=='__main__':unittest.main()
