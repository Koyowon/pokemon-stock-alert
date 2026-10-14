"""Pure, offline Emart24 inventory health classification. No I/O or side effects."""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional


class Health(str, Enum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Result:
    health: Health
    checked: int
    unknown: int
    http_502: int
    recovered: bool


def diagnose(statuses: Mapping[str, str], quantities: Mapping[str, object],
             *, previous_health: Optional[Health] = None) -> Result:
    """Classify per-store observations; only nonnegative *int* values are verified.

    Statuses: OK, HTTP_502, BATCH_ERROR, SINGLE_ERROR, NOT_CHECKED,
    MISSING_IN_RESPONSE, NULL_OR_INVALID_QTY. Unknown statuses are unverified.
    A 502 is counted only when explicitly identified, never inferred from a
    generic batch/single error. No values are logged or persisted.
    """
    if previous_health is not None and not isinstance(previous_health, Health):
        raise TypeError("previous_health must be Health or None")
    if set(quantities) - set(statuses):
        raise ValueError("quantities include unregistered stores")
    checked = sum(
        status == "OK" and type(quantities.get(code)) is int
        and quantities[code] >= 0
        for code, status in statuses.items()
    )
    unknown = len(statuses) - checked
    http_502 = sum(status == "HTTP_502" for status in statuses.values())
    health = (Health.UNKNOWN if checked == 0 else
              Health.OK if unknown == 0 else Health.PARTIAL)
    return Result(health, checked, unknown, http_502,
                  previous_health in (Health.UNKNOWN, Health.PARTIAL)
                  and health == Health.OK)
