"""Standalone, opt-in Asan GS25 expansion engine. No production imports or writes.
Default disabled. Caller supplies a query function and persists returned state separately.
"""
from dataclasses import dataclass
from time import monotonic
import re

@dataclass(frozen=True)
class Limits:
    max_queries: int = 30
    max_seconds: float = 90.0
    max_results_per_query: int = 100


def validate_config(config):
    if config.get('enabled') is not True:
        return False
    if config.get('alerts_enabled') is not True:
        # First deploy can use baseline-only mode; alerts stay off.
        pass
    codes = config.get('approved_codes', [])
    if not isinstance(codes, list) or len(codes) != len(set(codes)) or any(not re.fullmatch(r'V[A-Z0-9]{4}', c) for c in codes):
        raise ValueError('INVALID_APPROVED_CODES')
    return True


def scan(config, prior, terms, query, *, limits=Limits(), clock=monotonic):
    """Returns (new_state, alerts, report); never mutates prior.

    Query returns list[dict] containing storeCode, storeName, realStockQuantity.
    On ANY failure, returns prior untouched and no alerts. Missing stores remain
    unknown; no inferred zero. Newly observed stores are always baseline-only.
    """
    if not validate_config(config):
        return dict(prior), [], {'status': 'DISABLED', 'queries': 0}
    if len(terms) > limits.max_queries or len(terms) == 0:
        return dict(prior), [], {'status': 'QUERY_BUDGET', 'queries': 0}
    allowed = set(config['approved_codes'])
    existing = {k: dict(v) for k, v in prior.items()}
    seen = {}
    start = clock()
    for n, term in enumerate(terms, 1):
        if clock() - start >= limits.max_seconds:
            return existing, [], {'status': 'TIME_BUDGET', 'queries': n - 1}
        try:
            rows = query(term)
            if not isinstance(rows, list) or len(rows) >= limits.max_results_per_query:
                raise ValueError('INVALID_OR_TRUNCATED_RESPONSE')
            for row in rows:
                code = row.get('storeCode')
                if code not in allowed:
                    continue
                quantity = row.get('realStockQuantity')
                if type(quantity) is not int or quantity < 0:
                    raise ValueError('INVALID_QUANTITY')
                name = row.get('storeName')
                if not isinstance(name, str) or not name.strip():
                    raise ValueError('INVALID_NAME')
                entry = {'name': name.strip()[:80], 'quantity': quantity}
                if code in seen and seen[code]['quantity'] != quantity:
                    raise ValueError('CONFLICTING_QUANTITY')
                seen[code] = entry
        except Exception as exc:
            return existing, [], {'status': 'QUERY_FAILED', 'queries': n, 'reason': type(exc).__name__}
        if clock() - start >= limits.max_seconds:
            return existing, [], {'status': 'TIME_BUDGET', 'queries': n}
    alerts = []
    for code, entry in sorted(seen.items()):
        previous = existing.get(code)
        if previous is not None and previous['quantity'] != entry['quantity'] and config.get('alerts_enabled') is True:
            alerts.append({'code': code, 'old': previous['quantity'], 'new': entry['quantity'], 'name': entry['name']})
        existing[code] = entry
    # Retired codes are excluded from current scanning, not deleted from history.
    return existing, alerts, {'status': 'OK', 'queries': len(terms), 'observed': len(seen), 'baselined': sum(k not in prior for k in seen)}
