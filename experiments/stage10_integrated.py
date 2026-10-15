"""Stage10 single-workflow isolated Git publisher and mock dispatcher.

No external API/Telegram. All network interactions are performed by the
containing GitHub Actions workflow's git push/fetch on an isolated test branch.
"""
import copy
import json
from pathlib import Path

from experiments.isolated_state_outbox import claim_event
from experiments.stage9_stability import claimed_audit, preserve_alerts


def publish_scanner_output(probe_path, scanned):
    """Persist synthetic scanner output while preserving prior events."""
    p=Path(probe_path)
    if p.exists():
        old=json.loads(p.read_text())
        assert old.get("synthetic") is True
        for chain in ("cu","emart24"):
            scanned["chains"][chain]["state"]=preserve_alerts(
                old["chains"][chain]["state"],scanned["chains"][chain]["state"]
            )
    assert scanned.get("telegram_calls")==0
    p.write_text(json.dumps(scanned,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    return scanned


def claim_pending(probe_path):
    p=Path(probe_path)
    d=json.loads(p.read_text())
    assert d["synthetic"] is True and d["telegram_calls"]==0
    claimed=[]
    for chain in ("cu","emart24"):
        v=d["chains"][chain]
        eid=v["eid"]
        if v["state"]["pending_alerts"][eid]["status"]=="pending":
            v["state"]=claim_event(v["state"],eid)
            claimed.append((chain,eid))
    p.write_text(json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    return claimed


def mock_dispatch_from_committed(committed):
    """Call only after Git claim push and remote fetch verification."""
    assert committed["synthetic"] is True and committed["telegram_calls"]==0
    attempts=[]
    for chain in ("cu","emart24"):
        v=committed["chains"][chain]
        if v["state"]["pending_alerts"][v["eid"]]["status"]=="claimed":
            attempts.append((chain,v["eid"]))
    return attempts


def audit(committed):
    return {chain:claimed_audit(v["state"]) for chain,v in committed["chains"].items()}
