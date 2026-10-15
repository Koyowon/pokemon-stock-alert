"""Proposed CU/emart24 production scanner adapter.

No network calls here. Scanners use their normal API only when explicitly run
by an approved production workflow. Inject state/cache paths to avoid using
the repository's operational files as an implicit baseline.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import cu_stock_monitor as cu
import monitor as em
from cu_emart24_state_store import FILES, validate


def scan_with_snapshot(chain, snapshot):
    """Scan authoritative snapshot; caller must CAS publish or discard it.

    No Telegram secret is read by this adapter. Existing scanners only queue
    alerts; their send functions are blocked defensively.
    """
    validate(chain,snapshot)
    with tempfile.TemporaryDirectory(prefix="cu-emart24-snapshot-") as d:
        root=Path(d)
        paths={}
        for path,doc in snapshot.items():
            local=root/path
            local.parent.mkdir(parents=True,exist_ok=True)
            local.write_text(json.dumps(doc,ensure_ascii=False),encoding="utf-8")
            paths[path]=local
        def blocked(*args,**kwargs):
            raise RuntimeError("Telegram disabled in scan stage")
        if chain=="cu":
            with patch.object(cu,"STATE_FILE",paths["cu_stock_state.json"]), \
                 patch.object(cu,"telegram",blocked):
                cu.main()
        elif chain=="emart24":
            with patch.object(em,"STATE_FILE",paths["state.json"]), \
                 patch.object(em,"STORES_FILE",paths["stores.json"]), \
                 patch.object(em,"notify",blocked):
                em.main()
        else:
            raise ValueError("unsupported chain")
        output={path:json.loads(local.read_text(encoding="utf-8"))
                for path,local in paths.items()}
    validate(chain,output)
    before=snapshot[FILES[chain][0]].get("pending_alerts",{})
    after=output[FILES[chain][0]].get("pending_alerts",{})
    for eid,event in before.items():
        if after.get(eid)!=event:
            raise ValueError("existing alert altered by scanner")
    return output
