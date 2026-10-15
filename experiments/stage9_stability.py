"""Isolated stage9 state-sync, CAS retry, and claimed-event audit utilities.

No I/O on import. Caller provides Git fetch/compare-and-swap implementation.
"""
import copy
from datetime import datetime, timezone


class ConcurrentUpdate(RuntimeError):
    pass


def preserve_alerts(old, new):
    """Never discard pending/claimed events when refreshing scanner stock."""
    result = copy.deepcopy(new)
    prior = old.get("pending_alerts", {})
    current = result.setdefault("pending_alerts", {})
    for eid, event in prior.items():
        if eid in current and current[eid] != event:
            raise ValueError("event state conflict")
        current[eid] = copy.deepcopy(event)
    result["alert_sequence"] = max(old.get("alert_sequence", 0), result.get("alert_sequence", 0))
    return result


def cas_publish(load, compare_and_swap, transform, retries=3):
    """Fetch latest state for EACH attempt; do not send any alert here."""
    for attempt in range(retries):
        version, latest = load()
        candidate = transform(copy.deepcopy(latest))
        if compare_and_swap(candidate, version):
            return candidate, attempt
    raise ConcurrentUpdate("CAS retries exhausted; do not send")


def claimed_audit(state, now=None, threshold_seconds=3600):
    """Surface claimed events that might never have been delivered."""
    if now is None:
        now = datetime.now(timezone.utc)
    flagged = []
    for eid, event in state.get("pending_alerts", {}).items():
        if event.get("status") != "claimed":
            continue
        when = event.get("claimed_at")
        if not when:
            flagged.append(eid)
            continue
        dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("claimed_at must have timezone")
        if (now - dt).total_seconds() >= threshold_seconds:
            flagged.append(eid)
    return flagged
