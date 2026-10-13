"""Offline GS25 integration contracts. No credentials, HTTP clients or transports.

This prototype intentionally cannot authenticate, call a stock API or send alerts.
Production adapters must be separately implemented and explicitly authorized.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence


@dataclass(frozen=True)
class StockRecord:
    product_code: str
    store_code: str
    store_name: str
    quantity: int
    observed_at: str


class AuthenticationProvider(ABC):
    @abstractmethod
    def authenticate(self) -> str:
        """Return a synthetic credential in this prototype."""


class StockProvider(ABC):
    @abstractmethod
    def fetch(self, credential: str, product_code: str) -> Sequence[StockRecord]:
        """Return synthetic observations; never call GS25."""


class AlertSender(ABC):
    @abstractmethod
    def send(self, event: Mapping[str, object], idempotency_key: str) -> str:
        """Return a synthetic delivery receipt; never send externally."""


class FakeAuthentication(AuthenticationProvider):
    def authenticate(self) -> str:
        return "FAKE_OFFLINE_CREDENTIAL"


class FakeStockProvider(StockProvider):
    def __init__(self, records: Sequence[StockRecord]):
        self._records = tuple(records)

    def fetch(self, credential: str, product_code: str) -> Sequence[StockRecord]:
        if credential != "FAKE_OFFLINE_CREDENTIAL":
            raise ValueError("offline fake credential required")
        if not isinstance(product_code, str) or not product_code.startswith("DEMO_"):
            raise ValueError("only DEMO_ products allowed")
        return tuple(record for record in self._records if record.product_code == product_code)


class FakeAlertSender(AlertSender):
    def __init__(self):
        self.receipts = {}

    def send(self, event: Mapping[str, object], idempotency_key: str) -> str:
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise ValueError("idempotency key required")
        if event.get("offlineOnly") is not True:
            raise ValueError("offline-only event required")
        if idempotency_key not in self.receipts:
            self.receipts[idempotency_key] = "FAKE_RECEIPT_" + idempotency_key
        return self.receipts[idempotency_key]
