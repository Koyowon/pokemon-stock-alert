"""End-to-end loopback-only integration tests with fake GS25 transports."""
import base64
import concurrent.futures
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

NOW = 1800000000
KEY = 'fake-integration-secret-123456'
BARCODE = '8800286275732'


def jwt(exp, suffix=''):
    data = base64.urlsafe_b64encode(json.dumps({'exp': exp, 'id': suffix}).encode()).decode().rstrip('=')
    return 'fake.' + data + '.sig'


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'session.json'
        self.save(jwt(NOW + 1), jwt(NOW + 7200))
        self.refresh_calls = 0
        self.stock_calls = 0
        self.guard = threading.Lock()
        self.refresh_error = False
        self.stock_mode = 'ok'
        self.save_error = False
        self.relay = self.new_relay()
        self.server = LocalRelayServer(self.relay)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def save(self, access, refresh):
        _private_replace(self.path, {'accessToken': access, 'refreshToken': refresh, 'deviceId': 'fake-device'})

    def refresh(self, old):
        with self.guard:
            self.refresh_calls += 1
            index = self.refresh_calls
        if self.refresh_error:
            return {'resultCode': 'FAILED'}
        return {'resultCode': '0000', 'data': {'access': jwt(NOW + 3600, str(index)), 'refresh': jwt(NOW + 7200, str(index))}}

    def stock(self, access, item, keyword):
        with self.guard:
            self.stock_calls += 1
        if self.stock_mode == '401':
            return 401, {}
        if self.stock_mode == '403':
            return 403, {}
        if self.stock_mode == 'first401' and self.stock_calls == 1:
            return 401, {}
        return 200, {'stores': [{'storeCode': 'FAKE01', 'storeName': '가상점포', 'realStockQuantity': 3}]}

    def new_relay(self, **kwargs):
        return OfflineRelay(self.path, KEY, self.refresh, self.stock, now=lambda: NOW, **kwargs)

    def stop(self):
        if self.thread.is_alive():
            self.server.shutdown()
            self.thread.join(timeout=3)
        self.server.server_close()

    def request(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        try:
            conn.request('GET', '/v1/stock?' + urlencode({'item_code': BARCODE, 'keyword': '테스트'}), headers={'Authorization': 'Bearer ' + KEY})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_concurrent_http_refresh_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda _: self.request(), range(12)))
        self.assertEqual([status for status, _ in results], [200] * 12)
        self.assertEqual(self.refresh_calls, 1)
        self.assertEqual(self.stock_calls, 12)
        self.assertEqual(json.loads(self.path.read_text())['refreshToken'], jwt(NOW + 7200, '1'))

    def test_restart_reuses_persisted_session_without_refresh(self):
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.refresh_calls, 1)
        self.stop()
        self.relay = self.new_relay()
        self.server = LocalRelayServer(self.relay)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.refresh_calls, 1)

    def test_refresh_error_never_claims_zero_stock(self):
        self.refresh_error = True
        status, body = self.request()
        self.assertEqual(status, 502)
        self.assertNotIn('inventory', body)
        self.assertEqual(self.stock_calls, 0)

    def test_save_error_fails_closed(self):
        original = self.path.read_bytes()
        def fail(*args):
            raise OSError('fake disk error')
        self.relay.replace = fail
        status, body = self.request()
        self.assertEqual((status, body), (502, {'error': 'SESSION_SAVE_FAILED'}))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.request(), (403, {'error': 'SESSION_REVOKED'}))
        self.assertEqual(self.stock_calls, 0)

    def test_401_retries_once_then_revokes(self):
        self.save(jwt(NOW + 3600), jwt(NOW + 7200))
        self.stock_mode = '401'
        status, body = self.request()
        self.assertEqual((status, body), (403, {'error': 'SESSION_REVOKED'}))
        self.assertEqual(self.stock_calls, 2)
        self.assertEqual(self.refresh_calls, 1)
        self.assertEqual(self.request()[0], 403)
        self.assertEqual(self.stock_calls, 2)

    def test_403_retries_once_then_revokes(self):
        self.save(jwt(NOW + 3600), jwt(NOW + 7200))
        self.stock_mode = '403'
        self.assertEqual(self.request()[0], 403)
        self.assertEqual(self.stock_calls, 2)
        self.assertEqual(self.refresh_calls, 1)

    def test_single_401_refresh_then_recovers(self):
        self.save(jwt(NOW + 3600), jwt(NOW + 7200))
        self.stock_mode = 'first401'
        status, body = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(body['data']['inventory']['stores'][0]['realStockQuantity'], 3)
        self.assertEqual(self.stock_calls, 2)
        self.assertEqual(self.refresh_calls, 1)


if __name__ == '__main__':
    unittest.main()
