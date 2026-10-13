"""Offline socket security tests: loopback only; all credentials and callbacks fake."""
import base64
import concurrent.futures
import http.client
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode
from http_relay import LocalRelayServer, CLIENT_TIMEOUT
from offline_relay import OfflineRelay, _private_replace

NOW=1800000000
KEY='fake-local-only-token-123456789'

def jwt(exp):
    return 'fake.' + base64.urlsafe_b64encode(json.dumps({'exp':exp}).encode()).decode().rstrip('=') + '.sig'

class HTTPHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/'session.json'
        _private_replace(self.file,{'accessToken':jwt(NOW+3600),'refreshToken':jwt(NOW+7200),'deviceId':'fake-device'})
        self.calls=[]
        def stock(*_):
            self.calls.append('stock')
            return 200,{'stores':[{'storeCode':'FAKE01','storeName':'가상점포','realStockQuantity':'2'}]}
        self.relay=OfflineRelay(self.file,KEY,lambda _: {'resultCode':'0000','data':{'access':jwt(NOW+3600),'refresh':jwt(NOW+7200)}},stock,now=lambda:NOW)
        self.server=LocalRelayServer(self.relay)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):
        if self.thread.is_alive():
            self.server.shutdown();self.thread.join(timeout=3)
        self.server.server_close()
    def query(self,auth=KEY,path=None,headers=None):
        path=path or '/v1/stock?'+urlencode({'item_code':'8800286275732','keyword':'테스트'})
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=2)
        try:
            h={'Authorization':'Bearer '+auth}
            if headers:h.update(headers)
            conn.request('GET',path,headers=h)
            resp=conn.getresponse()
            return resp.status,resp.read().decode(),dict(resp.getheaders())
        finally:conn.close()
    def test_concurrent_20_requests(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            results=list(pool.map(lambda _:self.query(),range(20)))
        self.assertTrue(all(s==200 for s,_,_ in results),results)
        self.assertEqual(len(self.calls),20)
    def test_no_token_in_response_or_headers(self):
        for auth in (KEY,'invalid','Bearer '+KEY):
            status,body,headers=self.query(auth=auth)
            self.assertNotIn(KEY,body)
            self.assertNotIn(KEY,str(headers))
            self.assertNotIn('fake.',body)
        self.assertEqual(status,401)
    def test_shutdown_and_restart(self):
        self.assertEqual(self.query()[0],200)
        self.server.shutdown();self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())
        self.server.server_close()
        self.server=LocalRelayServer(self.relay)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.assertEqual(self.query()[0],200)
    def test_oversized_request_target(self):
        status,_,_=self.query(path='/v1/stock?'+ 'x'*600)
        self.assertEqual(status,414)
        self.assertEqual(self.calls,[])
    def test_oversized_authorization_header(self):
        status,_,_=self.query(auth='x'*300)
        self.assertEqual(status,431)
        self.assertEqual(self.calls,[])
    def test_duplicate_authorization_headers(self):
        sock=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
        try:
            sock.settimeout(2)
            request=(f'GET /v1/stock?item_code=8800286275732&keyword=x HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\nAuthorization: Bearer {KEY}\r\nAuthorization: Bearer {KEY}\r\nConnection: close\r\n\r\n')
            sock.sendall(request.encode())
            data=sock.recv(2048)
            self.assertIn(b'401',data.split(b'\r\n',1)[0])
        finally:sock.close()
        self.assertEqual(self.calls,[])
    def test_slow_partial_request_times_out(self):
        sock=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
        try:
            sock.settimeout(2)
            sock.sendall(b'GET /v1/stock HTTP/1.1\r\nHost: 127.0.0.1\r\n')
            time.sleep(CLIENT_TIMEOUT+0.3)
            data=sock.recv(2048)
            self.assertTrue(data==b'' or b'408' in data or b'400' in data)
        finally:sock.close()
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
