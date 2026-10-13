"""Offline-only GS25 mock stock change detection. No network or notification transport."""
import re
from datetime import datetime, timezone

from mock_outbox import queue_event
from stock_state_store import (
    StockAlertError, locked_state, parse_timestamp, read_state, save_state, valid_quantity,
)


def _key(product_code, store_code):
    for code in (product_code, store_code):
        if not isinstance(code, str) or not re.fullmatch(r"MOCK_[A-Z0-9_]{1,64}", code):
            raise StockAlertError("invalid mock code")
    return product_code + "::" + store_code


def process_mock_snapshot(state_path, product_code, product_name, stores, observed_at=None):
    """Record mock stock changes and pending mock alerts in one atomic state document.

    First observation establishes baseline. Only increases queue an alert.
    Older/equal-time observations are ignored. All storage is local and offline.
    """
    if not isinstance(product_name, str) or not product_name.strip() or len(product_name) > 120:
        raise StockAlertError("invalid product name")
    if not isinstance(stores, list) or not stores:
        raise StockAlertError("stores must be a nonempty list")
    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat()
    timestamp = parse_timestamp(observed_at).isoformat()

    validated = []
    seen = set()
    for store in stores:
        if not isinstance(store, dict):
            raise StockAlertError("invalid store")
        key = _key(product_code, store.get("storeCode"))
        name = store.get("storeName")
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise StockAlertError("invalid store name")
        quantity = valid_quantity(store.get("realStockQuantity"))
        if key in seen:
            raise StockAlertError("duplicate store")
        seen.add(key)
        validated.append((key, name, quantity, store["storeCode"]))

    with locked_state(state_path):
        state = read_state(state_path)
        events = []
        changed = False
        for key, name, quantity, store_code in validated:
            previous = state["items"].get(key)
            if previous is not None:
                prior_time = parse_timestamp(previous["observed_at"])
                if parse_timestamp(timestamp) <= prior_time:
                    continue
                old = previous["quantity"]
                if quantity > old:
                    event = {
                        "type": "restocked" if old == 0 else "increased",
                        "productCode": product_code,
                        "productName": product_name,
                        "storeCode": store_code,
                        "storeName": name,
                        "previousQuantity": old,
                        "currentQuantity": quantity,
                        "observedAt": timestamp,
                        "mockOnly": True,
                    }
                    queued = queue_event(state, event)
                    events.append(dict(queued))
            state["items"][key] = {"quantity": quantity, "observed_at": timestamp}
            changed = True
        if changed:
            save_state(state_path, state)
        return events


def mock_notification_preview(event):
    """Return a local text preview; never send a notification."""
    if not isinstance(event, dict) or event.get("mockOnly") is not True:
        raise StockAlertError("only mock events supported")
    for field in ("productName", "storeName", "storeCode"):
        if not isinstance(event.get(field), str) or not event[field]:
            raise StockAlertError("invalid mock event")
    old = valid_quantity(event.get("previousQuantity"))
    new = valid_quantity(event.get("currentQuantity"))
    return ("[GS25 모의 재고 알림] " + event["productName"] + "\n"
            + event["storeName"] + " (" + event["storeCode"] + ")\n"
            + str(old) + "개 → " + str(new) + "개\n"
            + "테스트 데이터 · 실제 매장 재고 아님")
