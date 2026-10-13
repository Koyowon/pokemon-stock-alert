"""Locked, atomic, offline-only storage for GS25 mock stock state (Linux)."""
import fcntl
import json
import os
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

STATE_VERSION = 2


class StockAlertError(ValueError):
    """Invalid input, state corruption, or unsafe state operation."""


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


def _validate_items(items):
    if not isinstance(items, dict):
        raise StockAlertError("invalid items")
    for key, entry in items.items():
        if not isinstance(key, str) or "::" not in key or not isinstance(entry, dict):
            raise StockAlertError("corrupt item")
        valid_quantity(entry.get("quantity"))
        parse_timestamp(entry.get("observed_at"))


def _validate_outbox(outbox):
    if not isinstance(outbox, dict):
        raise StockAlertError("invalid outbox")
    for event_id, entry in outbox.items():
        if not isinstance(event_id, str) or not isinstance(entry, dict):
            raise StockAlertError("corrupt outbox")
        if entry.get("id") != event_id or entry.get("status") not in ("pending", "completed"):
            raise StockAlertError("corrupt outbox status")
        if entry.get("mockOnly") is not True:
            raise StockAlertError("non-mock outbox entry")
        valid_quantity(entry.get("previousQuantity"))
        valid_quantity(entry.get("currentQuantity"))
        parse_timestamp(entry.get("observedAt"))
        for field in ("productCode", "productName", "storeCode", "storeName", "type"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                raise StockAlertError("corrupt outbox field")


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
    _validate_items(state.get("items"))
    if version == 1:
        if set(state) != {"version", "items"}:
            raise StockAlertError("unexpected v1 state fields")
        return {"version": STATE_VERSION, "items": state["items"], "outbox": {}}
    if version != STATE_VERSION or set(state) != {"version", "items", "outbox"}:
        raise StockAlertError("unsupported state")
    _validate_outbox(state.get("outbox"))
    return state


def save_state(path, state):
    """Replace a single document atomically; caller must hold its lock."""
    path = Path(path)
    _validate_items(state.get("items"))
    _validate_outbox(state.get("outbox"))
    if state.get("version") != STATE_VERSION:
        raise StockAlertError("invalid state version")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".gs25-state-", suffix=".tmp", delete=False) as f:
            temp_name = f.name
            json.dump(state, f, ensure_ascii=False, sort_keys=True, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
        # Best effort directory fsync for durability after rename.
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


@contextmanager
def locked_state(path, timeout=5.0):
    """Exclusive advisory lock on stable sidecar file across read/modify/write."""
    path = Path(path)
    if not isinstance(timeout, (int, float)) or timeout < 0:
        raise StockAlertError("invalid lock timeout")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with open(lock_path, "a+b") as lock_file:
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
