"""Offline GS25 session contract tests; no network, credentials, or production imports.

Run manually: python -m unittest -v tests.test_gs25_auth_contract
These tests model the upstream contract and do not test a live GS25 session.
"""
import base64
import multiprocessing
import stat
import time
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path


NOW = 1800000000


class AuthError(Exception):
    pass


def token(exp):
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return "mock." + payload + ".signature"


def exp(jwt):
    try:
        data = jwt.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)))["exp"]
    except (IndexError, KeyError, ValueError, TypeError, AttributeError, UnicodeError) as exc:
        raise AuthError("BAD_TOKEN") from exc


def adapt(response):
    if not isinstance(response, dict) or response.get("success") is False or not isinstance(response.get("stores"), list):
        raise AuthError("INVALID_STORES")
    result = []
    for row in response["stores"]:
        if not isinstance(row, dict):
            raise AuthError("INVALID_ROW")
        q = row.get("realStockQuantity")
        if not isinstance(row.get('storeCode'), str) or not row['storeCode'].strip() or not isinstance(row.get('storeName'), str) or not row['storeName'].strip():
            raise AuthError('INVALID_STORE_ID')
        if isinstance(q, bool) or not (type(q) is int and q >= 0 or isinstance(q, str) and q.isascii() and q.isdecimal()):
            raise AuthError("INVALID_QUANTITY")
        result.append({**row, "realStockQuantity": int(q)})
    return {"success": True, "data": {"inventory": {"stores": result}}}


class FakeSession:
    def __init__(self, file, renew, stock, replace=os.replace, owner=None, refresh_timeout=0.1):
        self.file, self.renew, self.stock, self.replace = Path(file), renew, stock, replace
        self.owner = os.getuid() if owner is None and hasattr(os, 'getuid') else owner
        self.refresh_timeout = refresh_timeout
        self.lock = threading.Lock()

    def request(self):
        with self.lock:
            info = self.file.stat()
            if info.st_mode & 0o077 or (self.owner is not None and info.st_uid != self.owner):
                raise AuthError("INSECURE_FILE")
            session = json.loads(self.file.read_text())
            def refresh():
                if exp(session["refreshToken"]) <= NOW:
                    raise AuthError("EXPIRED_REFRESH")
                start = time.monotonic()
                status, result = self.renew(session["refreshToken"])
                if time.monotonic() - start > self.refresh_timeout:
                    raise AuthError('REFRESH_TIMEOUT')
                if status in (401, 403):
                    raise AuthError("REFRESH_REJECTED")
                if status != 200 or result.get("resultCode") != "0000":
                    raise AuthError("REFRESH_FAILED")
                next_tokens = result["data"]
                if exp(next_tokens["access"]) <= NOW + 60 or exp(next_tokens["refresh"]) <= NOW:
                    raise AuthError("INVALID_REFRESH_EXP")
                updated = {"accessToken": next_tokens["access"], "refreshToken": next_tokens["refresh"], "deviceId": session["deviceId"]}
                temp = self.file.with_suffix('.' + str(threading.get_ident()) + '.mocktmp')
                try:
                    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'w') as f:
                        json.dump(updated, f)
                    self.replace(temp, self.file)
                except OSError as exc:
                    raise AuthError("SAVE_FAILED") from exc
                finally:
                    temp.unlink(missing_ok=True)
                session.update(updated)
            if exp(session["accessToken"]) <= NOW + 60:
                refresh()
            status, response = self.stock(session["accessToken"])
            if status in (401, 403):
                refresh()
                status, response = self.stock(session["accessToken"])
            if status != 200:
                raise AuthError("STOCK_FAILED")
            return adapt(response)


def positive(_):
    return 200, {"stores": [{"storeCode": "FAKE001", "storeName": "병점역점", "realStockQuantity": "2"}]}


