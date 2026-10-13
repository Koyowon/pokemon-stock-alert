"""Offline-only mock alert outbox with atomic claims and bounded retries."""
import secrets
from datetime import datetime, timedelta, timezone

from stock_state_store import (
    MAX_ATTEMPTS, StockAlertError, event_id, locked_state, parse_timestamp, read_state, save_state,
)

DEFAULT_LEASE_SECONDS = 60


def _now(now):
    return datetime.now(timezone.utc) if now is None else parse_timestamp(now)


def queue_event(state, event):
    if event.get("mockOnly") is not True:
        raise StockAlertError("only mock events may be queued")
    identifier = event_id(event)
    if identifier not in state["outbox"]:
        state["outbox"][identifier] = {
            **event, "id": identifier, "status": "pending",
            "attempts": 0, "claimToken": None, "claimExpiresAt": None,
        }
    return state["outbox"][identifier]


def pending_mock_events(state_path):
    """Read-only preview; does not reserve events."""
    with locked_state(state_path):
        state = read_state(state_path)
        return [dict(event) for event in state["outbox"].values() if event["status"] == "pending"]


def _recover(state, now):
    changed = False
    for event in state["outbox"].values():
        if event["status"] == "processing" and parse_timestamp(event["claimExpiresAt"]) <= now:
            event["status"] = "failed" if event["attempts"] >= MAX_ATTEMPTS else "pending"
            event["claimToken"] = None
            event["claimExpiresAt"] = None
            changed = True
    return changed


def recover_expired_claims(state_path, now=None):
    now = _now(now)
    with locked_state(state_path):
        state = read_state(state_path)
        changed = _recover(state, now)
        if changed:
            save_state(state_path, state)
        return changed


def claim_mock_event(state_path, identifier, now=None, lease_seconds=DEFAULT_LEASE_SECONDS):
    """Claim one pending event; returns claimed event with fencing token or None."""
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
        raise StockAlertError("invalid lease duration")
    now = _now(now)
    with locked_state(state_path):
        state = read_state(state_path)
        changed = _recover(state, now)
        event = state["outbox"].get(identifier)
        claimed = None
        if event is None:
            raise StockAlertError("unknown event")
        if event["status"] == "pending":
            if event["attempts"] >= MAX_ATTEMPTS:
                event["status"] = "failed"
                changed = True
            else:
                event["status"] = "processing"
                event["attempts"] += 1
                event["claimToken"] = secrets.token_hex(16)
                event["claimExpiresAt"] = (now + timedelta(seconds=lease_seconds)).isoformat()
                claimed = dict(event)
                changed = True
        if changed:
            save_state(state_path, state)
        return claimed


def _owned(event, token, now):
    if not isinstance(token, str) or not token or event["status"] != "processing":
        raise StockAlertError("event not owned")
    if event["claimToken"] != token or parse_timestamp(event["claimExpiresAt"]) <= now:
        raise StockAlertError("expired or incorrect claim token")


def complete_mock_event(state_path, identifier, token, now=None):
    """Complete only a currently held, unexpired claim. No message is sent."""
    now = _now(now)
    with locked_state(state_path):
        state = read_state(state_path)
        event = state["outbox"].get(identifier)
        if event is None:
            raise StockAlertError("unknown event")
        _owned(event, token, now)
        event.update(status="completed", claimToken=None, claimExpiresAt=None)
        save_state(state_path, state)
        return True


def release_mock_event(state_path, identifier, token, now=None):
    """Release a failed claim, or mark failed after the last attempt."""
    now = _now(now)
    with locked_state(state_path):
        state = read_state(state_path)
        event = state["outbox"].get(identifier)
        if event is None:
            raise StockAlertError("unknown event")
        _owned(event, token, now)
        event.update(
            status="failed" if event["attempts"] >= MAX_ATTEMPTS else "pending",
            claimToken=None, claimExpiresAt=None,
        )
        save_state(state_path, state)
        return event["status"]
