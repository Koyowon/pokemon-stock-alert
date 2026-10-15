"""CU/emart24 candidate state protocol (not enabled in operating workflows).

Reads/writes exact chain files on a dedicated Git state branch, never main.
Git remote/branch selection is restricted; dispatcher callback must be separately
authorized and is NEVER wired to real Telegram here.
"""
import copy
import json
from pathlib import Path
from experiments.stage13_state_publisher import git, PublishConflict

BRANCH="validation/cu-emart24-cutover-state-20261016"
FILES={"cu":("cu_stock_state.json",),"emart24":("state.json","stores.json")}
BASELINES={"cu":{"stores":{}},"emart24":{}}


def check(chain, branch, paths):
    if branch!=BRANCH or chain not in FILES or tuple(paths)!=FILES[chain]:
        raise ValueError("unapproved branch/chain/path")
    return True


def fetch_bundle(worktree,chain,branch=BRANCH):
    paths=FILES[chain]
    check(chain,branch,paths)
    git("fetch","origin",branch,cwd=worktree)
    sha=git("rev-parse","FETCH_HEAD",cwd=worktree).stdout.strip()
    result={}
    for path in paths:
        found=git("show","FETCH_HEAD:"+path,cwd=worktree,check=False)
        if found.returncode:
            raise RuntimeError("state migration missing: "+path)
        result[path]=json.loads(found.stdout)
    return sha,result


def publish_bundle(worktree,chain,expected_sha,bundle,branch=BRANCH):
    check(chain,branch,tuple(bundle))
    current,_=fetch_bundle(worktree,chain,branch)
    if current!=expected_sha:
        raise PublishConflict("state branch changed; discard scanner result and rescan")
    git("reset","--hard",current,cwd=worktree)
    for path,obj in bundle.items():
        (Path(worktree)/path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    git("add","--",*FILES[chain],cwd=worktree)
    changed=git("diff","--cached","--quiet",cwd=worktree,check=False)
    if changed.returncode==0:
        return current
    git("-c","user.name=github-actions[bot]",
        "-c","user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit","-m","candidate: "+chain+" state [skip ci]",cwd=worktree)
    pushed=git("push","origin","HEAD:refs/heads/"+branch,cwd=worktree,check=False)
    if pushed.returncode:
        raise PublishConflict("push rejected; no dispatch")
    new_sha=git("rev-parse","HEAD",cwd=worktree).stdout.strip()
    git("fetch","origin",branch,cwd=worktree)
    verified=git("rev-parse","FETCH_HEAD",cwd=worktree).stdout.strip()
    if verified!=new_sha:
        raise PublishConflict("unverified remote state; no dispatch")
    return new_sha


def claim_bundle(bundle,chain,run_id,when):
    """One immutable claim owner per event, never reclaim claimed."""
    result=copy.deepcopy(bundle)
    key=FILES[chain][0]
    ids=[]
    for eid,event in result[key].get("pending_alerts",{}).items():
        if event["status"]=="pending":
            event.update(status="claimed",claimed_at=when,claim_run=run_id)
            ids.append(eid)
    return result,ids


def outcome_bundle(bundle,chain,ids,run_id,send):
    """Called only with events from verified successful claim commit.

    Record result in chain state. If subsequent Git commit fails, claims remain
    ambiguous and MUST NOT be automatically retried.
    """
    result=copy.deepcopy(bundle)
    state=result[FILES[chain][0]]
    for eid in ids:
        event=state["pending_alerts"][eid]
        if event["status"]!="claimed" or event.get("claim_run")!=run_id:
            raise ValueError("claim not owned")
        if "send_outcome" in event:
            raise ValueError("already attempted")
        try:
            send(event["message"])
        except Exception:
            event["send_outcome"]="send_unknown"
        else:
            event["send_outcome"]="mock_sent"
    return result


def audit_bundle(bundle,chain):
    state=bundle[FILES[chain][0]]
    return [eid for eid,e in state.get("pending_alerts",{}).items()
            if e["status"]=="claimed" and e.get("send_outcome")!="mock_sent"]


def prepare_backup(bundle,chain):
    """Pure, immutable backup payload and digest for operator export."""
    import hashlib
    check(chain,BRANCH,tuple(bundle))
    data={k:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
          for k,v in bundle.items()}
    return {k:{"json":value,"sha256":hashlib.sha256(value.encode()).hexdigest()}
            for k,value in data.items()}
