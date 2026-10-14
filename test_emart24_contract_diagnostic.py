"""Offline contract checks: python -B -m unittest -v test_emart24_contract_diagnostic.py"""
import json
import unittest
from urllib.parse import urlencode
from emart24_contract_diagnostic import BASE_URL, PRODUCT_PLU, Outcome, check_request, check_response

def response(rows):
    return json.dumps({"success": True, "data": {"stores": rows}})

class ContractTests(unittest.TestCase):
    def test_request_matches_monitor(self):
        url = BASE_URL + "?" + urlencode({"pluCd": PRODUCT_PLU, "bizNoArr": "001,002"})
        self.assertEqual(check_request(url, ["001", "002"]).outcome, Outcome.OK)

    def test_wrong_path(self):
        self.assertEqual(check_request(BASE_URL + "/other?pluCd=" + PRODUCT_PLU + "&bizNoArr=001", ["001"]).outcome, Outcome.REQUEST_MISMATCH)

    def test_wrong_product(self):
        self.assertEqual(check_request(BASE_URL + "?pluCd=wrong&bizNoArr=001", ["001"]).outcome, Outcome.REQUEST_MISMATCH)

    def test_wrong_store_order(self):
        self.assertEqual(check_request(BASE_URL + "?pluCd=" + PRODUCT_PLU + "&bizNoArr=002,001", ["001", "002"]).outcome, Outcome.REQUEST_MISMATCH)

    def test_too_many_stores(self):
        self.assertEqual(check_request(BASE_URL + "?pluCd=" + PRODUCT_PLU + "&bizNoArr=001,002,003,004", ["001", "002", "003", "004"]).outcome, Outcome.REQUEST_MISMATCH)

    def test_post_rejected(self):
        self.assertEqual(check_request(BASE_URL + "?pluCd=" + PRODUCT_PLU + "&bizNoArr=001", ["001"], "POST").outcome, Outcome.REQUEST_MISMATCH)

    def test_http_502(self):
        self.assertEqual(check_response(502, "bad gateway", ["001"]).outcome, Outcome.HTTP_502)

    def test_other_http_not_502(self):
        self.assertEqual(check_response(403, "{}", ["001"]).outcome, Outcome.UNKNOWN)

    def test_invalid_json(self):
        self.assertEqual(check_response(200, "{", ["001"]).outcome, Outcome.INVALID_JSON)

    def test_invalid_envelope(self):
        self.assertEqual(check_response(200, '{"success":false}', ["001"]).outcome, Outcome.INVALID_RESPONSE)

    def test_missing_stores_array(self):
        self.assertEqual(check_response(200, '{"success":true,"data":{}}', ["001"]).outcome, Outcome.INVALID_RESPONSE)

    def test_verified_zero_stock(self):
        r = check_response(200, response([{"bizNo":"001","bizQty":0}]), ["001"])
        self.assertEqual((r.outcome,r.verified,r.zero_stock), (Outcome.ZERO_STOCK,1,1))

    def test_positive_stock(self):
        self.assertEqual(check_response(200, response([{"bizNo":"001","bizQty":4}]), ["001"]).outcome, Outcome.OK)

    def test_partial(self):
        r = check_response(200, response([{"bizNo":"001","bizQty":0}]), ["001","002"])
        self.assertEqual((r.outcome,r.verified,r.unknown), (Outcome.PARTIAL,1,1))

    def test_invalid_quantity(self):
        for qty in (True, -1, "0", None):
            with self.subTest(qty=qty):
                self.assertEqual(check_response(200, response([{"bizNo":"001","bizQty":qty}]), ["001"]).outcome, Outcome.UNKNOWN)

    def test_unrelated_store_ignored(self):
        self.assertEqual(check_response(200, response([{"bizNo":"999","bizQty":2}]), ["001"]).outcome, Outcome.UNKNOWN)

if __name__ == "__main__":
    unittest.main()
