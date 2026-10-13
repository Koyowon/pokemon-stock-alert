"""Socket tests use only 127.0.0.1, mock sessions, and fake stock callbacks."""
import base64
import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from http_relay import LocalRelayServer
from offline_relay import OfflineRelay, _private_replace

NOW=1800000000
KEY='local-fake-secret-123456789'
def jwt(exp):
    return 'fake.'+base64.urlsafe_b64encode(json.dumps({'exp':exp}).encode()).decode().rstrip('=')+'.sig'

class LocalHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/'session.json'
        _private_replace(self.file,{'accessToken':jwt(NOW+3600),'refreshToken':jwt(NOW+7200),'deviceId':'fake-device'})
        self.calls=[]
        def refresh(_):
            self.calls.append('refresh')
            return {'resultCode':'0000','data':{'access':jwt(NOW+3600),'refresh':jwt(NOW+14400)}}
        def stock(*_):
            self.calls.append('stock')
            return 200, {'stores':[{'storeCode':'FAKE01','storeName':'가상점포','realStockQuantity':'2'}]}
        self.relay=OfflineRelay(self.file,KEY,refresh,stock,now=lambda:NOW)
        self.server=LocalRelayServer(self.relay)
        self.addCleanup(self.server.server_close)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):
        self.server.shutdown();self.thread.join(timeout=3)
    def query(self,path=None,auth=KEY,method='GET',headers=None):
        if path is None: path='/v1/stock?'+urlencode({'item_code':'8800286275732','keyword':'테스트'})
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        try:
            h={'Authorization':'Bearer '+auth}
            if headers: h.update(headers)
            conn.request(method,path,headers=h)
            response=conn.getresponse();return response.status,json.loads(response.read()),dict(response.getheaders())
        finally:conn.close()
    def test_bind_loopback_only(self):
        self.assertEqual(self.server.server_address[0],'127.0.0.1')
        with self.assertRaises(ValueError):LocalRelayServer(self.relay,'0.0.0.0')
        with self.assertRaises(ValueError):LocalRelayServer(self.relay,'::1')
    def test_authorized_stock_adapter(self):
        status,body,headers=self.query()
        self.assertEqual(status,200)
        self.assertEqual(body['data']['inventory']['stores'][0]['realStockQuantity'],2)
        self.assertEqual(headers['Cache-Control'],'no-store')
    def test_wrong_token_no_upstream(self):
        self.assertEqual(self.query(auth='bad')[0],401)
        self.assertEqual(self.calls,[])
    def test_missing_authorization_no_upstream(self):
        self.assertEqual(self.query(headers={'Authorization':''})[0],401)
        self.assertEqual(self.calls,[])
    def test_bad_query_rejected(self):
        for p in ('/v1/stock?item_code=bad&keyword=abc','/v1/stock?item_code=8800286275732&keyword=x&keyword=y','/v1/stock?item_code=8800286275732','/v1/stock?item_code=8800286275732&keyword=x&other=1'):
            with self.subTest(path=p):self.assertEqual(self.query(p)[0],400)
        self.assertEqual(self.calls,[])
    def test_path_and_method_rejected(self):
        self.assertEqual(self.query('/v1/unknown')[0],404)
        self.assertEqual(self.query(method='POST')[0],405)
        self.assertEqual(self.calls,[])
    def test_invalid_host_rejected(self):
        self.assertEqual(self.query(headers={'Host':'example.com'})[0],400)
        self.assertEqual(self.calls,[])
    def test_refresh_failure_safe(self):
        _private_replace(self.file,{'accessToken':jwt(NOW+1),'refreshToken':jwt(NOW+7200),'deviceId':'fake-device'})
        self.relay.fake_refresh=lambda _: {'resultCode':'ERROR'}
        status,body,_=self.query()
        self.assertEqual(status,502);self.assertNotIn('inventory',body)
    def test_stock_failure_safe(self):
        self.relay.fake_stock=lambda *_:(503,{})
        status,body,_=self.query()
        self.assertEqual(status,502);self.assertNotIn('inventory',body)
    def test_bad_stock_shape_safe(self):
        self.relay.fake_stock=lambda *_:(200,{'stores':[{'storeCode':'FAKE01','storeName':'x'}]})
        status,body,_=self.query()
        self.assertEqual(status,502);self.assertNotIn('inventory',body)
if __name__=='__main__':unittest.main()
