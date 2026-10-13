"""Loopback-only, offline HTTP facade for OfflineRelay; never calls GS25."""
import json
import ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

HOST = '127.0.0.1'
MAX_TARGET = 512
MAX_AUTH_HEADER = 256
MAX_HEADERS = 24
CLIENT_TIMEOUT = 0.5

class LocalRelayServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True
    def __init__(self, relay, host=HOST, port=0):
        if host != HOST:
            raise ValueError('loopback IPv4 binding only')
        self.relay = relay
        super().__init__((HOST, port), RelayHandler)

class RelayHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def setup(self):
        super().setup()
        self.connection.settimeout(CLIENT_TIMEOUT)
    def log_message(self, *args):
        pass  # no secrets, URLs or authorization headers in logs
    def _respond(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        if len(self.path) > MAX_TARGET:
            return self._respond(414, {'error':'INVALID_REQUEST'})
        target = urlsplit(self.path)
        if target.path != '/v1/stock' or target.fragment:
            return self._respond(404, {'error':'NOT_FOUND'})
        if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length') not in (None, '0'):
            self.close_connection = True
            return self._respond(400, {'error':'INVALID_REQUEST'})
        if self.headers.get('Host') not in (f'{HOST}:{self.server.server_port}', HOST):
            return self._respond(400, {'error':'INVALID_HOST'})
        if len(self.headers) > MAX_HEADERS or any(len(v) > MAX_AUTH_HEADER for v in self.headers.get_all('Authorization', [])):
            return self._respond(431, {'error':'HEADERS_TOO_LARGE'})
        if len(self.headers.get_all('Authorization', [])) != 1:
            return self._respond(401, {'error':'UNAUTHORIZED'})
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer ') or auth.count(' ') != 1:
            return self._respond(401, {'error':'UNAUTHORIZED'})
        token = auth[7:]
        try:
            params = parse_qs(target.query, keep_blank_values=True, strict_parsing=True, max_num_fields=3)
        except ValueError:
            return self._respond(400, {'error':'INVALID_REQUEST'})
        if set(params) != {'item_code', 'keyword'} or any(len(v) != 1 for v in params.values()):
            return self._respond(400, {'error':'INVALID_REQUEST'})
        status, result = self.server.relay.handle(token, params['item_code'][0], params['keyword'][0])
        self._respond(status, result)
    def do_POST(self):
        self.close_connection = True
        self._respond(405, {'error':'METHOD_NOT_ALLOWED'})
    def do_PUT(self):
        self.close_connection = True
        self._respond(405, {'error':'METHOD_NOT_ALLOWED'})
    def do_DELETE(self):
        self.close_connection = True
        self._respond(405, {'error':'METHOD_NOT_ALLOWED'})
