"""Offline-only GS25 relay prototype. No real network or production imports.

The only transport is a caller-supplied fake callable; no HTTP client exists here.
Local endpoint handling is a pure function (not a listening server).
"""
import fcntl
import hmac
import json
import os
import re
import stat
import time
from pathlib import Path


class RelayFailure(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason
        super().__init__(reason)


def _jwt_exp(value):
    import base64
    import binascii
    if not isinstance(value, str) or not re.fullmatch(r'[\w-]+\.[\w-]+\.[\w-]+', value):
        raise RelayFailure(403, 'INVALID_SESSION')
    try:
        payload = value.split('.')[1]
        exp = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))['exp']
        if isinstance(exp, bool) or not isinstance(exp, (int, float)) or exp <= 0:
            raise ValueError()
        return exp
    except (ValueError, KeyError, TypeError, UnicodeError, binascii.Error) as exc:
        raise RelayFailure(403, 'INVALID_SESSION') from exc


def _private_read(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 16384 or info.st_uid != os.getuid():
        raise RelayFailure(403, 'INVALID_SESSION_FILE')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('deviceId'), str) or not re.fullmatch(r'[\w-]{1,100}', data['deviceId']):
        raise RelayFailure(403, 'INVALID_SESSION')
    _jwt_exp(data.get('accessToken'))
    _jwt_exp(data.get('refreshToken'))
    return data


def _private_replace(path, data, replace=os.replace):
    path = Path(path)
    tmp = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _lock(fd, timeout):
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise RelayFailure(503, 'SESSION_BUSY')
            time.sleep(0.01)


def adapt_stores(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('stores'), list):
        raise RelayFailure(502, 'INVALID_STOCK_RESPONSE')
    rows = []
    for row in payload['stores']:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k].strip() for k in ('storeCode', 'storeName')):
            raise RelayFailure(502, 'INVALID_STORE')
        q = row.get('realStockQuantity')
        if type(q) is int and q >= 0:
            quantity = q
        elif isinstance(q, str) and q.isascii() and q.isdecimal():
            quantity = int(q)
        else:
            raise RelayFailure(502, 'INVALID_QUANTITY')
        rows.append({'storeCode': row['storeCode'], 'storeName': row['storeName'], 'realStockQuantity': quantity})
    return {'success': True, 'data': {'inventory': {'stores': rows}}}


class OfflineRelay:
    def __init__(self, session_file, relay_token, fake_refresh, fake_stock, now=None, lock_timeout=1, replace=os.replace):
        if not isinstance(relay_token, str) or len(relay_token) < 16:
            raise ValueError('relay token must be 16+ characters')
        self.session_file = Path(session_file)
        self.lock_file = self.session_file.with_suffix('.lock')
        self.relay_token = relay_token
        self.fake_refresh = fake_refresh
        self.fake_stock = fake_stock
        self.now = now or time.time
        self.lock_timeout = lock_timeout
        self.replace = replace
        self.revoked = False

    def _refresh(self, session):
        if _jwt_exp(session['refreshToken']) <= self.now():
            self.revoked = True
            raise RelayFailure(403, 'SESSION_EXPIRED')
        try:
            result = self.fake_refresh(session['refreshToken'])
        except Exception as exc:
            raise RelayFailure(502, 'REFRESH_UNAVAILABLE') from exc
        if not isinstance(result, dict) or result.get('resultCode') != '0000' or not isinstance(result.get('data'), dict):
            raise RelayFailure(502, 'REFRESH_INVALID')
        values = result['data']
        updated = {'accessToken': values.get('access'), 'refreshToken': values.get('refresh'), 'deviceId': session['deviceId']}
        if _jwt_exp(updated['accessToken']) <= self.now() + 60 or _jwt_exp(updated['refreshToken']) <= self.now():
            raise RelayFailure(502, 'REFRESH_INVALID')
        try:
            _private_replace(self.session_file, updated, self.replace)
        except OSError as exc:
            self.revoked = True
            raise RelayFailure(502, 'SESSION_SAVE_FAILED') from exc
        return updated

    def _session(self, force_token=None):
        fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or info.st_uid != os.getuid():
                raise RelayFailure(403, 'INSECURE_LOCK')
            _lock(fd, self.lock_timeout)
            session = _private_read(self.session_file)
            if force_token is None and _jwt_exp(session['accessToken']) > self.now() + 60:
                return session
            if force_token is not None and session['accessToken'] != force_token:
                return session
            return self._refresh(session)
        finally:
            os.close(fd)

    def handle(self, supplied_token, item_code, keyword):
        if not isinstance(supplied_token, str) or not hmac.compare_digest(supplied_token, self.relay_token):
            return 401, {'error': 'UNAUTHORIZED'}
        if not isinstance(item_code, str) or not re.fullmatch(r'\d{8,14}', item_code) or not isinstance(keyword, str) or not 1 <= len(keyword) <= 80:
            return 400, {'error': 'INVALID_REQUEST'}
        try:
            if self.revoked:
                raise RelayFailure(403, 'SESSION_REVOKED')
            session = self._session()
            try:
                status, payload = self.fake_stock(session['accessToken'], item_code, keyword)
            except Exception as exc:
                raise RelayFailure(502, 'STOCK_UNAVAILABLE') from exc
            if status in (401, 403):
                session = self._session(force_token=session['accessToken'])
                try:
                    status, payload = self.fake_stock(session['accessToken'], item_code, keyword)
                except Exception as exc:
                    raise RelayFailure(502, 'STOCK_UNAVAILABLE') from exc
                if status in (401, 403):
                    self.revoked = True
                    raise RelayFailure(403, 'SESSION_REVOKED')
            if status != 200:
                raise RelayFailure(502, 'STOCK_UNAVAILABLE')
            return 200, adapt_stores(payload)
        except RelayFailure as exc:
            return exc.status, {'error': exc.reason}
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return 502, {'error': 'SESSION_FAILURE'}
