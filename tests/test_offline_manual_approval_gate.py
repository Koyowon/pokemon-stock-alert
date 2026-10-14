import unittest
from offline_manual_approval_gate import inspect, BARCODE

class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.registry=[{'registry_id':'A','name':'CU A','address':'충남 아산시 1','cu_store_code':''}]
        self.row={'chain':'cu','registry_id':'A','store_code':'12345','name':'CU A','address':'충남 아산시 1','barcode':BARCODE,'source_url':'https://example.com/store','observed_at':'2026-10-14'}
    def check(self, status, rows=None, used=()):
        out=inspect(rows or [self.row], self.registry, used, ())
        self.assertEqual(out[0]['status'],status)
        self.assertFalse(out[0]['approved'])
    def test_manual_only(self): self.check('MANUAL_REVIEW_REQUIRED')
    def test_missing_code(self): self.row['store_code']=''; self.check('BLOCKED_NO_CODE')
    def test_existing_code(self): self.check('REJECT_DUPLICATE_CODE',used=('12345',))
    def test_duplicate_batch(self): self.check('REJECT_DUPLICATE_CODE',rows=[self.row,self.row])
    def test_duplicate_candidate_distinct_codes(self):
        second = dict(self.row, store_code='54321')
        self.check('REJECT_DUPLICATE_CANDIDATE', rows=[self.row, second])

    def test_duplicate_code_whitespace_normalized(self):
        second = dict(self.row, store_code=' 12345 ')
        self.check('REJECT_DUPLICATE_CODE', rows=[self.row, second])

    def test_wrong_product(self): self.row['barcode']='x'; self.check('REJECT_BARCODE')
    def test_unknown_candidate(self): self.row['registry_id']='X'; self.check('REJECT_UNKNOWN_CANDIDATE')
    def test_mismatch(self): self.row['address']='other'; self.check('REVIEW_IDENTITY_MISMATCH')
    def test_invalid_source(self): self.row['source_url']='http://example.com'; self.check('REJECT_PROVENANCE')
    def test_future_date(self): self.row['observed_at']='2099-01-01'; self.check('REJECT_PROVENANCE')
    def test_jeju_wrong_region(self): self.row.update(chain='emart24',address='서울'); self.check('REJECT_NOT_JEJU')
    def test_spoofed_jeju_substring(self):
        self.row.update(chain='emart24',address='서울특별시 제주시처럼 보이는 거리')
        self.check('REJECT_NOT_JEJU')
    def test_missing_emart_name(self):
        self.row.update(chain='emart24',address='제주시 테스트로 1',name='')
        self.check('REJECT_MISSING_IDENTITY')
    def test_credentialed_evidence_url(self):
        self.row['source_url']='https://user:pass@example.com/store'
        self.check('REJECT_PROVENANCE')
    def test_jeju_review(self): self.row.update(chain='emart24',address='제주특별자치도 제주시 테스트로 1'); self.check('MANUAL_REVIEW_REQUIRED')

if __name__=='__main__': unittest.main()
