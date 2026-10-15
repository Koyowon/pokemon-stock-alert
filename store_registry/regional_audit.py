"""Pure in-memory regional audit summaries of offline review reports.

Counts are observations, not verified stores, closures, or permissions.
"""
from collections import Counter

from store_registry.source_audit import REGIONS


def summarize(report):
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("unsupported report")
    if report.get("approved_for_production") != 0 or report.get("automatic_registration") is not False:
        raise ValueError("unsafe approval flag")
    items = report.get("items")
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    regions = {region: {"total": 0, "manual_review": 0, "quarantined": 0}
               for region in sorted(REGIONS)}
    reasons = Counter()
    freshness = Counter()
    repeats = Counter()
    evidence = {"missing": 0, "supplied_unverified": 0, "independently_verified": 0}
    seen = set()
    for item in items:
        if not isinstance(item, dict) or item.get("region") not in REGIONS:
            raise ValueError("invalid candidate region")
        key = (item.get("chain"), item.get("store_id"))
        if key in seen:
            raise ValueError("duplicate candidate")
        seen.add(key)
        if item.get("approved_for_production") is not False:
            raise ValueError("candidate cannot be approved")
        status = item.get("status")
        if status not in ("manual_review", "quarantined"):
            raise ValueError("invalid status")
        r = regions[item["region"]]
        r["total"] += 1
        r[status] += 1
        item_reasons = item.get("quarantine_reasons")
        if not isinstance(item_reasons, list) or any(not isinstance(x, str) for x in item_reasons):
            raise ValueError("invalid reasons")
        reasons.update(set(item_reasons))
        if item.get("freshness") not in ("stale", "within_policy"):
            raise ValueError("invalid freshness")
        freshness[item["freshness"]] += 1
        if item.get("repeated_capture") not in ("confirmed", "unconfirmed"):
            raise ValueError("invalid repeat status")
        repeats[item["repeated_capture"]] += 1
        if item.get("evidence_independently_verified") is not False:
            raise ValueError("unverified evidence must not be promoted")
        evidence["missing" if "independent_evidence_missing" in item_reasons
                 else "supplied_unverified"] += 1
    return {
        "schema_version": 1, "chain": report.get("chain"),
        "total_candidates": len(items),
        "by_region": regions,
        "quarantine_reasons": dict(sorted(reasons.items())),
        "evidence": evidence,
        "freshness": dict(sorted(freshness.items())),
        "repeated_capture": dict(sorted(repeats.items())),
        "capture_change_observations": {
            "missing_in_one_capture": reasons["not_repeated"],
            "identity_changed": reasons["identity_changed"],
            "confirmed_repeat": repeats["confirmed"],
        },
        "approved_for_production": 0, "closure_candidates": [],
        "read_only": True,
    }


def render_markdown(summary):
    def safe(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = [
        "# Offline candidate regional audit",
        "",
        "Declarations are unverified; this report does not authorize store admission or closure.",
        "",
        "Chain: " + safe(summary["chain"]),
        "Total candidates: " + str(summary["total_candidates"]),
        "Approved for production: 0",
        "",
        "| Region | Total | Manual review | Quarantined |",
        "| --- | ---: | ---: | ---: |",
    ]
    for region, counts in summary["by_region"].items():
        lines.append("| " + safe(region) + " | " + " | ".join(
            str(counts[k]) for k in ("total", "manual_review", "quarantined")) + " |")
    for title, key in [
        ("Quarantine reasons", "quarantine_reasons"),
        ("Evidence status", "evidence"),
        ("Capture freshness", "freshness"),
        ("Repeat capture", "repeated_capture"),
        ("Capture changes", "capture_change_observations"),
    ]:
        lines += ["", "## " + title, ""]
        for label, count in summary[key].items():
            lines.append("- " + safe(label) + ": " + str(count))
    return "\n".join(lines) + "\n"
