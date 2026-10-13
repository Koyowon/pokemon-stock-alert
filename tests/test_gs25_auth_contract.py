"""Offline GS25 session contract tests; no network, credentials, or production imports.

Run manually: python -m unittest -v tests.test_gs25_auth_contract
These tests model the upstream contract and do not test a live GS25 session.
"""
import base64
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
    except (IndexError, KeyError, ValueError, TypeError) as exc:
        raise AuthError("BAD_TOKEN") from exc


def adapt(response):
    if not isinstance(response, dict) or response.get("success") is False or not isinstance(response.get("stores"), list):
        raise AuthError("INVALID_STORES")
    result = []
    for row in response["stores"]:
        if not isinstance(row, dict):
            raise AuthError("INVALID_ROW")
        q = row.get("realStockQuantity")
        if isinstance(q, bool) or not (type(q) is int and q >= 0 or isinstance(q, str) and q.isascii() and q.isdecimal()):
            raise AuthError("INVALID_QUANTITY")
        result.append({**row, "realStockQuantity": int(q)})
    return {"success": True, "data": {"inventory": {"stores": result}}}


class FakeSession:
    def __init__(self, file, renew, stock, replace=os.replace):
        self.file, self.renew, self.stock, self.replace = Path(file), renew, stock, replace
        self.lock = threading.Lock()

    def request(self):
        with self.lock:
            if self.file.stat().st_mode & 0o077:
                raise AuthError("INSECURE_FILE")
            session = json.loads(self.file.read_text())
            def refresh():
                if exp(session["refreshToken"]) <= NOW:
                    raise AuthError("EXPIRED_REFRESH")
                status, result = self.renew(session["refreshToken"])
                if status in (401, 403):
                    raise AuthError("REFRESH_REJECTED")
                if status != 200 or result.get("resultCode") != "0000":
                    raise AuthError("REFRESH_FAILED")
                next_tokens = result["data"]
                if exp(next_tokens["access"]) <= NOW + 60 or exp(next_tokens["refresh"]) <= NOW:
                    raise AuthError("INVALID_REFRESH_EXP")
                updated = {"accessToken": next_tokens["access"], "refreshToken": next_tokens["refresh"], "deviceId": session["deviceId"]}
                temp = self.file.with_suffix(".mocktmp")
                try:
                    with open(temp, "x") as f:
                        json.dump(updated, f)
                    os.chmod(temp, 0o600)
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

    def make(self, stock=positive, renew=None, replace=os.replace):
        return FakeSession(self.file, renew or self.renew, stock, replace)

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


if __name__ == "__main__":
    unittest.main()
