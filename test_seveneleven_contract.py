import copy
import json
from pathlib import Path
import unittest
from seveneleven_contract import classify_snapshot, UnverifiedSnapshot

FIXTURES = Path(__file__).parent / 'tests/fixtures/seveneleven_20261017'


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.directory=json.loads((FIXTURES/'namwon_stores.json').read_text())
        self.inventory=json.loads((FIXTURES/'namwon_inventory.json').read_text())

    def test_recorded_city_snapshot_17_identities_12_zero_5_unknown(self):
        rows=classify_snapshot(self.directory,self.inventory,'namwon')
        self.assertEqual(len(rows),17)
        self.assertEqual(sum(x['quantity']==0 for x in rows.values()),12)
        self.assertEqual(sum(x['quantity'] is None for x in rows.values()),5)
        self.assertEqual(rows['59128']['quantity'],0)
        self.assertEqual(rows['68505']['status'],'UNKNOWN')

    def test_jeju_keyword_matches_are_excluded(self):
        rows=classify_snapshot(self.directory,self.inventory,'namwon')
        self.assertNotIn('64303',rows)
        self.assertTrue(all('남원시 ' in x['address'] for x in rows.values()))

    def test_directory_truncation_is_rejected(self):
        directory=json.loads((FIXTURES/'asan_stores_partial.json').read_text())
        with self.assertRaisesRegex(UnverifiedSnapshot,'INCOMPLETE_PAGE'):
            classify_snapshot(directory,self.inventory,'asan')

    def test_inventory_truncation_is_rejected(self):
        self.inventory['data']['inventory']['totalStoreCount']+=1
        with self.assertRaisesRegex(UnverifiedSnapshot,'INCOMPLETE_PAGE'):
            classify_snapshot(self.directory,self.inventory,'namwon')

    def test_product_code_mismatch_rejected(self):
        self.inventory['data']['product']['itemCode']='wrong'
        with self.assertRaisesRegex(UnverifiedSnapshot,'PRODUCT_CODE_MISMATCH'):
            classify_snapshot(self.directory,self.inventory,'namwon')

    def test_product_name_mismatch_rejected(self):
        self.inventory['data']['product']['itemName']='다른 상품'
        with self.assertRaisesRegex(UnverifiedSnapshot,'PRODUCT_NAME_MISMATCH'):
            classify_snapshot(self.directory,self.inventory,'namwon')

    def test_provider_failure_is_not_zero(self):
        with self.assertRaisesRegex(UnverifiedSnapshot,'API_FAILURE'):
            classify_snapshot(self.directory,{'success':False},'namwon')

    def test_stock_error_is_not_zero(self):
        self.inventory['data']['stockError']='upstream failed'
        with self.assertRaisesRegex(UnverifiedSnapshot,'STOCK_UNAVAILABLE'):
            classify_snapshot(self.directory,self.inventory,'namwon')

    def test_negative_null_bool_float_and_string_stay_unknown(self):
        row=self.inventory['data']['inventory']['stores'][0]
        code=row['storeCode']
        for invalid in (-1,None,False,True,0.0,'0'):
            row['stockQuantity']=invalid
            self.assertIsNone(classify_snapshot(self.directory,self.inventory,'namwon')[code]['quantity'])

    def test_numeric_zero_valid(self):
        row=self.inventory['data']['inventory']['stores'][0];row['stockQuantity']=0
        self.assertEqual(classify_snapshot(self.directory,self.inventory,'namwon')[row['storeCode']]['quantity'],0)

    def test_missing_observation_is_unknown(self):
        rows=self.inventory['data']['inventory']['stores'];code=rows.pop()['storeCode']
        self.inventory['data']['inventory']['totalStoreCount']-=1
        self.assertIsNone(classify_snapshot(self.directory,self.inventory,'namwon')[code]['quantity'])

    def test_wrong_address_same_code_is_rejected(self):
        self.inventory['data']['inventory']['stores'][0]['address']='전라북도 남원시 다른로 999'
        with self.assertRaisesRegex(UnverifiedSnapshot,'STORE_IDENTITY_MISMATCH'):
            classify_snapshot(self.directory,self.inventory,'namwon')

    def test_wrong_name_same_code_is_rejected(self):
        self.inventory['data']['inventory']['stores'][0]['storeName']='다른점'
        with self.assertRaisesRegex(UnverifiedSnapshot,'STORE_IDENTITY_MISMATCH'):
            classify_snapshot(self.directory,self.inventory,'namwon')

    def test_duplicate_inventory_code_is_rejected(self):
        block=self.inventory['data']['inventory'];block['stores'].append(copy.deepcopy(block['stores'][0]));block['totalStoreCount']+=1
        with self.assertRaisesRegex(UnverifiedSnapshot,'DUPLICATE_INVENTORY_CODE'):
            classify_snapshot(self.directory,self.inventory,'namwon')

    def test_unsupported_region_rejected(self):
        with self.assertRaisesRegex(UnverifiedSnapshot,'UNSUPPORTED_REGION'):
            classify_snapshot(self.directory,self.inventory,'jeju')


if __name__=='__main__':unittest.main()
