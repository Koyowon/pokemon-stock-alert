"""Stage 12 isolated candidate: scan real CU/emart24 entrypoints from remote state.

Only synthetic inventory and mock Telegram. State writes are delegated to a
separate, allowlisted Git worktree. This module NEVER calls GitHub or Telegram.
"""
import contextlib
import copy
import io
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import cu_stock_monitor as cu
import monitor as em


CHAINS = ("cu", "emart24")


def blank():
    return {"schema": 12, "synthetic": True, "chains": {
        "cu": {"state": {"stores": {}}},
        "emart24": {"state": {}, "stores": {}},
    }, "outcomes": {}, "telegram_calls": 0}


def validate(doc):
    if doc.get("synthetic") is not True or doc.get("schema") != 12 or doc.get("telegram_calls") != 0:
        raise ValueError("not a stage12 synthetic state")
    if set(doc["chains"]) != set(CHAINS):
        raise ValueError("chain mismatch")
    return doc


def scan_from_latest(remote):
    """Use remote branch snapshot as BOTH scanner baselines; no real network."""
    remote = validate(copy.deepcopy(remote))
    out = copy.deepcopy(remote)
    with tempfile.TemporaryDirectory(prefix="stage12-mock-") as d:
        root = Path(d)
        cp = root / "cu.json"
        cp.write_text(json.dumps(remote["chains"]["cu"]["state"]))
        item = {"code": "FAKE-CU-01", "name": "테스트점",
                "address": "충청남도 아산시 테스트로 12",
                "city": "아산", "stock": 3}
        with patch.object(cu, "STATE_FILE", cp), \
             patch.object(cu, "POINTS", {"아산": [(36.79, 127.0)]}), \
             patch.object(cu, "query", return_value=[item]), \
             patch.object(cu, "telegram", side_effect=AssertionError("CU real send blocked")), \
             patch("unified_settings.enabled", return_value={"asan"}), \
             patch("cu_asan_registry.summarize_observations", return_value=None), \
             contextlib.redirect_stdout(io.StringIO()):
            cu.main()
        out["chains"]["cu"]["state"] = json.loads(cp.read_text())
        ep = root / "em.json"
        sp = root / "stores.json"
        ep.write_text(json.dumps(remote["chains"]["emart24"]["state"]))
        sp.write_text(json.dumps(remote["chains"]["emart24"].get("stores", {})))
        fake = {"FAKE-EM-01": {"name": "가상점",
                              "address": "충청남도 아산시 테스트로 20"}}
        with patch.object(em, "STATE_FILE", ep), \
             patch.object(em, "STORES_FILE", sp), \
             patch.object(em, "get_stores", return_value=fake), \
             patch.object(em, "stock", return_value=({"FAKE-EM-01": 4}, {"FAKE-EM-01": "OK"})), \
             patch.object(em, "notify", side_effect=AssertionError("emart real send blocked")), \
             patch("unified_settings.enabled", return_value={"asan"}), \
             contextlib.redirect_stdout(io.StringIO()):
            em.main()
        out["chains"]["emart24"]["state"] = json.loads(ep.read_text())
        out["chains"]["emart24"]["stores"] = json.loads(sp.read_text())
    for chain in CHAINS:
        previous = remote["chains"][chain]["state"].get("pending_alerts", {})
        updated = out["chains"][chain]["state"].get("pending_alerts", {})
        for eid, event in previous.items():
            if updated.get(eid) != event:
                raise ValueError("scanner altered prior event")
    return validate(out)


def claim_new(doc, run_id, when=None):
    """Return updated document and ONLY newly claimed IDs."""
    d = validate(copy.deepcopy(doc))
    when = when or datetime.now(timezone.utc).isoformat()
    claimed = []
    for chain in CHAINS:
        for eid, event in d["chains"][chain]["state"].get("pending_alerts", {}).items():
            if event["status"] == "pending":
                event["status"] = "claimed"
                event["claimed_at"] = when
                event["claim_run"] = run_id
                claimed.append((chain, eid))
    return d, claimed


def record_mock_outcome(doc, claim_run, claimed_ids):
    """Record only IDs from THIS successful remote claim commit."""
    d = validate(copy.deepcopy(doc))
    for chain, eid in claimed_ids:
        event = d["chains"][chain]["state"]["pending_alerts"][eid]
        if event["status"] != "claimed" or event.get("claim_run") != claim_run:
            raise ValueError("not claimed by this run")
        key = chain + ":" + eid
        if key in d["outcomes"]:
            raise ValueError("duplicate mock send")
        d["outcomes"][key] = {"status": "mock_sent", "claim_run": claim_run}
    return d


def audit(doc):
    d = validate(doc)
    return [(chain, eid) for chain in CHAINS
            for eid, e in d["chains"][chain]["state"].get("pending_alerts", {}).items()
            if e["status"] == "claimed" and
            d["outcomes"].get(chain + ":" + eid, {}).get("status") != "mock_sent"]
