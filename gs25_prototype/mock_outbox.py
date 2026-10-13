"""Persistent offline-only outbox for mock GS25 alerts. Never sends messages."""
import hashlib
import json

from stock_state_store import StockAlertError, locked_state, read_state, save_state


def event_id(event):
    fields = ("productCode", "storeCode", "previousQuantity", "currentQuantity", "observedAt")
    payload = json.dumps([event[field] for field in fields], ensure_ascii=False, separators=(",", ":"))
    return "evt_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def queue_event(state, event):
    if event.get("mockOnly") is not True:
        raise StockAlertError("only mock events may be queued")
    identifier = event_id(event)
    if identifier not in state["outbox"]:
        state["outbox"][identifier] = {**event, "id": identifier, "status": "pending"}
    return state["outbox"][identifier]


def pending_mock_events(state_path):
    """Read persistent pending previews under the same state lock."""
    with locked_state(state_path):
        state = read_state(state_path)
        return [dict(event) for event in state["outbox"].values() if event["status"] == "pending"]


def complete_mock_event(state_path, identifier):
    """Mark a mock event completed locally. Does not deliver it."""
    with locked_state(state_path):
        state = read_state(state_path)
        event = state["outbox"].get(identifier)
        if event is None:
            raise StockAlertError("unknown event")
        if event["status"] == "completed":
            return False
        event["status"] = "completed"
        save_state(state_path, state)
        return True
