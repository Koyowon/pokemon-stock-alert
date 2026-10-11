"""GS25 inventory provider boundary. No network calls or credentials in this module."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class Status(str, Enum):
    NOT_CONFIGURED = 'AUTHORIZED_INTERFACE_NOT_CONFIGURED'
    UNAUTHORIZED = 'AUTHORIZATION_REQUIRED'
    UNKNOWN = 'STOCK_UNKNOWN'
    AVAILABLE = 'STOCK_VERIFIED'

@dataclass(frozen=True)
class StockResult:
    status: Status
    quantity: Optional[int] = None
    store_id: Optional[str] = None

    def __post_init__(self):
        if self.status == Status.AVAILABLE:
            if type(self.quantity) is not int or self.quantity < 0 or not self.store_id:
                raise ValueError('Verified stock requires nonnegative integer quantity and store ID')
        elif self.quantity is not None:
            raise ValueError('Unknown/error status must not carry quantity')


def query_stock(*, item_code: str, store_id: str) -> StockResult:
    """Fail closed until an explicitly authorized inventory interface is integrated."""
    if not item_code or not store_id:
        raise ValueError('item_code and store_id required')
    return StockResult(status=Status.NOT_CONFIGURED)
