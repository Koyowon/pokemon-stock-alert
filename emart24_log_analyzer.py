"""Offline parser for existing Emart24 monitor logs; no network or state writes.

Input can contain sensitive material. Never print or retain original lines in
diagnostic output. An OK store status verifies numeric stock but does NOT reveal
whether the quantity was zero. The zeroes passed to diagnose are internal
verification markers, NOT observed inventory quantities.
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from emart24_health_diagnostic import Health, diagnose

STORE = re.compile(r"\bSTORE\s+(\d+)\s*\|[^\r\n|]*\|\s*(OK|NOT_CHECKED|BATCH_ERROR|SINGLE_ERROR|MISSING_IN_RESPONSE|NULL_OR_INVALID_QTY)\s*$")
HTTP_502 = re.compile(r"\b(?:HTTP(?:Error)?(?:\s*:?\s*|\s+Error\s+))502\b|\b502\s*:\s*Bad Gateway\b", re.I)
WARNING_ERROR = re.compile(r"\bWARNING:\s*(?:inventory batch failed|single-store lookup failed)\b")
NUMERIC_SUMMARY = re.compile(r"\b(\d+)\s*/\s*(\d+)\s+numeric results\b")


@dataclass(frozen=True)
class Summary:
    health: str
    verified_numeric_stores: int
    unknown_stores: int
    total_stores: int
    http_502_evidence: bool
    generic_error_evidence: bool
    confirmed_zero_stores: int | None
    recovered: bool

    def safe_dict(self):
        return vars(self).copy()


def analyze(text: str, previous_health: Health | None = None) -> Summary:
    if not isinstance(text, str):
        raise TypeError("text must be str")
    statuses = {}
    saw_502 = False
    saw_generic = False
    reported = None
    for line in text.splitlines():
        match = STORE.search(line)
        if match:
            statuses[match.group(1)] = match.group(2)
        if WARNING_ERROR.search(line):
            if HTTP_502.search(line):
                saw_502 = True
            else:
                saw_generic = True
        match = NUMERIC_SUMMARY.search(line)
        if match:
            reported = (int(match.group(1)), int(match.group(2)))

    # The existing monitor logs OK only after validating a nonnegative int.
    # 0 here is an opaque valid-int marker, never an observed stock quantity.
    markers = {code: 0 for code, status in statuses.items() if status == "OK"}
    result = diagnose(statuses, markers, previous_health=previous_health)
    health = result.health
    if not statuses or reported is None or (\n            reported[0] != result.checked or reported[1] != len(statuses)):
        # Incomplete or inconsistent logs cannot establish a healthy run.
        health = Health.UNKNOWN
    return Summary(
        health=health.value,
        verified_numeric_stores=result.checked,
        unknown_stores=result.unknown,
        total_stores=len(statuses),
        http_502_evidence=saw_502,
        generic_error_evidence=saw_generic,
        confirmed_zero_stores=None,
        recovered=previous_health in (Health.UNKNOWN, Health.PARTIAL)
                  and health == Health.OK and len(statuses) > 0,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline, redacted Emart24 log health summary")
    parser.add_argument("log_file", help="Local pre-existing monitor log (read-only)")
    parser.add_argument("--previous-health", choices=[x.value for x in Health])
    args = parser.parse_args(argv)
    try:
        raw = Path(args.log_file).read_text(encoding="utf-8", errors="replace")
        prev = Health(args.previous_health) if args.previous_health else None
        summary = analyze(raw, prev)
    except (OSError, ValueError, TypeError):
        print("ERROR: unable to analyze input", file=sys.stderr)
        return 2
    print(json.dumps(summary.safe_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
