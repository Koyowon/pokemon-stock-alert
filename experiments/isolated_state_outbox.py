"""Isolated branch prototype: separate state branch and at-most-once notification outbox.

No network, Telegram, GitHub, or filesystem writes on import. The caller owns
atomic commits and must persist the claimed event before attempting delivery.
"""
import copy
import hashlib
import json


def event_id(chain, sequence, message):
    if chain not in ("cu", "emart24"):
        raise ValueError("unsupported chain")
    if not isinstance(sequence, int) or sequence < 1:
        raise ValueError("invalid sequence")
    if not isinstance(message, str) or not message:
        raise ValueError("invalid message")
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]
    return f"{chain}-{sequence}-{digest}"


def queue_transition(state, chain, message):
    """Return a new state and event id; caller must publish before dispatch."""
    result = copy.deepcopy(state)
    if not isinstance(result, dict):
        raise ValueError("invalid state")
    pending = result.setdefault("pending_alerts", {})
    if not isinstance(pending, dict):
        raise ValueError("invalid outbox")
    if len([v for v in pending.values() if v["status"] == "pending"]) >= 1000:
        raise ValueError("pending capacity exceeded")
    seq = result.get("alert_sequence", 0) + 1
    eid = event_id(chain, seq, message)
    if eid in pending:
        raise ValueError("event collision")
    pending[eid] = {"status": "pending", "message": message}
    result["alert_sequence"] = seq
    return result, eid


def claim_event(state, eid):
    """Claim an event in an atomic Git commit BEFORE any Telegram attempt."""
    result = copy.deepcopy(state)
    event = result.get("pending_alerts", {}).get(eid)
    if not event or event.get("status") != "pending":
        raise ValueError("event not pending")
    event["status"] = "claimed"
    return result


def dispatch_once(load, commit, send, eid):
    """Never call send unless a durable claim commit succeeds.

    commit(candidate, expected_version) must be atomic compare-and-swap.
    Returns whether send was attempted, not whether Telegram delivered.
    """
    version, state = load()
    candidate = claim_event(state, eid)
    if not commit(candidate, version):
        return False
    send(candidate["pending_alerts"][eid]["message"])
    return True


def state_branch_policy(branch, paths):
    """Validate isolation; not a replacement for GitHub branch protection."""
    if branch != "stock-state-isolated":
        raise ValueError("state branch required")
    allowed = {"cu_stock_state.json", "state.json", "stores.json",
               "gs25_independent/gs25_stock_state.json"}
    if not paths or not set(paths) <= allowed:
        raise ValueError("non-state path")
    return True
