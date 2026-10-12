import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from probe import api_query, evaluate, normalized, load_candidates

class FakeResponse:
    status=200
    def __init__(self,data): self.data=data
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,n): return self.data

class ProbeTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalized('GS25 아산 주공점'), '아산주공점')
    def test_valid_api(self):
        doc={'success':True,'data':{'inventory':{'stores':[{'storeCode':'VES44','storeName':'아산주공점','realStockQuantity':2}]}}}
        rows=api_query('아산주공점',opener=lambda req,timeout:FakeResponse(json.dumps(doc).encode()))
        self.assertEqual(len(rows),1)
    def test_api_error(self):
        with self.assertRaises(ValueError):
            api_query('test',opener=lambda req,timeout:FakeResponse(b'{"success":false}'))
    def test_truncation(self):
        doc={'success':True,'data':{'inventory':{'stores':[{}]*100}}}
        with self.assertRaises(ValueError):
            api_query('test',opener=lambda req,timeout:FakeResponse(json.dumps(doc).encode()))
    def test_exact_match_only_and_pending(self):
        candidates={'아산주공점':{'store_name':'아산주공점','address':'아산시 시민로 277-1','ambiguous':False}}
        rows=[{'storeCode':'VES44','storeName':'아산주공점','realStockQuantity':4}, {'storeCode':'V0000','storeName':'아산주공점2','realStockQuantity':1}]
        out=evaluate(rows,candidates,set())
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['approval'],'pending')
        self.assertEqual(out[0]['code_address_verified'],'no')
    def test_exclude_existing(self):
        candidates={'온양사랑점':{'store_name':'온양사랑점','address':'','ambiguous':False}}
        out=evaluate([{'storeCode':'VDQ67','storeName':'온양사랑점','realStockQuantity':0}],candidates,{'VDQ67'})
        self.assertEqual(out[0]['existing_13'],'yes')
    def test_conflict_rejected(self):
        candidates={'온양사랑점':{'store_name':'온양사랑점','address':'','ambiguous':False}}
        with self.assertRaises(ValueError):
            evaluate([{'storeCode':'VDQ67','storeName':'온양사랑점','realStockQuantity':0},{'storeCode':'VDQ67','storeName':'온양사랑점','realStockQuantity':1}],candidates,set())

if __name__=='__main__': unittest.main()
