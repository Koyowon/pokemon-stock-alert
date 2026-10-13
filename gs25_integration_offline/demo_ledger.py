"""Separate offline DEMO_ state and idempotent simulated delivery ledger.

Does not import gs25_prototype and does not share its state file.
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path

from contracts import StockRecord


class OfflineDemoLedger:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.state_path = self.directory / "demo-stock.json"
        self.receipts_path = self.directory / "demo-receipts.json"

    @staticmethod
    def _read(path, default):
        if not path.exists():
            return default
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("invalid demo state")
        return value

    @staticmethod
    def _write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as f:
                name = f.name
                json.dump(value, f, ensure_ascii=False, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, path)
            fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def observe(self, record: StockRecord):
        """Return a new DEMO_ increase event or None; no external effects."""
        if not isinstance(record, StockRecord):
            raise ValueError("StockRecord required")
        if not record.product_code.startswith("DEMO_") or not record.store_code.startswith("DEMO_"):
            raise ValueError("demo codes only")
        if type(record.quantity) is not int or not 0 <= record.quantity <= 9999:
            raise ValueError("invalid demo quantity")
        from datetime import datetime, timezone
        instant = datetime.fromisoformat(record.observed_at)
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("timezone required")
        normalized = instant.astimezone(timezone.utc).isoformat()
        key = record.product_code + "::" + record.store_code
        state = self._read(self.state_path, {})
        previous = state.get(key)
        if previous is not None and normalized <= previous["observed_at"]:
            return None
        event = None
        if previous is not None and record.quantity > previous["quantity"]:
            payload = [record.product_code, record.store_code, previous["quantity"], record.quantity, normalized]
            digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()[:32]
            event = {
                "id": "demo_" + digest, "productCode": record.product_code,
                "storeCode": record.store_code, "storeName": record.store_name,
                "previousQuantity": previous["quantity"], "currentQuantity": record.quantity,
                "observedAt": normalized, "offlineOnly": True,
            }
        state[key] = {"quantity": record.quantity, "observed_at": normalized}
        self._write(self.state_path, state)
        return event

    def preview_send(self, event, sender):
        """Record a fake receipt, keyed by event ID, without a real transport."""
        if event.get("offlineOnly") is not True or not str(event.get("id", "")).startswith("demo_"):
            raise ValueError("offline DEMO_ event required")
        receipts = self._read(self.receipts_path, {})
        identifier = event["id"]
        if identifier in receipts:
            return receipts[identifier]
        receipt = sender.send(event, identifier)
        receipts[identifier] = receipt
        self._write(self.receipts_path, receipts)
        return receipt
