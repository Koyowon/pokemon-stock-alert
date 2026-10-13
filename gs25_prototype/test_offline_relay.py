"""Offline relay tests. No sockets or external network; all upstream calls are fakes.

Run from repository root:
  python -m unittest discover -s gs25_prototype -p 'test_*.py' -v
"""
import base64
import json
import os
import tempfile
import unittest
from pathlib import Path

from offline_relay import OfflineRelay, _private_replace


NOW = 1800000000
KEY = 'test-only-relay-secret-123'


def jwt(exp):
    payload = base64.urlsafe_b64encode(json.dumps({'exp': exp}).encode()).decode().rstrip('=')
    return 'fake.' + payload + '.sig'


class OfflineRelayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'session.json'
        _private_replace(self.path, {'accessToken': jwt(NOW + 3600), 'refreshToken': jwt(NOW + 7200), 'deviceId': 'fake-device'})
        self.calls = []

    def refresh(self, old):
        self.calls.append(('refresh', old))
        return {'resultCode': '0000', 'data': {'access': jwt(NOW + 3600), 'refresh': jwt(NOW + 14400)}}

    def stock(self, access, item_code, keyword):
        self.calls.append(('stock', access))
        return 200, {'stores': [{'storeCode': 'FAKE01', 'storeName': '가상점포', 'realStockQuantity': '2'}]}

    def relay(self, **kwargs):
        return OfflineRelay(self.path, KEY, self.refresh, self.stock, now=lambda: NOW, **kwargs)

    def query(self, relay, token=KEY):
        return relay.handle(token, '8800286275732', '테스트')

    def test_authorized_response_adapter(self):
        status, data = self.query(self.relay())
        self.assertEqual(status, 200)
        self.assertEqual(data['data']['inventory']['stores'][0]['realStockQuantity'], 2)

    def test_bad_relay_token_denied_before_stock(self):
        status, _ = self.query(self.relay(), 'invalid')
        self.assertEqual(status, 401)
        self.assertEqual(self.calls, [])

    def test_proactive_refresh_rotates_session(self):
        self.path.write_text(json.dumps({'accessToken': jwt(NOW + 1), 'refreshToken': jwt(NOW + 7200), 'deviceId': 'fake-device'}))
        os.chmod(self.path, 0o600)
        status, _ = self.query(self.relay())
        self.assertEqual(status, 200)
        self.assertEqual([x[0] for x in self.calls].count('refresh'), 1)
        self.assertEqual(json.loads(self.path.read_text())['refreshToken'], jwt(NOW + 14400))

    def test_failed_refresh_does_not_report_zero_stock(self):
        self.path.write_text(json.dumps({'accessToken': jwt(NOW + 1), 'refreshToken': jwt(NOW + 7200), 'deviceId': 'fake-device'}))
        os.chmod(self.path, 0o600)
        relay = self.relay()
        relay.fake_refresh = lambda _: {'resultCode': 'FAILED'}
        status, payload = self.query(relay)
        self.assertNotEqual(status, 200)
        self.assertNotIn('inventory', payload)

    def test_save_failure_revokes_in_memory(self):
        self.path.write_text(json.dumps({'accessToken': jwt(NOW + 1), 'refreshToken': jwt(NOW + 7200), 'deviceId': 'fake-device'}))
        os.chmod(self.path, 0o600)
        def fail(*_):
            raise OSError('simulated')
        relay = self.relay(replace=fail)
        status, payload = self.query(relay)
        self.assertEqual(status, 502)
        self.assertEqual(payload['error'], 'SESSION_SAVE_FAILED')
        self.assertEqual(self.query(relay)[1]['error'], 'SESSION_REVOKED')

    def test_invalid_request_denied_before_stock(self):
        status, _ = self.relay().handle(KEY, '../bad', 'test')
        self.assertEqual(status, 400)
        self.assertEqual(self.calls, [])

    def test_bad_stock_shape_is_not_zero(self):
        relay = self.relay()
        relay.fake_stock = lambda *_: (200, {'stores': [{'storeCode': 'FAKE01', 'storeName': '가상점포'}]})
        status, payload = self.query(relay)
        self.assertEqual(status, 502)
        self.assertNotIn('inventory', payload)


if __name__ == '__main__':
    unittest.main()
