"""Opt-in Asan status delivery; separate from legacy CU alert state.

Disabled by default. Deduplication uses a separate, private status marker.
"""
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
    rows = snapshot["candidates"]
    if len(rows) != 123 or any(row.get("status") == "NOT_QUERIED" for row in rows):
        raise ValueError("Incomplete Asan snapshot")
    canonical = [(r["registry_id"], r["status"], r["stock"]) for r in rows]
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def send_status(snapshot, pages, sender, *, marker_path=None, environ=None):
    """Fail closed: no send without opt-in and explicit, separate marker path.

    Marker is written only after every page succeeds. A failed multi-page send
    can repeat earlier pages on retry; callers must not promise exactly-once.
    """
    env = os.environ if environ is None else environ
    if not enabled(env):
        return "DISABLED"
    path = marker_path if marker_path is not None else env.get(MARKER_ENV)
    if not path:
        return "NO_MARKER_PATH"
    path = Path(path)
    if path.is_symlink() or not path.parent.is_dir():
        return "INVALID_MARKER_PATH"
    if path.name == "cu_stock_state.json":
        return "INVALID_MARKER_PATH"
    from cu_stock_monitor import STATE_FILE
    if path.resolve() == STATE_FILE.resolve():
        return "INVALID_MARKER_PATH"
    key = delivery_key(snapshot)
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if old.get("key") == key:
                return "UNCHANGED"
        except (OSError, ValueError, AttributeError):
            return "INVALID_MARKER"
    if not pages or any(not isinstance(page, str) or len(page) > 4096 for page in pages):
        raise ValueError("Invalid status pages")
    for page in pages:
        if sender(page) is not True:
            return "SEND_FAILED"
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("x", encoding="utf-8") as stream:
            json.dump({"key": key}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return "SENT"
