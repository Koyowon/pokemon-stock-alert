"""Opt-in Asan status delivery; separate from legacy CU alert state.

Disabled by default. Deduplication uses a separate, private status marker.
"""
import errno
import fcntl
import stat
import uuid
import hashlib
import json
import os
from pathlib import Path

ENV_FLAG = "ASAN_CU_STATUS_TELEGRAM_ENABLED"
MARKER_ENV = "ASAN_CU_STATUS_MARKER_PATH"


def enabled(environ=None):
    env = os.environ if environ is None else environ
    return env.get(ENV_FLAG, "") == "true"


def delivery_key(snapshot):
    """Stable observation key: only fully successful Asan runs qualify."""
    if snapshot.get("query_succeeded") is not True or snapshot.get("candidate_count") != 123:
        raise ValueError("Incomplete Asan observation")
    if snapshot.get("barcode") != "8800286275732":
        raise ValueError("Unexpected barcode")
    if snapshot.get("query_failures", 0) or snapshot.get("conflicting_codes"):
        raise ValueError("Incomplete or conflicting observation")
    if "query_total" in snapshot and (snapshot["query_total"] < 1 or snapshot.get("query_successes") != snapshot["query_total"]):
        raise ValueError("Partial coordinate coverage")
    rows = snapshot["candidates"]
    if len(rows) != 123 or any(row.get("status") == "NOT_QUERIED" for row in rows):
        raise ValueError("Incomplete Asan snapshot")
    ids = [r.get("registry_id") for r in rows]
    if len(set(ids)) != 123 or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("Duplicate or missing Asan registry IDs")
    if not any(r.get("status") in ("IN_STOCK", "ZERO_STOCK") for r in rows):
        raise ValueError("No observed stock values")
    for row in rows:
        status, stock = row.get("status"), row.get("stock")
        if status == "IN_STOCK" and (type(stock) is not int or stock <= 0):
            raise ValueError("Invalid positive stock")
        if status == "ZERO_STOCK" and (type(stock) is not int or stock != 0):
            raise ValueError("Invalid zero stock")
        if status not in ("IN_STOCK", "ZERO_STOCK", "NOT_OBSERVED", "NO_VALID_STOCK_VALUE"):
            raise ValueError("Invalid stock status")
        if status not in ("IN_STOCK", "ZERO_STOCK") and stock is not None:
            raise ValueError("Unknown stock must be null")
    canonical = [(r["registry_id"], r["status"], r["stock"]) for r in rows]
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _atomic_marker(path, data):
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as stream:
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temp.unlink(missing_ok=True)


def send_status(snapshot, pages, sender, *, marker_path=None, environ=None):
    """Journal each page before sending; uncertain deliveries require reconciliation."""
    env = os.environ if environ is None else environ
    if not enabled(env):
        return "DISABLED"
    path = marker_path if marker_path is not None else env.get(MARKER_ENV)
    if not path:
        return "NO_MARKER_PATH"
    path = Path(path)
    from cu_stock_monitor import STATE_FILE
    if (path.is_symlink() or not path.parent.is_dir() or path.name == "cu_stock_state.json"
            or path.resolve() == STATE_FILE.resolve()):
        return "INVALID_MARKER_PATH"
    key = delivery_key(snapshot)
    if not pages or any(not isinstance(p, str) or not p or len(p) > 4096 for p in pages):
        raise ValueError("Invalid status pages")
    page_hash = hashlib.sha256(json.dumps(pages, ensure_ascii=False).encode()).hexdigest()
    lock_path = path.with_name(path.name + ".lock")
    if lock_path.is_symlink():
        return "INVALID_LOCK"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_nlink != 1:
            return "INVALID_LOCK"
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EACCES):
                return "LOCKED"
            raise
        if path.is_symlink():
            return "INVALID_MARKER_PATH"
        if path.exists():
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(old, dict):
                    return "INVALID_MARKER"
                if old.get("state") == "IN_FLIGHT":
                    return "NEEDS_RECONCILIATION"
                if old.get("key") == key and old.get("state", "DONE") == "DONE":
                    return "UNCHANGED"
                if old.get("state", "DONE") != "DONE":
                    return "INVALID_MARKER"
            except (OSError, ValueError, AttributeError):
                return "INVALID_MARKER"
        for index, page in enumerate(pages):
            _atomic_marker(path, {"key": key, "pages_sha256": page_hash,
                                  "state": "IN_FLIGHT", "page_index": index,
                                  "page_count": len(pages)})
            try:
                success = sender(page) is True
            except Exception:
                return "NEEDS_RECONCILIATION"
            if not success:
                return "SEND_FAILED" if index == 0 else "NEEDS_RECONCILIATION"
        _atomic_marker(path, {"key": key, "pages_sha256": page_hash,
                              "state": "DONE", "page_count": len(pages)})
        return "SENT"
    finally:
        os.close(fd)
