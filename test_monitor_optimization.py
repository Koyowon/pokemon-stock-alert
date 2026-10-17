"""Offline regression and deterministic latency tests. No external network allowed."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / 'gs25_independent'))
import monitor as em
spec = importlib.util.spec_from_file_location('emart24_baseline', ROOT / 'tests/fixtures/emart24_monitor_baseline.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
import cu_stock_monitor as cu
import cu_registration_monitor as reg
import gs25_auto_monitor as gs
import unified_settings
from request_pacing import RequestPacer


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Response(io.BytesIO):
    status = 200


def simulate(module, count=183, latency=0.7, fail=False):
    clock = Clock()
    calls = []
    def urlopen(req, timeout):
        clock.now += 15 if fail else latency
        calls.append(req.full_url)
        if fail:
            raise urllib.error.URLError('offline outage')
        args = urllib.parse.parse_qs(urllib.parse.urlsplit(req.full_url).query)
        rows = [{'bizNo': c, 'bizQty': 0} for c in args['bizNoArr'][0].split(',')]
        return Response(json.dumps({'success': True, 'data': {'stores': rows}}).encode())
    em.INVENTORY_PACER = RequestPacer(1.5)
    codes = [str(i).zfill(5) for i in range(count)]
    with patch('time.monotonic', side_effect=lambda: clock.now), patch('time.sleep', side_effect=clock.sleep), patch('urllib.request.urlopen', side_effect=urlopen):
        values, statuses = module.stock('8800286275732', codes)
    return clock.now, calls, values, statuses


class OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.net = patch('urllib.request.urlopen', side_effect=AssertionError('real network forbidden'))
        cls.net.start()

    @classmethod
    def tearDownClass(cls):
        cls.net.stop()

    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()

    def tearDown(self):
        self.output.__exit__(None, None, None)

    def test_success_latency_improves_same_183_results(self):
        before, bc, bv, bs = simulate(old)
        after, ac, av, ass = simulate(em)
        self.assertEqual(len(ac), 61)
        self.assertEqual(ac, bc)
        self.assertEqual(av, bv)
        self.assertEqual(ass, bs)
        self.assertAlmostEqual(before, 134.2)
        self.assertAlmostEqual(after, 90.7)

    def test_slow_responses_do_not_add_fixed_sleep(self):
        before, _, bv, _ = simulate(old, latency=2)
        after, _, av, _ = simulate(em, latency=2)
        self.assertEqual(av, bv)
        self.assertAlmostEqual(before - after, 91.5)

    def test_outage_skips_six_pointless_single_probes(self):
        before, bc, _, _ = simulate(old, fail=True)
        after, ac, values, statuses = simulate(em, fail=True)
        self.assertEqual(len(bc), 12)
        self.assertEqual(len(ac), 6)
        self.assertEqual(values, {})
        self.assertEqual(statuses['00020'], 'NOT_CHECKED')
        self.assertLess(after, before)
        self.assertAlmostEqual(after, 99)

    def test_inventory_rate_limit_stops_whole_scan(self):
        error = urllib.error.HTTPError('https://example.invalid', 429, 'limited', {}, None)
        with patch.object(em.urllib.request, 'urlopen', side_effect=error) as call, patch('time.sleep'):
            values, statuses = em.stock('p', ['00001', '00002', '00003', '00004'])
        self.assertEqual(call.call_count, 1)
        self.assertEqual(values, {})
        self.assertEqual(statuses['00001'], 'HTTP_BLOCKED')
        self.assertEqual(statuses['00004'], 'NOT_CHECKED')

    def test_partial_batch_failure_recovers_only_failed_codes(self):
        calls = []
        def api(path, params, attempts):
            codes = params['bizNoArr'].split(',')
            calls.append(codes)
            if len(codes) == 3 and codes[0] == '00001':
                raise RuntimeError('partial failure')
            return {'stores': [{'bizNo': c, 'bizQty': 0} for c in codes]}
        with patch.object(em, 'api', side_effect=api), patch('time.sleep'):
            values, statuses = em.stock('p', ['00001','00002','00003','00004'])
        self.assertEqual(len(values), 4)
        self.assertEqual(len(calls), 5)
        self.assertTrue(all(s == 'OK' for s in statuses.values()))

    def test_duplicates_do_not_add_requests(self):
        with patch.object(em, 'api', return_value={'stores': []}) as call:
            _, statuses = em.stock('p', ['00001'] * 20)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(statuses, {'00001':'MISSING_IN_RESPONSE'})

    def test_invalid_or_absent_is_not_zero(self):
        with patch.object(em, 'api', return_value={'stores': [{'bizNo':'00001','bizQty':None}, {'bizNo':'00002','bizQty':False}]}):
            values, statuses = em.stock('p', ['00001','00002','00003'])
        self.assertEqual(values, {})
        self.assertEqual(statuses['00003'], 'MISSING_IN_RESPONSE')

    def test_fallbacks_remain_bounded(self):
        n = 0
        def api(path, params, attempts):
            nonlocal n
            codes = params['bizNoArr'].split(',')
            if len(codes) == 1:
                n += 1
                raise RuntimeError('single failed')
            if int(codes[0]) % 6 == 0:
                raise RuntimeError('batch failed')
            return {'stores': []}
        with patch.object(em,'api',side_effect=api), patch('time.sleep'):
            em.stock('p',[str(i).zfill(5) for i in range(36)])
        self.assertEqual(n,6)

    def test_failed_directory_refresh_has_cooldown_and_keeps_all_codes(self):
        cache = json.loads((ROOT / 'stores.json').read_text())
        cache['last_refresh'] = '2000-01-01T00:00:00+00:00'
        seed = json.loads((ROOT / 'emart24_jeonju_seed.json').read_text())
        def read(path, default):
            return cache if path.name == 'stores.json' else seed
        def save(path, value):
            cache.clear(); cache.update(value)
        with patch.object(em,'read_json',side_effect=read), patch.object(em,'save_json',side_effect=save), patch.object(em,'api',side_effect=RuntimeError('offline')) as call, patch('time.sleep'):
            one = em.get_stores({'남원':'남원시','아산':'아산시','전주':'전주시'})
            two = em.get_stores({'남원':'남원시','아산':'아산시','전주':'전주시'})
        self.assertEqual(len(one),183)
        self.assertEqual(one,two)
        self.assertEqual(call.call_count,2)
        self.assertEqual(cache['last_refresh'],'2000-01-01T00:00:00+00:00')

    def test_emart_alert_failure_preserves_old_and_unknown(self):
        stores={'00001':{'name':'A','address':'충청남도 아산시 길 1'},'00002':{'name':'B','address':'충청남도 아산시 길 2'}}
        previous={'이마트24|00001|8800286275732':3,'이마트24|00002|8800286275732':4}
        with patch.object(unified_settings,'enabled',return_value={'asan'}),patch.object(em,'load_enabled_regions',return_value={'asan'}),patch.object(em,'get_stores',return_value=stores),patch.object(em,'read_json',return_value=copy.deepcopy(previous)),patch.object(em,'stock',return_value=({'00001':0},{})),patch.object(em,'notify',return_value=False) as notify,patch.object(em,'save_json') as save:
            em.main()
        self.assertEqual(notify.call_count,1)
        self.assertEqual(save.call_args.args[1],previous)

    def cu_run(self, query, points=None, state=None):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(unified_settings,'enabled',return_value={'namwon'}))
            stack.enter_context(patch.object(cu,'load_enabled_regions',return_value={'namwon'}))
            stack.enter_context(patch.object(cu,'load_state',return_value=copy.deepcopy(state or {'stores':{}})))
            stack.enter_context(patch.object(cu,'POINTS',points or {'남원':[(1,i) for i in range(10)]}))
            q=stack.enter_context(patch.object(cu,'query',side_effect=query))
            save=stack.enter_context(patch.object(cu,'save_state'))
            tel=stack.enter_context(patch.object(cu,'telegram',return_value=False))
            try:
                cu.main()
            except RuntimeError:
                pass
            return q,save,tel

    def test_cu_three_failures_stop_without_state_write(self):
        q,save,tel=self.cu_run(RuntimeError('offline'))
        self.assertEqual(q.call_count,3);save.assert_not_called();tel.assert_not_called()

    def test_cu_429_stops_after_one(self):
        q,save,tel=self.cu_run(urllib.error.HTTPError('x',429,'limited',{},None))
        self.assertEqual(q.call_count,1);save.assert_not_called()

    def test_cu_deduplicates_points_and_keeps_zero(self):
        item={'code':'001','city':'남원','name':'A','address':'전북특별자치도 남원시 요천로 1','stock':0}
        q,save,tel=self.cu_run(lambda *a:[item],{'남원':[(1,1),(1,1)]})
        self.assertEqual(q.call_count,1)
        self.assertEqual(save.call_args.args[0]['stores']['001']['stock'],0)
        tel.assert_not_called()

    def test_cu_conflict_is_not_committed(self):
        item={'code':'001','city':'남원','name':'A','address':'전북특별자치도 남원시 요천로 1','stock':0}
        q,save,tel=self.cu_run([[item],[dict(item,stock=2)]],{'남원':[(1,1),(1,2)]})
        self.assertEqual(save.call_args.args[0],{'stores':{}});tel.assert_not_called()

    def test_cu_alert_failure_does_not_advance(self):
        item={'code':'001','city':'남원','name':'A','address':'전북특별자치도 남원시 요천로 1','stock':2}
        q,save,tel=self.cu_run(lambda *a:[item],{'남원':[(1,1)]})
        self.assertEqual(save.call_args.args[0],{'stores':{}})
        self.assertEqual(tel.call_count,1)

    def test_registration_circuit_preserves_state(self):
        with patch.object(reg,'load_state',return_value={'notified':{}}),patch.object(reg,'get_page',side_effect=RuntimeError('offline')) as q,patch.object(reg,'save_state') as save,patch.object(reg,'telegram') as tel,patch('time.sleep'):
            with self.assertRaises(RuntimeError):reg.main()
        self.assertEqual(q.call_count,3);save.assert_not_called();tel.assert_not_called()

    def test_registration_429_stops_immediately(self):
        with patch.object(reg,'load_state',return_value={'notified':{}}),patch.object(reg,'get_page',side_effect=urllib.error.HTTPError('x',429,'limited',{},None)) as q,patch.object(reg,'save_state') as save,patch('time.sleep'):
            with self.assertRaises(RuntimeError):reg.main()
        self.assertEqual(q.call_count,1);save.assert_not_called()

    def test_gs25_rate_limit_no_retry(self):
        with patch('urllib.request.urlopen',side_effect=urllib.error.HTTPError('x',429,'limited',{},None)) as q,patch('time.sleep') as sleep:
            with self.assertRaises(gs.ProviderBlocked):gs.api_query('12345678','남원')
        self.assertEqual(q.call_count,1);sleep.assert_not_called()

    def gs_run(self, query, previous):
        cfg={'provider':'GS25','item_code':'12345678','regions':[{'id':'namwon','name':'남원','enabled':True},{'id':'jeonju','name':'전주','enabled':True}]}
        class File:
            name='mock_state'
            def exists(self):return True
            def read_text(self,**kw):return json.dumps(previous)
            def write_text(self,*args,**kw):pass
        state=File()
        with patch.object(gs,'CONFIG') as config,patch.object(gs,'STATE',state),patch.object(unified_settings,'enabled',return_value={'namwon','jeonju'}),patch.object(gs,'api_query',side_effect=query) as q,patch.object(state,'write_text') as write,patch.object(gs,'telegram',side_effect=RuntimeError('offline notification')) as tel:
            config.read_text.return_value=json.dumps(cfg)
            status=gs.main()
        return status,q,write,tel

    def test_gs_total_failure_keeps_state_no_alert(self):
        previous={'item_code':'12345678','regions':{'namwon':{'stores':{'1':{'name':'A','quantity':2}}}}}
        status,q,write,tel=self.gs_run(RuntimeError('offline'),previous)
        self.assertEqual(status,1);self.assertEqual(q.call_count,3);write.assert_not_called();tel.assert_not_called()

    def test_gs_terminal_failure_keeps_unscanned_regions(self):
        status,q,write,tel=self.gs_run(gs.ProviderBlocked('HTTP 403'),{'item_code':'12345678','regions':{}})
        self.assertEqual(q.call_count,1);write.assert_not_called();tel.assert_not_called()

    def test_gs_unknown_does_not_become_zero(self):
        previous={'item_code':'12345678','regions':{'namwon':{'stores':{'1':{'name':'A','quantity':2}}}}}
        status,q,write,tel=self.gs_run(lambda *a:[],previous)
        saved=json.loads(write.call_args.args[0])
        self.assertEqual(saved['regions']['namwon']['stores']['1']['quantity'],2);tel.assert_not_called()

    def test_gs_failed_notification_preserves_quantity(self):
        previous={'item_code':'12345678','regions':{'namwon':{'stores':{'1':{'name':'A','quantity':2}}}}}
        status,q,write,tel=self.gs_run(lambda code,term:[{'storeCode':'1','storeName':'A','realStockQuantity':0}],previous)
        saved=json.loads(write.call_args.args[0])
        self.assertEqual(saved['regions']['namwon']['stores']['1']['quantity'],2)
        self.assertEqual(tel.call_count,1)

    def test_pacer_minimum_gap_without_trailing_sleep(self):
        c=Clock();p=RequestPacer(1.5)
        with patch('time.monotonic',side_effect=lambda:c.now),patch('time.sleep',side_effect=c.sleep):
            p.wait();c.now+=0.5;p.wait()
        self.assertEqual(c.sleeps,[1.0]);self.assertEqual(c.now,1.5)

    def test_pacer_rejects_negative_interval(self):
        with self.assertRaises(ValueError):RequestPacer(-1)

    def test_emart_all_regions_disabled_calls_nothing(self):
        with patch.object(unified_settings,'enabled',return_value=set()),patch.object(em,'load_enabled_regions',return_value=set()),patch.object(em,'get_stores') as stores,patch.object(em,'stock') as stock,patch.object(em,'save_json') as save:
            em.main()
        stores.assert_not_called();stock.assert_not_called();save.assert_not_called()

    def test_cu_all_regions_disabled_calls_nothing(self):
        with patch.object(unified_settings,'enabled',return_value=set()),patch.object(cu,'load_enabled_regions',return_value=set()),patch.object(cu,'load_state',return_value={'stores':{}}),patch.object(cu,'query') as q,patch.object(cu,'save_state') as save:
            cu.main()
        q.assert_not_called();save.assert_not_called()

    def test_gs_all_regions_disabled_calls_nothing(self):
        with patch.object(gs,'CONFIG') as cfg,patch.object(unified_settings,'enabled',return_value=set()),patch.object(gs,'api_query') as q,patch.object(gs,'telegram') as tel:
            cfg.read_text.return_value=json.dumps({'provider':'GS25','item_code':'12345678','regions':[]})
            self.assertEqual(gs.main(),0)
        q.assert_not_called();tel.assert_not_called()

    def test_emart_terminal_single_probe_stops_remaining(self):
        def api(path,params,attempts):
            codes=params['bizNoArr'].split(',')
            if codes==['00001','00002','00003']:raise RuntimeError('bad batch')
            if len(codes)==1 and codes[0]=='00001':raise em.InventoryRequestBlocked('HTTP 429')
            return {'stores':[]}
        with patch.object(em,'api',side_effect=api) as q,patch('time.sleep'):
            values,statuses=em.stock('p',['00001','00002','00003','00004'])
        self.assertEqual(q.call_count,3)
        self.assertEqual(statuses['00001'],'HTTP_BLOCKED')
        self.assertEqual(statuses['00002'],'BATCH_ERROR')

    def test_success_after_failures_resets_cu_circuit(self):
        # Six isolated errors separated by a valid empty response are not an outage.
        sequence=[RuntimeError('one'),RuntimeError('two'),[]]*3
        q,save,tel=self.cu_run(sequence,{'남원':[(1,i) for i in range(9)]})
        self.assertEqual(q.call_count,9);self.assertEqual(save.call_count,1)

    def test_successful_registration_alert_deduplicated(self):
        product={'itemCode':reg.BARCODE,'itemName':'포켓몬30주년카드'}
        with patch.object(reg,'load_state',return_value={'notified':{}}),patch.object(reg,'get_page',return_value=([product],1)),patch.object(reg,'save_state') as save,patch.object(reg,'telegram',return_value=True) as tel,patch('time.sleep'):
            reg.main()
        self.assertEqual(tel.call_count,1);self.assertEqual(save.call_count,1)


if __name__=='__main__':
    unittest.main()
