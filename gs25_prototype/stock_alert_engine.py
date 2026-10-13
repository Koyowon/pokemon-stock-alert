"""Offline-only GS25 mock stock change detection. No network or notification transport."""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STATE_VERSION = 1
MAX_QUANTITY = 9999


class StockAlertError(ValueError):
    """Invalid or unsafe mock stock input."""


def _key(product_code, store_code):
    if not isinstance(product_code, str) or not product_code.startswith("MOCK_") or not product_code[5:].replace("_", "").isalnum():
        raise StockAlertError("invalid mock product code")
    if not isinstance(store_code, str) or not store_code.startswith("MOCK_") or not store_code[5:].replace("_", "").isalnum():
        raise StockAlertError("invalid mock store code")
    return product_code + "::" + store_code


def _quantity(value):
    if type(value) is not int or not 0 <= value <= MAX_QUANTITY:
        raise StockAlertError("invalid quantity")
    return value


def _read_state(path):
    path = Path(path)
    if not path.exists():
        return {"version": STATE_VERSION, "items": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StockAlertError("unreadable state; refusing to overwrite") from exc
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION or not isinstance(state.get("items"), dict):
        raise StockAlertError("unsupported state")
    for key, item in state["items"].items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise StockAlertError("corrupt state")
        _quantity(item.get("quantity"))
        if not isinstance(item.get("observed_at"), str):
            raise StockAlertError("corrupt timestamp")
    return state


def _save_state(path, state):
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
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def process_mock_snapshot(state_path, product_code, product_name, stores, observed_at=None):
    """Process a complete offline snapshot, returning mock notifications only.

    First observation establishes baseline. Increased quantities generate one event.
    Identical snapshots do not repeat events. Older observations are ignored.
    No network, Android, GS25 app, or external message transport is used.
    """
    if not isinstance(product_name, str) or not product_name.strip() or len(product_name) > 120:
        raise StockAlertError("invalid product name")
    if not isinstance(stores, list) or not stores:
        raise StockAlertError("stores must be a nonempty list")
    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat()
    try:
        timestamp = datetime.fromisoformat(observed_at)
        if timestamp.tzinfo is None:
            raise ValueError("timezone required")
        timestamp = timestamp.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError) as exc:
        raise StockAlertError("invalid observed_at") from exc

    validated = []
    seen = set()
    for store in stores:
        if not isinstance(store, dict):
            raise StockAlertError("invalid store")
        key = _key(product_code, store.get("storeCode"))
        name = store.get("storeName")
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise StockAlertError("invalid store name")
        quantity = _quantity(store.get("realStockQuantity"))
        if key in seen:
            raise StockAlertError("duplicate store")
        seen.add(key)
        validated.append((key, name, quantity, store["storeCode"]))

    state = _read_state(state_path)
    events = []
    changed = False
    for key, name, quantity, store_code in validated:
        previous = state["items"].get(key)
        if previous is not None:
            prior_time = datetime.fromisoformat(previous["observed_at"])
            if prior_time.tzinfo is None:
                raise StockAlertError("corrupt timestamp")
            if timestamp <= prior_time.astimezone(timezone.utc):
                continue
            old = previous["quantity"]
            if quantity > old:
                events.append({
                    "type": "restocked" if old == 0 else "increased",
                    "productCode": product_code,
                    "productName": product_name,
                    "storeCode": store_code,
                    "storeName": name,
                    "previousQuantity": old,
                    "currentQuantity": quantity,
                    "observedAt": timestamp,
                    "mockOnly": True,
                })
        state["items"][key] = {"quantity": quantity, "observed_at": timestamp}
        changed = True
    if changed:
        _save_state(state_path, state)
    return events


def mock_notification_preview(event):
    """Return a local text preview; never send a notification."""
    if event.get("mockOnly") is not True:
        raise StockAlertError("only mock events supported")
    return ("[GS25 모의 재고 알림] " + event["productName"] + "\n"
            + event["storeName"] + " (" + event["storeCode"] + ")\n"
            + str(event["previousQuantity"]) + "개 → " + str(event["currentQuantity"]) + "개\n"
            + "테스트 데이터 · 실제 매장 재고 아님")
