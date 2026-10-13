"""Network-free tests for the explicit opt-in Asan observation probe."""
import unittest
from asan_live_observation import observe
from cu_stock_monitor import BARCODE

def classifier(observed, *, query_succeeded=False):
    return [{"registry_id": f"ASAN-CU-{i+1:03}",
             "status": "IN_STOCK" if i == 0 and observed else
                       ("NOT_OBSERVED" if query_succeeded else "NOT_QUERIED"),
             "stock": 2 if i == 0 and observed else None}
            for i in range(123)]

def item(stock=2):
    return {"code":"101", "name":"CU 시험점", "address":"충청남도 아산시 시험로 1",
            "stock":stock, "city":"아산"}

class ObservationTests(unittest.TestCase):
    def test_all_123_preserved(self):
        r=observe([(36.7,127.0)],lambda *args:[item()],classifier)
        self.assertEqual(r["candidate_count"],123)
        self.assertEqual(len(r["candidates"]),123)
        self.assertEqual(r["barcode"],BARCODE)
    def test_deduplicate_coordinates(self):
        calls=[]
        def query(*args):
            calls.append(args); return [item()]
        r=observe([(36.7,127.0)]*3,query,classifier)
        self.assertEqual(len(calls),1)
        self.assertEqual(r["query_successes"],1)
    def test_failed_query_unknown_not_zero(self):
        def failure(*args): raise TimeoutError()
        r=observe([(36.7,127.0)],failure,classifier)
        self.assertEqual(r["query_successes"],0)
        self.assertEqual(r["candidates"][0]["status"],"NOT_QUERIED")
        self.assertEqual(r["candidates"][0]["stock"],None)
    def test_conflicting_stock_held(self):
        calls=[[item(2)],[item(5)]]
        r=observe([(36.7,127.0),(36.8,127.1)],lambda *args:calls.pop(0),classifier)
        self.assertEqual(r["conflicting_codes"],["101"])
        self.assertEqual(r["candidates"][0]["status"],"NOT_OBSERVED")
    def test_partial_failure_keeps_observation(self):
        def query(city,lat,lng):
            if lat==36.8: raise TimeoutError()
            return [item()]
        r=observe([(36.7,127.0),(36.8,127.1)],query,classifier)
        self.assertEqual((r["query_successes"],r["query_failures"]),(1,1))
        self.assertEqual(r["candidates"][0]["status"],"IN_STOCK")
    def test_reject_incomplete_registry(self):
        with self.assertRaises(ValueError):
            observe([(36.7,127.0)],lambda *args:[],lambda *args,**kwargs:[])
if __name__=="__main__":
    unittest.main()
