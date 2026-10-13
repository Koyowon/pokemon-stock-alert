"""Offline-only DEMO ledger: locked state, leased fake deliveries, recovery.

No GS25 API, credentials, real notification transport or gs25_prototype imports.
The receipt ledger records synthetic receipts only. A production sender is forbidden.
"""
import fcntl
import hashlib
import json
import os
import secrets
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from contracts import FakeAlertSender, StockRecord

MAX_ATTEMPTS = 3
LEASE_SECONDS = 60


class DemoStateError(ValueError):
    pass


class DemoDurabilityError(DemoStateError):
    """File replacement succeeded, but directory fsync was not confirmed."""


def _time(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if not isinstance(value, str):
        raise DemoStateError("invalid timestamp")
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError("timezone required")
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise DemoStateError("invalid timestamp") from exc


def _demo_code(value):
    return isinstance(value, str) and value.startswith("DEMO_") and 5 < len(value) <= 70 and all(
        char.isupper() or char.isdigit() or char == "_" for char in value[5:]
    )


def _validate_stock(data):
    if not isinstance(data, dict):
        raise DemoStateError("invalid stock state")
    for key, entry in data.items():
        if not isinstance(key, str) or len(key.split("::")) != 2 or not all(
            _demo_code(code) for code in key.split("::")
        ):
            raise DemoStateError("invalid stock key")
        if not isinstance(entry, dict) or set(entry) != {"quantity", "observed_at"}:
            raise DemoStateError("invalid stock entry")
        if type(entry["quantity"]) is not int or not 0 <= entry["quantity"] <= 9999:
            raise DemoStateError("invalid stock quantity")
        _time(entry["observed_at"])


def _validate_receipts(data):
    if not isinstance(data, dict):
        raise DemoStateError("invalid receipt ledger")
    for identifier, entry in data.items():
        if not isinstance(identifier, str) or not identifier.startswith("demo_"):
            raise DemoStateError("invalid event identifier")
        if isinstance(entry, str):  # read old offline prototype receipts
            if not entry.startswith("FAKE_RECEIPT_"):
                raise DemoStateError("invalid legacy receipt")
            continue
        if not isinstance(entry, dict) or set(entry) != {
            "status", "attempts", "token", "expires_at", "receipt"
        }:
            raise DemoStateError("invalid delivery entry")
        status, attempts = entry["status"], entry["attempts"]
        if status not in ("pending", "processing", "completed", "failed"):
            raise DemoStateError("invalid delivery status")
        if type(attempts) is not int or not 0 <= attempts <= MAX_ATTEMPTS:
            raise DemoStateError("invalid attempts")
        if status == "processing":
            if attempts == 0 or not isinstance(entry["token"], str) or not entry["token"]:
                raise DemoStateError("invalid claim")
            _time(entry["expires_at"])
            if entry["receipt"] is not None:
                raise DemoStateError("unexpected processing receipt")
        else:
            if entry["token"] is not None or entry["expires_at"] is not None:
                raise DemoStateError("unexpected claim")
            if status == "completed":
                if not isinstance(entry["receipt"], str) or not entry["receipt"].startswith("FAKE_RECEIPT_"):
                    raise DemoStateError("invalid completed receipt")
            elif entry["receipt"] is not None:
                raise DemoStateError("unexpected receipt")


class OfflineDemoLedger:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.state_path = self.directory / "demo-stock.json"
        self.receipts_path = self.directory / "demo-receipts.json"
        self.lock_path = self.directory / "demo-ledger.lock"

    @contextmanager
    def _locked(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _read(path, validator):
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DemoStateError("corrupt state; refusing overwrite") from exc
        validator(data)
        return data

    @staticmethod
    def _write(path, data, validator):
        validator(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", dir=path.parent, encoding="utf-8", delete=False
            ) as handle:
                temporary = handle.name
                json.dump(data, handle, ensure_ascii=False, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            temporary = None
            try:
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError as exc:
                raise DemoDurabilityError("file replaced; durability unconfirmed") from exc
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def _save(self, path, data, validator):
        # Backups are verified copies of the last readable state, never of corrupt input.
        if path.exists():
            prior = self._read(path, validator)
            self._write(path.with_name(path.name + ".bak"), prior, validator)
        self._write(path, data, validator)

    def backup(self):
        """Refresh validated backups under the lock; never silently restore corruption."""
        with self._locked():
            for path, validator in (
                (self.state_path, _validate_stock),
                (self.receipts_path, _validate_receipts),
            ):
                if path.exists():
                    current = self._read(path, validator)
                    self._write(path.with_name(path.name + ".bak"), current, validator)

    def restore_backup(self, kind):
        """Explicit manual recovery only; no automatic overwriting of corrupt files."""
        if kind not in ("stock", "receipts"):
            raise DemoStateError("invalid backup kind")
        path = self.state_path if kind == "stock" else self.receipts_path
        validator = _validate_stock if kind == "stock" else _validate_receipts
        with self._locked():
            backup_path = path.with_name(path.name + ".bak")
            if not backup_path.exists():
                raise DemoStateError("backup missing")
            recovered = self._read(backup_path, validator)
            self._write(path, recovered, validator)

    def observe(self, record: StockRecord):
        if not isinstance(record, StockRecord):
            raise DemoStateError("StockRecord required")
        if not _demo_code(record.product_code) or not _demo_code(record.store_code):
            raise DemoStateError("DEMO_ codes only")
        if not isinstance(record.store_name, str) or not record.store_name.strip():
            raise DemoStateError("invalid store name")
        if type(record.quantity) is not int or not 0 <= record.quantity <= 9999:
            raise DemoStateError("invalid quantity")
        instant = _time(record.observed_at).isoformat()
        key = record.product_code + "::" + record.store_code
        with self._locked():
            state = self._read(self.state_path, _validate_stock)
            previous = state.get(key)
            if previous and instant <= _time(previous["observed_at"]).isoformat():
                return None
            event = None
            if previous and record.quantity > previous["quantity"]:
                payload = [record.product_code, record.store_code, previous["quantity"], record.quantity, instant]
                digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()[:32]
                event = {
                    "id": "demo_" + digest, "productCode": record.product_code,
                    "storeCode": record.store_code, "storeName": record.store_name,
                    "previousQuantity": previous["quantity"], "currentQuantity": record.quantity,
                    "observedAt": instant, "offlineOnly": True,
                }
            state[key] = {"quantity": record.quantity, "observed_at": instant}
            self._save(self.state_path, state, _validate_stock)
            return event

    @staticmethod
    def _check_event(event):
        if not isinstance(event, dict) or event.get("offlineOnly") is not True:
            raise DemoStateError("offline event required")
        if not isinstance(event.get("id"), str) or not event["id"].startswith("demo_"):
            raise DemoStateError("invalid demo event")
        if not _demo_code(event.get("productCode")) or not _demo_code(event.get("storeCode")):
            raise DemoStateError("DEMO_ event codes required")
        return event["id"]

    @staticmethod
    def _recover(entries, now):
        changed = False
        for entry in entries.values():
            if isinstance(entry, dict) and entry["status"] == "processing" and _time(entry["expires_at"]) <= now:
                entry.update(
                    status="failed" if entry["attempts"] >= MAX_ATTEMPTS else "pending",
                    token=None, expires_at=None,
                )
                changed = True
        return changed

    def recover_expired_claims(self, now=None):
        instant = _time(now)
        with self._locked():
            entries = self._read(self.receipts_path, _validate_receipts)
            changed = self._recover(entries, instant)
            if changed:
                self._save(self.receipts_path, entries, _validate_receipts)
            return changed

    def claim(self, event, now=None, lease_seconds=LEASE_SECONDS):
        identifier = self._check_event(event)
        instant = _time(now)
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise DemoStateError("invalid lease")
        with self._locked():
            entries = self._read(self.receipts_path, _validate_receipts)
            changed = self._recover(entries, instant)
            entry = entries.setdefault(identifier, {
                "status": "pending", "attempts": 0, "token": None,
                "expires_at": None, "receipt": None,
            })
            if entry["status"] != "pending":
                if changed:
                    self._save(self.receipts_path, entries, _validate_receipts)
                return None
            if entry["attempts"] >= MAX_ATTEMPTS:
                entry["status"] = "failed"
                self._save(self.receipts_path, entries, _validate_receipts)
                return None
            token = secrets.token_hex(16)
            entry.update(
                status="processing", attempts=entry["attempts"] + 1, token=token,
                expires_at=(instant + timedelta(seconds=lease_seconds)).isoformat(),
            )
            self._save(self.receipts_path, entries, _validate_receipts)
            return token

    def _finish(self, event, token, receipt, now=None):
        identifier = self._check_event(event)
        instant = _time(now)
        with self._locked():
            entries = self._read(self.receipts_path, _validate_receipts)
            entry = entries.get(identifier)
            if not isinstance(entry, dict) or entry["status"] != "processing":
                raise DemoStateError("event not claimed")
            if not isinstance(token, str) or entry["token"] != token or _time(entry["expires_at"]) <= instant:
                raise DemoStateError("invalid or expired claim")
            if receipt is not None and (not isinstance(receipt, str) or not receipt.startswith("FAKE_RECEIPT_")):
                raise DemoStateError("fake receipt required")
            entry.update(
                status=("completed" if receipt is not None else
                        "failed" if entry["attempts"] >= MAX_ATTEMPTS else "pending"),
                token=None, expires_at=None, receipt=receipt,
            )
            self._save(self.receipts_path, entries, _validate_receipts)
            return entry["status"]

    def complete(self, event, token, receipt, now=None):
        return self._finish(event, token, receipt, now)

    def release(self, event, token, now=None):
        return self._finish(event, token, None, now)

    def preview_send(self, event, sender):
        """Only a FakeAlertSender is allowed; no real delivery or transport."""
        identifier = self._check_event(event)
        if type(sender) is not FakeAlertSender:
            raise DemoStateError("FakeAlertSender required")
        with self._locked():
            entries = self._read(self.receipts_path, _validate_receipts)
            existing = entries.get(identifier)
            if isinstance(existing, str):
                return existing
            if isinstance(existing, dict) and existing["status"] == "completed":
                return existing["receipt"]
        token = self.claim(event)
        if token is None:
            return None
        try:
            receipt = sender.send(event, identifier)
            self.complete(event, token, receipt)
            return receipt
        except Exception:
            try:
                self.release(event, token)
            except DemoStateError:
                pass
            raise
