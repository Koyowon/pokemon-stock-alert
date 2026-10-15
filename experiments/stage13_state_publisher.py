"""Stage13 isolated state-branch publisher and claimed-event dispatcher candidate.

No real Telegram, API calls or GitHub credentials. Git operations use an
explicit injected runner. This is NOT a production-ready sender.
"""
import copy
import json
import subprocess
from pathlib import Path
from experiments.stage12_candidate import validate, claim_new, audit

STATE_BRANCH = "validation/pr2-stage13-state-20261016"
STATE_PREFIX = "experiments/stage13_probe_"


class PublishConflict(RuntimeError):
    pass


def validate_target(branch, path):
    if branch != STATE_BRANCH or not path.startswith(STATE_PREFIX) or not path.endswith(".json"):
        raise ValueError("non-isolated state destination")
    if "/" in path[len(STATE_PREFIX):]:
        raise ValueError("nested state path rejected")


def git(*args, cwd, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check,
                          capture_output=True, text=True)


def remote_state(worktree, branch, path):
    validate_target(branch, path)
    git("fetch", "origin", branch, cwd=worktree)
    sha=git("rev-parse", "FETCH_HEAD", cwd=worktree).stdout.strip()
    existing=git("show", "FETCH_HEAD:"+path, cwd=worktree, check=False)
    if existing.returncode:
        return sha, None
    return sha, validate(json.loads(existing.stdout))


def publish_if_unchanged(worktree, branch, path, expected_sha, document, message):
    """Fail closed on a stale baseline; no force push, no automatic rebase."""
    validate_target(branch, path)
    validate(document)
    sha,_=remote_state(worktree, branch, path)
    if sha != expected_sha:
        raise PublishConflict("remote branch advanced; reload and recompute")
    git("reset", "--hard", sha, cwd=worktree)
    target=Path(worktree)/path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    git("add", "--", path, cwd=worktree)
    staged=git("diff", "--cached", "--quiet", cwd=worktree, check=False)
    if staged.returncode==0:
        return sha
    git("-c","user.name=github-actions[bot]",
        "-c","user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit","-m",message+" [skip ci]",cwd=worktree)
    pushed=git("push","origin","HEAD:refs/heads/"+branch,cwd=worktree,check=False)
    if pushed.returncode:
        raise PublishConflict("non-fast-forward or push failure; no send")
    new_sha=git("rev-parse","HEAD",cwd=worktree).stdout.strip()
    remote_sha,_=remote_state(worktree,branch,path)
    if remote_sha!=new_sha:
        raise PublishConflict("remote verification failed; no send")
    return new_sha


def claim_for_run(doc, run_id, when):
    return claim_new(doc,run_id,when)


def dispatch_claimed(doc, claimed_ids, run_id, send):
    """Send ONLY after caller verified the unique claim commit on remote."""
    d=validate(copy.deepcopy(doc))
    results={}
    for chain,eid in claimed_ids:
        e=d["chains"][chain]["state"]["pending_alerts"][eid]
        if e.get("claim_run")!=run_id or e.get("status")!="claimed":
            raise ValueError("unowned claim")
        key=chain+":"+eid
        if key in d["outcomes"]:
            raise ValueError("already attempted")
        try:
            send(e["message"])
        except Exception:
            results[key]={"status":"send_unknown","claim_run":run_id}
        else:
            results[key]={"status":"mock_sent","claim_run":run_id}
    d["outcomes"].update(results)
    return d


def missing_or_uncertain(doc):
    d=validate(doc)
    return [(chain,eid) for chain in ("cu","emart24")
            for eid,e in d["chains"][chain]["state"].get("pending_alerts",{}).items()
            if e["status"]=="claimed" and
            d["outcomes"].get(chain+":"+eid,{}).get("status")!="mock_sent"]
