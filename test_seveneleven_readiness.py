import contextlib
import io
import json
import unittest
import urllib.error
from unittest.mock import patch
import seveneleven_readiness as s


class Response(io.BytesIO):
    status = 200


class ReadinessTests(unittest.TestCase):
    def test_default_mode_never_calls_network(self):
        with patch.object(s, 'open_request', side_effect=AssertionError('network forbidden')) as call, contextlib.redirect_stdout(io.StringIO()) as out:
            s.main([])
        call.assert_not_called()
        result=json.loads(out.getvalue())
        self.assertEqual(result['mode'],'OFFLINE_PLAN')
        self.assertFalse(result['inventory_activation'])

    def test_reviewed_plan_is_only_three_requests(self):
        self.assertEqual(len(s.request_plan()),3)
        self.assertTrue(all(x['path'].startswith('/api/seveneleven/') for x in s.request_plan()))
        with self.assertRaises(ValueError):s.probe([])

    def test_mock_success_is_still_unverified(self):
        with patch.object(s,'open_request',side_effect=lambda *a,**kw:Response(b'{"success":true,"data":{"stockQuantity":0}}')) as call:
            result=s.probe()
        self.assertEqual(call.call_count,3)
        self.assertTrue(all(x['inventory_status']=='UNVERIFIED' for x in result))
        self.assertTrue(all(x['top_level_fields']==['data','success'] for x in result))

    def test_rate_limit_stops_without_retry(self):
        with patch.object(s,'open_request',side_effect=urllib.error.HTTPError('x',429,'limited',{},None)) as call:
            result=s.probe()
        self.assertEqual(call.call_count,1)
        self.assertEqual(result[0]['http_status'],429)
        self.assertEqual(result[0]['inventory_status'],'UNVERIFIED')

    def test_upstream_failure_is_not_zero(self):
        with patch.object(s,'open_request',side_effect=urllib.error.HTTPError('x',502,'upstream',{},None)) as call:
            result=s.probe()
        self.assertEqual(call.call_count,1)
        self.assertNotIn('quantity',result[0])
        self.assertEqual(result[0]['inventory_status'],'UNVERIFIED')

    def test_timeout_stops_without_alternative_route(self):
        with patch.object(s,'open_request',side_effect=TimeoutError()) as call:
            result=s.probe()
        self.assertEqual(call.call_count,1)
        self.assertEqual(result[0]['error'],'TimeoutError')

    def test_oversize_response_stops(self):
        with patch.object(s,'open_request',side_effect=lambda *a,**kw:Response(b'x'*(s.MAX_BODY+1))) as call:
            result=s.probe()
        self.assertEqual(call.call_count,1)
        self.assertEqual(result[0]['error'],'BODY_TOO_LARGE')
        self.assertEqual(result[0]['body_preview'],'')


if __name__=='__main__':unittest.main()
