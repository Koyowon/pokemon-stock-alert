"""Isolated CU/emart24 candidate runner. No live inventory or Telegram enabled."""
import contextlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import cu_stock_monitor as cu
import monitor as em
from cutover_candidate import FILES,fetch_bundle,publish_bundle,claim_bundle,outcome_bundle,audit_bundle


def scanner(chain,bundle,mock_only=True):
    if not mock_only:
        raise RuntimeError("live scanning not authorized")
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        for path,obj in bundle.items():
            (root/path).write_text(json.dumps(obj,ensure_ascii=False))
        if chain=="cu":
            item={"code":"FAKE-CU-01","name":"테스트점","address":"충청남도 아산시 테스트로 12",
                  "city":"아산","stock":3}
            with patch.object(cu,"STATE_FILE",root/"cu_stock_state.json"), \
                 patch.object(cu,"POINTS",{"아산":[(36.79,127.0)]}), \
                 patch.object(cu,"query",return_value=[item]), \
                 patch.object(cu,"telegram",side_effect=AssertionError("blocked")), \
                 patch("unified_settings.enabled",return_value={"asan"}), \
                 patch("cu_asan_registry.summarize_observations",return_value=None):
                cu.main()
        elif chain=="emart24":
            stores={"FAKE-EM-01":{"name":"가상점","address":"충청남도 아산시 테스트로 20"}}
            with patch.object(em,"STATE_FILE",root/"state.json"), \
                 patch.object(em,"STORES_FILE",root/"stores.json"), \
                 patch.object(em,"get_stores",return_value=stores), \
                 patch.object(em,"stock",return_value=({"FAKE-EM-01":4},{"FAKE-EM-01":"OK"})), \
                 patch.object(em,"notify",side_effect=AssertionError("blocked")), \
                 patch("unified_settings.enabled",return_value={"asan"}):
                em.main()
        else:
            raise ValueError("unknown chain")
        result={path:json.loads((root/path).read_text()) for path in FILES[chain]}
    for eid,event in bundle[FILES[chain][0]].get("pending_alerts",{}).items():
        if result[FILES[chain][0]].get("pending_alerts",{}).get(eid)!=event:
            raise ValueError("scanner lost previously claimed or pending event")
    return result


def cycle(worktree,chain,run_id,when,send):
    """CAS publish scanner result, CAS claim, send owned only, audit outcome."""
    sha,base=fetch_bundle(worktree,chain)
    scanned=scanner(chain,base)
    published=publish_bundle(worktree,chain,sha,scanned)
    sha,latest=fetch_bundle(worktree,chain)
    assert sha==published
    claimed,ids=claim_bundle(latest,chain,run_id,when)
    claim_sha=publish_bundle(worktree,chain,sha,claimed)
    sha,committed=fetch_bundle(worktree,chain)
    if sha!=claim_sha:
        raise RuntimeError("claim commit not verified")
    if not ids:
        return []
    results=outcome_bundle(committed,chain,ids,run_id,send)
    publish_bundle(worktree,chain,sha,results)
    return audit_bundle(results,chain)
