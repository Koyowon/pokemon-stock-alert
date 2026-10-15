"""Pure in-memory JSON and Markdown reports for offline manual review.

Never writes files, calls providers, sends messages or approves candidates.
"""
import json
from datetime import datetime, timezone

from store_registry.manual_review_queue import queue

ACTIONS = {
    "not_repeated": "Repeat capture; missing store is not a closure",
    "identity_changed": "Confirm store identity against independent evidence",
    "coverage_unverified": "Document geographic coverage for both captures",
    "capture_has_quarantined_rows": "Resolve quarantined input rows",
    "stale_capture": "Provide fresh captures",
    "already_registered": "Review existing registry entry; do not duplicate",
    "independent_evidence_missing": "Supply two independently checkable sources",
}


def build_report(root, captures, evidence=None, now=None):
    """Return report data only; no filesystem or external side effects."""
    if now is None:
        now = datetime.now(timezone.utc)
    result = queue(root, captures, evidence=evidence, now=now)
    items = []
    for item in result["items"]:
        code = item["store_id"]
        supplied = (evidence or {}).get(code, [])
        refs = []
        if isinstance(supplied, list):
            for entry in supplied:
                if isinstance(entry, dict):
                    refs.append({"source": str(entry.get("source", "")),
                                 "reference": str(entry.get("reference", "")),
                                 "verified": False})
        reasons = item["reasons"]
        next_actions = [ACTIONS[r] for r in reasons if r in ACTIONS]
        if not next_actions:
            next_actions = ["Independently authenticate evidence and obtain human approval"]
        items.append({
            "chain": item["chain"], "store_id": code,
            "name": item["identity"]["name"], "address": item["identity"]["address"],
            "region": item["identity"]["region"], "status": item["status"],
            "repeated_capture": "confirmed" if "not_repeated" not in reasons and
                "identity_changed" not in reasons else "unconfirmed",
            "captured_at": [c["captured_at"] for c in captures],
            "freshness": "stale" if "stale_capture" in reasons else "within_policy",
            "evidence": refs, "evidence_independently_verified": False,
            "quarantine_reasons": reasons, "next_actions": next_actions,
            "approved_for_production": False,
        })
    return {
        "schema_version": 1, "chain": result["chain"],
        "generated_at": now.isoformat(),
        "items": items, "counts": result["counts"],
        "closure_candidates": [], "approved_for_production": 0,
        "automatic_registration": False, "read_only": True,
    }


def render_json(report):
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_markdown(report):
    lines = [
        "# Offline store candidate manual review",
        "",
        "This is a read-only report. Evidence claims are unverified; no production approval.",
        "",
        "Chain: " + _cell(report["chain"]),
        "Captured report at: " + _cell(report["generated_at"]),
        "Production approvals: 0",
        "",
        "| Store ID | Name | Region | Repeated | Freshness | Status | Reasons | Evidence | Next checks |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["items"]:
        refs = ", ".join(_cell(e["source"] + ":" + e["reference"] + " (unverified)")
                         for e in item["evidence"]) or "none"
        columns = [
            item["store_id"], item["name"], item["region"],
            item["repeated_capture"], item["freshness"], item["status"],
            ", ".join(item["quarantine_reasons"]) or "none",
            refs, "; ".join(item["next_actions"]),
        ]
        lines.append("| " + " | ".join(_cell(c) for c in columns) + " |")
    lines += ["", "Capture times: " +
              ", ".join(_cell(c["captured_at"]) for c in
                        [{"captured_at": t} for t in
                         (report["items"][0]["captured_at"] if report["items"] else [])]),
              "", "No automated registration or closure decisions.", ""]
    return "\n".join(lines)
