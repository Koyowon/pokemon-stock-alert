"""Integration tests against local snapshot; no operational writes."""
import csv
import tempfile
import unittest
from pathlib import Path
from offline_evidence_preflight_cli import check

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ['chain','registry_id','store_code','name','address','source_url','observed_at','barcode']

class EvidencePreflightCLITests(unittest.TestCase):
    def run_rows(self, rows):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'evidence.csv'
            with p.open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            return check(ROOT,p)

    def test_empty_template_stays_unapproved(self):
        self.assertEqual(self.run_rows([]), {'rows':0,'manual_review':0,'blocked':0,'approved':0,'results':[]})

    def test_real_candidate_without_code_is_blocked(self):
        row={'chain':'cu','registry_id':'ASAN-CU-001','store_code':'',
             'name':'씨유아산둔포원룸점','address':'충청남도 아산시 둔포면 둔포로 78',
             'source_url':'','observed_at':'','barcode':'8800286275732'}
        out=self.run_rows([row])
        self.assertEqual((out['rows'],out['blocked'],out['approved']),(1,1,0))
        self.assertEqual(out['results'][0]['status'],'BLOCKED_NO_CODE')

    def test_jeju_without_code_is_blocked(self):
        row={'chain':'emart24','registry_id':'','store_code':'',
             'name':'테스트용가상점포','address':'제주특별자치도 제주시 테스트로 1',
             'source_url':'','observed_at':'','barcode':'8800286275732'}
        out=self.run_rows([row])
        self.assertEqual(out['results'][0]['status'],'BLOCKED_NO_CODE')
        self.assertEqual(out['approved'],0)

if __name__ == '__main__':
    unittest.main()
