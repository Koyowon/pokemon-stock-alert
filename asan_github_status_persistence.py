"""Separate GitHub-branch persistence for Asan status, with optimistic CAS.

No network occurs on import. Inject an adapter implementing read() and cas().
The adapter must implement compare-and-swap against a remote branch ref, not
merely a read-then-write of a GitHub Contents API file SHA.
"""
import hashlib
import json

STATE_BRANCH = "state/asan-cu-status"
STATE_PATH = "asan_status_delivery_state.json"


class PersistenceError(RuntimeError):
    pass


def _digest(pages):
    return hashlib.sha256(json.dumps(pages, ensure_ascii=False).encode()).hexdigest()


def deliver_persistent(snapshot, pages, sender, adapter, *, enabled=False):
    """Fail closed on absent state branch, CAS failure, or uncertain delivery.

    adapter.read() -> (revision, state). A missing branch must raise.
    adapter.cas(expected_revision, state) -> new revision, or raise.
    IN_FLIGHT is intentionally never auto-retried, even after a send failure.
    """
    if not enabled:
        return "DISABLED"
    from asan_status_delivery import delivery_key
    key = delivery_key(snapshot)
    if not pages or any(not isinstance(p, str) or not p or len(p) > 4096 for p in pages):
        raise ValueError("Invalid pages")
    try:
        revision, old = adapter.read()
        if not revision or not isinstance(old, dict):
            return "STATE_UNAVAILABLE"
        if old.get("state") == "IN_FLIGHT":
            return "NEEDS_RECONCILIATION"
        if old.get("state") not in ("READY", "DONE"):
            return "INVALID_STATE"
        if old.get("state") == "DONE" and old.get("key") == key:
            return "UNCHANGED"
        revision = adapter.cas(revision, {"state": "IN_FLIGHT", "key": key,
                                          "pages_sha256": _digest(pages),
                                          "page_index": 0, "page_count": len(pages)})
    except Exception:
        return "STATE_UNAVAILABLE"
    for index, page in enumerate(pages):
        if index:
            try:
                revision = adapter.cas(revision, {"state": "IN_FLIGHT", "key": key,
                                                  "pages_sha256": _digest(pages),
                                                  "page_index": index,
                                                  "page_count": len(pages)})
            except Exception:
                return "NEEDS_RECONCILIATION"
        try:
            if sender(page) is not True:
                return "NEEDS_RECONCILIATION"
        except Exception:
            return "NEEDS_RECONCILIATION"
    try:
        adapter.cas(revision, {"state": "DONE", "key": key,
                               "pages_sha256": _digest(pages),
                               "page_count": len(pages)})
    except Exception:
        return "NEEDS_RECONCILIATION"
    return "SENT"