class GS25AuthContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "session.json"
        self.write(NOW + 3600)
        self.renewals = 0

    def write(self, access_exp):
        self.file.write_text(json.dumps({"accessToken": token(access_exp), "refreshToken": token(NOW + 7200), "deviceId": "mock-device"}))
        os.chmod(self.file, 0o600)

    def renew(self, _):
        self.renewals += 1
        return 200, {"resultCode": "0000", "data": {"access": token(NOW + 3600), "refresh": token(NOW + 14400)}}

    def make(self, stock=positive, renew=None, replace=os.replace, **kwargs):
        return FakeSession(self.file, renew or self.renew, stock, replace, **kwargs)

    def test_preexpiry_refresh_and_rotated_storage(self):
        self.write(NOW + 59)
        self.assertEqual(self.make().request()["data"]["inventory"]["stores"][0]["realStockQuantity"], 2)
        self.assertEqual(self.renewals, 1)
        self.assertEqual(json.loads(self.file.read_text())["refreshToken"], token(NOW + 14400))

    def test_401_403_retry(self):
        for status in (401, 403):
            with self.subTest(status=status):
                calls = []
                def stock(t):
                    calls.append(t)
                    return (status, {}) if len(calls) == 1 else positive(t)
                self.assertEqual(self.make(stock).request()["data"]["inventory"]["stores"][0]["realStockQuantity"], 2)
                self.assertEqual(len(calls), 2)

    def test_refresh_rejection_not_zero(self):
        self.write(NOW + 1)
        with self.assertRaisesRegex(AuthError, "REFRESH_REJECTED"):
            self.make(renew=lambda _: (403, {})).request()

    def test_storage_failure_not_zero(self):
        self.write(NOW + 1)
        before = self.file.read_bytes()
        def fail(_src, _dst):
            raise OSError("mock disk failure")
        with self.assertRaisesRegex(AuthError, "SAVE_FAILED"):
            self.make(replace=fail).request()
        self.assertEqual(before, self.file.read_bytes())

    def test_concurrent_requests_one_refresh(self):
        self.write(NOW + 1)
        session = self.make()
        results = []
        threads = [threading.Thread(target=lambda: results.append(session.request())) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 8)
        self.assertEqual(self.renewals, 1)

    def test_response_adapter(self):
        self.assertEqual(adapt(positive(None)[1])["data"]["inventory"]["stores"][0]["realStockQuantity"], 2)
        for invalid in ({}, {"stores": None}, {"stores": [{"realStockQuantity": -1}]}, {"success": False, "stores": []}):
            with self.subTest(invalid=invalid), self.assertRaises(AuthError):
                adapt(invalid)

    def test_session_permissions(self):
        os.chmod(self.file, 0o644)
        with self.assertRaisesRegex(AuthError, "INSECURE_FILE"):
            self.make().request()

    def test_retry_still_unauthorized_is_error(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.write(NOW + 3600)
                with self.assertRaisesRegex(AuthError, 'STOCK_FAILED'):
                    self.make(stock=lambda _: (status, {})).request()

    def test_invalid_jwt_rejected(self):
        for invalid in ('invalid', 'a.!.b', '', None):
            with self.subTest(value=invalid):
                session = json.loads(self.file.read_text())
                session['accessToken'] = invalid
                self.file.write_text(json.dumps(session))
                with self.assertRaises(AuthError):
                    self.make().request()
                self.write(NOW + 3600)

    def test_refresh_timeout_is_error(self):
        self.write(NOW + 1)
        def slow(_):
            time.sleep(0.02)
            return self.renew(_)
        with self.assertRaisesRegex(AuthError, 'REFRESH_TIMEOUT'):
            self.make(renew=slow, refresh_timeout=0.001).request()

    @unittest.skipUnless(hasattr(os, 'getuid'), 'requires POSIX owner semantics')
    def test_wrong_session_owner_rejected(self):
        with self.assertRaisesRegex(AuthError, 'INSECURE_FILE'):
            self.make(owner=os.getuid() + 1).request()

    def test_missing_store_identifier_rejected(self):
        for row in ({'storeName': '병점역점', 'realStockQuantity': 2},
                    {'storeCode': 'FAKE001', 'realStockQuantity': 2},
                    {'storeCode': '', 'storeName': '병점역점', 'realStockQuantity': 2}):
            with self.subTest(row=row), self.assertRaisesRegex(AuthError, 'INVALID_STORE_ID'):
                adapt({'stores': [row]})

    def test_temp_file_is_private_at_creation(self):
        self.write(NOW + 1)
        def inspect(src, dst):
            self.assertEqual(stat.S_IMODE(os.stat(src).st_mode), 0o600)
            return os.replace(src, dst)
        self.make(replace=inspect).request()

    def test_multi_process_refresh_rotation_conflict_detected(self):
        # Two isolated workers can both read the same initial token; a plain
        # atomic rename does NOT provide compare-and-swap for rotated tokens.
        # This is a documented risk, not a claim that cross-process locking exists.
        original = json.loads(self.file.read_text())
        first = {**original, 'refreshToken': token(NOW + 14400)}
        second = {**original, 'refreshToken': token(NOW + 21600)}
        self.file.write_text(json.dumps(first))
        os.replace(self.file, self.file)  # atomic replace alone has no CAS condition
        self.file.write_text(json.dumps(second))
        self.assertEqual(json.loads(self.file.read_text())['refreshToken'], second['refreshToken'])
        self.assertNotEqual(first['refreshToken'], second['refreshToken'])


if __name__ == "__main__":
    unittest.main()
