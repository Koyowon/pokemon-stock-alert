import copy
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import infernox_preflight as p

class Preflight(unittest.TestCase):
    def sample(self,brand='cu'):
        return {'fixture':False,'source_kind':'relay_response','brand':brand,
                'response_barcode':p.BARCODE,'response_name':'포켓몬)인페르노X',
                'captured_at':'2026-10-22T11:00:00+09:00','sale_unit':'pack',
                'codes':{key:p.BARCODE for key in p.FIELDS[brand]}}
    def test_user_barcode_passes_ean13(self):self.assertTrue(p.valid_ean13(p.BARCODE))
    def test_invalid_barcode_rejected(self):
        for value in ('8800286278529',None,8800286278528,'../8800286278528'):
            self.assertFalse(p.valid_ean13(value))
    def test_no_brand_is_operationally_enabled(self):
        result=p.report();self.assertFalse(result['operationally_enabled'])
        self.assertTrue(all(v=='MISSING_RESPONSE_EVIDENCE' for v in result['brands'].values()))
    def test_each_brand_requires_own_identifiers(self):
        for brand in p.BRANDS:
            sample=self.sample(brand);self.assertEqual(p.identity_check(brand,sample),'IDENTITY_CONSISTENT_STOCK_UNTESTED')
            sample['codes']={};self.assertEqual(p.identity_check(brand,sample),'MISSING_BRAND_IDENTIFIERS')
    def test_fixture_is_never_provider_proof(self):
        sample=self.sample();sample['fixture']=True
        self.assertEqual(p.identity_check('cu',sample),'FIXTURE_OR_UNKNOWN_PROVENANCE')
    def test_shop_listing_is_not_brand_proof(self):
        sample=self.sample();sample['source_kind']='retailer_listing'
        self.assertEqual(p.identity_check('cu',sample),'NOT_A_PROVIDER_RESPONSE')
    def test_wrong_product_rejected(self):
        sample=self.sample();sample['response_barcode']='8800286275732'
        self.assertEqual(p.identity_check('cu',sample),'BARCODE_MISMATCH')
    def test_box_kit_foreign_variants_rejected(self):
        for name in ('인페르노X박스','인페르노X 스페셜 키트','인페르노X 일본어','인페르노X 영문','인페르노X 세트'):
            sample=self.sample();sample['response_name']=name
            self.assertEqual(p.identity_check('cu',sample),'PRODUCT_NAME_OR_VARIANT_MISMATCH')
    def test_unit_must_be_confirmed(self):
        sample=self.sample();sample.pop('sale_unit')
        self.assertEqual(p.identity_check('cu',sample),'SALE_UNIT_UNCONFIRMED')
    def test_wrong_brand_rejected(self):self.assertEqual(p.identity_check('seven',self.sample()),'BRAND_MISMATCH')
    def test_cu_selection_must_match(self):
        sample=self.sample();sample['codes']['stockItemCode']='other'
        self.assertEqual(p.identity_check('cu',sample),'CU_SELECTED_PRODUCT_MISMATCH')
    def test_missing_inventory_does_not_mean_zero(self):self.assertEqual(p.inventory_check('cu',self.sample()),'MISSING_INVENTORY_EVIDENCE')
    def test_stock_identity_and_quantity_gate(self):
        sample=self.sample();sample['inventory']=[{'product_barcode':p.BARCODE,'store_code':'001',
                'name':'테스트점','address':'전주시 테스트로 1','store_identity_verified':True,'quantity':0}]
        self.assertEqual(p.inventory_check('cu',sample),'SUPPLIED_SAMPLE_CONSISTENT_APPROVAL_REQUIRED')
        for qty in (None,-1,True,'0',1.5):
            altered=copy.deepcopy(sample);altered['inventory'][0]['quantity']=qty
            self.assertEqual(p.inventory_check('cu',altered),'UNKNOWN_OR_INVALID_QUANTITY')
    def test_stock_for_30th_cannot_be_inferno_evidence(self):
        sample=self.sample();sample['inventory']=[{'product_barcode':'8800286275732'}]
        self.assertEqual(p.inventory_check('cu',sample),'STOCK_PRODUCT_MISMATCH')
    def test_product_states_are_separate_but_limits_shared(self):
        with tempfile.TemporaryDirectory() as folder:
            a=p.state_paths(folder,p.BARCODE,'cu');b=p.state_paths(folder,'8800286275732','cu')
            self.assertNotEqual(a['stock'],b['stock']);self.assertNotEqual(a['alerts'],b['alerts'])
            self.assertEqual(a['shared_budget'],b['shared_budget']);self.assertEqual(a['brand_hold'],b['brand_hold'])
    def test_same_store_alert_keys_do_not_collide(self):
        self.assertNotEqual(p.product_key(p.BARCODE,'cu','001'),p.product_key('8800286275732','cu','001'))
    def test_report_has_no_network_or_filesystem_side_effects(self):
        with patch('socket.socket',side_effect=AssertionError('network')),patch.object(pathlib.Path,'write_text',side_effect=AssertionError('write')):
            self.assertFalse(p.report()['operationally_enabled'])
    def test_second_product_exceeds_current_budget(self):
        result=p.report();self.assertEqual(result['existing_20min_estimate'],2304)
        self.assertEqual(result['two_products_20min_estimate'],4608)
        self.assertGreater(result['two_products_20min_estimate'],result['cu_gs_daily_budget'])
        self.assertEqual(result['two_products_40min_estimate'],2304)

if __name__=='__main__':unittest.main()
