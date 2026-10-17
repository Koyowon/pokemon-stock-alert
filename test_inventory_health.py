import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import inventory_health as ih
import monitor as em
import cu_stock_monitor as cu
sys.path.insert(0,str(Path(__file__).resolve().parent/'gs25_independent'))
import gs25_auto_monitor as gs

class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.output=contextlib.redirect_stdout(io.StringIO());self.output.__enter__()
        self.net=patch('urllib.request.urlopen',side_effect=AssertionError('Network forbidden'));self.net.start()
    def tearDown(self):
        self.net.stop();self.output.__exit__(None,None,None);self.temp.cleanup()
    def health(self, chain='cu', tick=10000):return ih.Health(chain,self.root,clock=lambda:tick)

    def test_zero_is_known_and_missing_stays_unknown(self):
        h=self.health();h.expect('a','A');h.expect('b','B');h.observe('a',0,'A')
        d=h.finish();self.assertEqual(d['stores']['a']['quantity'],0)
        self.assertEqual(d['stores']['b']['status'],'UNKNOWN');self.assertIsNone(d['stores']['b']['quantity'])
    def test_unknown_keeps_last_success_and_counts_consecutive_runs(self):
        h=self.health();h.observe('a',7,'A');h.finish()
        for tick in [10300,10600]:
            h=self.health(tick=tick);h.expect('a','A');h.finish()
        r=json.loads(h.path.read_text())['stores']['a']
        self.assertEqual(r['last_known_quantity'],7);self.assertEqual(r['last_success_at'],10000)
        self.assertEqual(r['unknown_runs'],2);self.assertEqual(r['first_unknown_at'],10300)
        self.assertIsNone(r['quantity'])
    def test_invalid_quantity_is_never_zero(self):
        h=self.health()
        for i,q in enumerate([-1,True,False,None,'0',0.5]):h.observe(str(i),q,'X')
        self.assertTrue(all(r['quantity'] is None for r in h.finish()['stores'].values()))
    def test_disabled_store_is_preserved(self):
        h=self.health();h.observe('a',0,'A');h.finish()
        d=self.health().finish();self.assertEqual(d['stores']['a']['status'],'DISABLED')
    def test_early_failure_retains_previous_active_as_unknown(self):
        h=self.health();h.observe('a',0,'A');h.finish()
        d=self.health().finish(RuntimeError('offline'))
        self.assertEqual(d['stores']['a']['status'],'UNKNOWN');self.assertEqual(d['errors'],['RuntimeError'])
    def test_conflict_removes_observation_and_recovery_resets_counter(self):
        h=self.health();h.observe('a',7,'A');h.unknown('a','CONFLICT');h.finish()
        h=self.health();h.observe('a',0,'A');r=h.finish()['stores']['a']
        self.assertEqual(r['quantity'],0);self.assertEqual(r['unknown_runs'],0)
        self.assertNotIn('first_unknown_at',r)
    def test_atomic_write_failure_keeps_original(self):
        h=self.health();h.observe('a',0,'A');h.finish();before=h.path.read_bytes()
        with patch('inventory_health.os.replace',side_effect=OSError('disk')):
            with self.assertRaises(OSError):h.finish()
        self.assertEqual(h.path.read_bytes(),before);self.assertFalse(list(self.root.glob('*.tmp')))
    def test_emart_alert_failure_health_still_records_query_without_advancing_baseline(self):
        h=self.health('emart24');stores={'1':{'name':'A','address':'전북특별자치도 남원시 도통로 1'},'2':{'name':'B','address':'전북특별자치도 남원시 도통로 2'}}
        with patch('unified_settings.enabled',return_value={'namwon'}),patch.object(em,'load_enabled_regions',return_value={'namwon'}),patch.object(em,'get_stores',return_value=stores),patch.object(em,'read_json',return_value={}),patch.object(em,'stock',return_value=({'1':3},{'1':'OK','2':'MISSING_IN_RESPONSE'})),patch.object(em,'notify',return_value=False),patch.object(em,'save_json') as save:
            em.run_monitor(h)
        d=h.finish();self.assertEqual(d['stores']['1']['quantity'],3);self.assertIsNone(d['stores']['2']['quantity'])
        self.assertEqual(save.call_args.args[1],{})
    def test_cu_total_failure_records_official_registry_without_sending_or_saving_stock(self):
        h=self.health()
        with patch('unified_settings.enabled',return_value={'namwon','asan','jeonju'}),patch.object(cu,'load_enabled_regions',return_value={'namwon'}),patch.object(cu,'load_state',return_value={'stores':{}}),patch.object(cu,'query',side_effect=RuntimeError('offline')),patch.object(cu,'telegram') as tel,patch.object(cu,'save_state') as save,patch('cu_asan_registry.summarize_observations'):
            with self.assertRaises(RuntimeError):cu.run_monitor(h)
        data=h.finish(RuntimeError());self.assertEqual(len(data['stores']),377)
        self.assertEqual(data['summary']['UNKNOWN'],377);tel.assert_not_called();save.assert_not_called()
    def test_gs_partial_scan_never_makes_old_quantity_current(self):
        h=self.health('gs25');config=self.root/'config.json';state=self.root/'gs.json'
        config.write_text(json.dumps({'provider':'GS25','item_code':'8800286275732','regions':[{'id':'namwon','name':'남원','enabled':True}]}))
        state.write_text(json.dumps({'version':2,'item_code':'8800286275732','regions':{'namwon':{'stores':{'A':{'name':'A','quantity':7},'B':{'name':'B','quantity':0}}}}}))
        before=state.read_bytes()
        with patch.object(gs,'CONFIG',config),patch.object(gs,'STATE',state),patch('unified_settings.enabled',return_value={'namwon'}),patch.object(gs,'KEYWORDS',{'namwon':['남원']}),patch.object(gs,'api_query',side_effect=RuntimeError('offline')),patch.object(gs,'telegram') as tel:
            self.assertEqual(gs.run_monitor(h),1)
        d=h.finish();self.assertEqual(d['summary']['UNKNOWN'],2)
        self.assertTrue(all(r['quantity'] is None for r in d['stores'].values()))
        self.assertEqual(state.read_bytes(),before);tel.assert_not_called()


    def test_corrupt_health_file_does_not_block_monitor(self):
        (self.root/'cu_inventory_health.json').write_text('broken')
        h=self.health();h.observe('a',0,'A')
        self.assertIn('PREVIOUS_HEALTH_INVALID',h.finish()['errors'])

    def test_health_save_failure_preserves_monitor_return_value(self):
        with patch('inventory_health.Health') as cls:
            cls.return_value.finish.side_effect=OSError('disk')
            self.assertEqual(ih.monitor_with_health('cu',lambda health: 7),7)

    def test_cu_observation_can_be_known_zero_with_other_directory_rows_unknown(self):
        h=self.health()
        directory=json.loads(Path(cu.__file__).with_name('cu_official_verified_directory.json').read_text())
        row=next(r for r in directory['stores'] if ih.region_of(r['address'])=='namwon')
        item={'code':row['cu_store_code'],'name':row['name'],'address':row['address'],'city':'남원','stock':0}
        with patch('unified_settings.enabled',return_value={'namwon'}),patch.object(cu,'load_enabled_regions',return_value={'namwon'}),patch.object(cu,'load_state',return_value={'stores':{}}),patch.object(cu,'POINTS',{'남원':[(0,0)]}),patch.object(cu,'query',return_value=[item]),patch.object(cu,'save_state'),patch.object(cu,'telegram') as tel:
            cu.run_monitor(h)
        data=h.finish();self.assertEqual(data['summary']['OK'],1)
        self.assertEqual(data['stores'][row['cu_store_code']]['quantity'],0);tel.assert_not_called()

    def test_gs_complete_scan_marks_missing_prior_store_unknown(self):
        h=self.health('gs25');config=self.root/'config.json';state=self.root/'gs.json'
        config.write_text(json.dumps({'provider':'GS25','item_code':'8800286275732','regions':[{'id':'namwon','name':'남원','enabled':True}]}))
        state.write_text(json.dumps({'version':2,'item_code':'8800286275732','regions':{'namwon':{'stores':{'A':{'name':'A','quantity':0},'B':{'name':'B','quantity':7}}}}}))
        with patch.object(gs,'CONFIG',config),patch.object(gs,'STATE',state),patch('unified_settings.enabled',return_value={'namwon'}),patch.object(gs,'KEYWORDS',{'namwon':['남원']}),patch.object(gs,'api_query',return_value=[{'storeCode':'A','storeName':'A','realStockQuantity':0}]),patch.object(gs,'telegram') as tel:
            self.assertEqual(gs.run_monitor(h),0)
        data=h.finish();self.assertEqual(data['stores']['A']['quantity'],0)
        self.assertIsNone(data['stores']['B']['quantity'])
        self.assertEqual(json.loads(state.read_text())['regions']['namwon']['stores']['B']['quantity'],7)
        tel.assert_not_called()

if __name__=='__main__':unittest.main()
