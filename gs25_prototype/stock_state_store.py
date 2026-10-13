"""Linux-only locked and atomic storage for offline GS25 mock events."""
import fcntl
import hashlib
import json
import math
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

STATE_VERSION = 3
MAX_ATTEMPTS = 3
CODE_RE = re.compile(r"MOCK_[A-Z0-9_]{1,64}\Z")


class StockAlertError(ValueError):
    """Invalid mock input or corrupt persistent state."""


class StateDurabilityError(StockAlertError):
    """Rename succeeded, but directory durability could not be confirmed."""

    def __init__(self, message, observed_state=None):
        super().__init__(message)
        self.observed_state = observed_state


def parse_timestamp(value):
    if not isinstance(value, str):
        raise StockAlertError("invalid timestamp")
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("timezone required")
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise StockAlertError("invalid timestamp") from exc


def valid_quantity(value):
    if type(value) is not int or not 0 <= value <= 9999:
        raise StockAlertError("invalid quantity")
    return value


def event_id(event):
    fields = ("productCode", "storeCode", "previousQuantity", "currentQuantity", "observedAt")
    payload = json.dumps([event[field] for field in fields], ensure_ascii=False, separators=(",", ":"))
    return "evt_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _validate_items(items):
    if not isinstance(items, dict):
        raise StockAlertError("invalid items")
    for key, item in items.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise StockAlertError("corrupt item")
        codes = key.split("::")
        if len(codes) != 2 or any(CODE_RE.fullmatch(code) is None for code in codes):
            raise StockAlertError("invalid item key")
        if set(item) != {"quantity", "observed_at"}:
            raise StockAlertError("invalid item fields")
        valid_quantity(item["quantity"])
        parse_timestamp(item["observed_at"])


def _validate_outbox(outbox, version):
    if not isinstance(outbox, dict):
        raise StockAlertError("invalid outbox")
    for identifier, event in outbox.items():
        if not isinstance(identifier, str) or not isinstance(event, dict):
            raise StockAlertError("corrupt outbox")
        if event.get("id") != identifier or event.get("mockOnly") is not True:
            raise StockAlertError("invalid event identity")
        for field in ("productCode", "storeCode"):
            if not isinstance(event.get(field), str) or CODE_RE.fullmatch(event[field]) is None:
                raise StockAlertError("invalid mock event code")
        for field, limit in (("productName", 120), ("storeName", 80)):
            value = event.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise StockAlertError("invalid event name")
        old = valid_quantity(event.get("previousQuantity"))
        new = valid_quantity(event.get("currentQuantity"))
        if new <= old or event.get("type") != ("restocked" if old == 0 else "increased"):
            raise StockAlertError("invalid stock transition")
        parse_timestamp(event.get("observedAt"))
        if event_id(event) != identifier:
            raise StockAlertError("event id mismatch")
        status = event.get("status")
        if version == 2:
            if status not in ("pending", "completed"):
                raise StockAlertError("invalid legacy status")
        else:
            if status not in ("pending", "processing", "completed", "failed"):
                raise StockAlertError("invalid event status")
            attempts = event.get("attempts")
            if type(attempts) is not int or not 0 <= attempts <= MAX_ATTEMPTS:
                raise StockAlertError("invalid attempt count")
            token = event.get("claimToken")
            expiry = event.get("claimExpiresAt")
            if status == "processing":
                if not isinstance(token, str) or not token or not isinstance(expiry, str):
                    raise StockAlertError("missing claim")
                parse_timestamp(expiry)
                if attempts == 0:
                    raise StockAlertError("invalid processing attempts")
            elif token is not None or expiry is not None:
                raise StockAlertError("unexpected claim")


def read_state(path):
    path = Path(path)
    if not path.exists():
        return {"version": STATE_VERSION, "items": {}, "outbox": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StockAlertError("unreadable state; refusing to overwrite") from exc
    if not isinstance(state, dict):
        raise StockAlertError("invalid state")
    version = state.get("version")
    if type(version) is not int or version not in (1, 2, 3):
        raise StockAlertError("unsupported state")
    if set(state) != ({"version", "items"} if version == 1 else {"version", "items", "outbox"}):
        raise StockAlertError("unexpected state fields")
    _validate_items(state["items"])
    if version == 1:
        outbox = {}
    else:
        outbox = state["outbox"]
        _validate_outbox(outbox, version)
    if version < STATE_VERSION:
        outbox = {identifier: {**event, "attempts": 0, "claimToken": None, "claimExpiresAt": None}
                  for identifier, event in outbox.items()}
    return {"version": STATE_VERSION, "items": state["items"], "outbox": outbox}


def save_state(path, state):
    """Caller holds lock. Rename and directory fsync are separate failure phases."""
    if not isinstance(state, dict) or set(state) != {"version", "items", "outbox"} or state["version"] != STATE_VERSION:
        raise StockAlertError("invalid state version")
    _validate_items(state["items"])
    _validate_outbox(state["outbox"], STATE_VERSION)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".gs25-state-", suffix=".tmp", delete=False) as f:
            temp_name = f.name
            json.dump(state, f, ensure_ascii=False, sort_keys=True, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
        try:
            fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as exc:
            try:
                observed = read_state(path)
            except StockAlertError:
                observed = None
            raise StateDurabilityError("state replaced; directory durability unconfirmed", observed) from exc
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


@contextmanager
def locked_state(path, timeout=5.0):
    """Stable advisory sidecar lock, never unlink the lock file."""
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout < 0:
        raise StockAlertError("invalid lock timeout")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "a+b") as lock_file:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise StockAlertError("state lock timeout")
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
