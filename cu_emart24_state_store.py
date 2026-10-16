"""CU/emart24 proposed production state protocol. Not activated by workflows.

Fail-closed dedicated state branch and chain-specific files. Caller must provide
a disposable Git checkout and explicitly approved branch at cutover.
"""
import copy
import hashlib
import json
import subprocess
from pathlib import Path

FILES = {"cu": ("cu_stock_state.json",),
         "emart24": ("state.json", "stores.json")}
PROPOSED_BRANCH = "stock-state-cu-emart24"
class Conflict(RuntimeError): pass
class MigrationRequired(RuntimeError): pass


def check(chain, branch, paths):
    if chain not in FILES or branch != PROPOSED_BRANCH or tuple(paths) != FILES[chain]:
        raise ValueError("unauthorized chain, branch or state paths")


def git(repo, *args, check_result=True):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=True, check=check_result)


def validate(chain, bundle):
    check(chain, PROPOSED_BRANCH, bundle.keys())
    for path, data in bundle.items():
        if not isinstance(data, dict):
            raise ValueError("invalid state object: " + path)
    if chain == "cu" and not isinstance(bundle["cu_stock_state.json"].get("stores"), dict):
        raise ValueError("CU store schema invalid")
    for path in FILES[chain][:1]:
        state = bundle[path]
        if not isinstance(state.get("pending_alerts", {}), dict):
            raise ValueError("outbox schema invalid")
        if not isinstance(state.get("alert_sequence", 0), int):
            raise ValueError("sequence schema invalid")
    if chain == "emart24" and not isinstance(bundle["stores.json"], dict):
        raise ValueError("emart24 store cache invalid")
    return bundle


def fetch(repo, chain, branch=PROPOSED_BRANCH):
    check(chain, branch, FILES[chain])
    git(repo, "fetch", "origin", branch)
    sha = git(repo, "rev-parse", "FETCH_HEAD").stdout.strip()
    bundle = {}
    for path in FILES[chain]:
        raw = git(repo, "show", "FETCH_HEAD:" + path, check_result=False)
        if raw.returncode:
            raise MigrationRequired("missing authoritative state: " + path)
        bundle[path] = json.loads(raw.stdout)
    return sha, validate(chain, bundle)


def publish(repo, chain, baseline, bundle, branch=PROPOSED_BRANCH):
    validate(chain, bundle)
    check(chain, branch, bundle.keys())
    latest, remote = fetch(repo, chain, branch)
    if latest != baseline:
        raise Conflict("stale branch; scanner must refresh and rescan")
    # The publisher is allowed to run only in a clean disposable checkout.
    # A reset in an arbitrary workspace could destroy unrelated local changes.
    if git(repo, "status", "--porcelain").stdout.strip():
        raise RuntimeError("publisher requires a clean disposable checkout")
    # No force push, no silent retry; never merge a stale scanner result.
    git(repo, "reset", "--hard", latest)
    for path, value in bundle.items():
        target = Path(repo) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+"\n")
    git(repo, "add", "--", *FILES[chain])
    if git(repo, "diff", "--cached", "--quiet", check_result=False).returncode == 0:
        return latest
    git(repo, "-c", "user.name=github-actions[bot]",
        "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit", "-m", "Update " + chain + " dedicated state [skip ci]")
    result = git(repo, "push", "origin", "HEAD:refs/heads/" + branch,
                 check_result=False)
    if result.returncode:
        raise Conflict("push rejected; do not dispatch")
    committed = git(repo, "rev-parse", "HEAD").stdout.strip()
    remote_sha, _ = fetch(repo, chain, branch)
    if remote_sha != committed:
        raise Conflict("remote commit not verified; do not dispatch")
    return committed


def immutable_backup(bundle, chain, baseline):
    validate(chain, bundle)
    result = {"chain": chain, "baseline_sha": baseline, "files": {}}
    for path, value in bundle.items():
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode()
        result["files"][path] = {"sha256": hashlib.sha256(raw).hexdigest(),
                                 "bytes": len(raw)}
    return result


def claim(bundle, chain, run_id, when):
    validate(chain, bundle)
    d = copy.deepcopy(bundle)
    ids = []
    for eid, event in d[FILES[chain][0]].get("pending_alerts", {}).items():
        if event["status"] == "pending":
            event.update(status="claimed", claim_run=run_id, claimed_at=when)
            ids.append(eid)
    return d, ids


def record_attempts(bundle, chain, ids, run_id, send):
    """Invoke ONLY after caller verifies own claim commit on remote.

    An ambiguous timeout or failed outcome publish requires operator review.
    Never automatically replay a claimed event.
    """
    validate(chain, bundle)
    d = copy.deepcopy(bundle)
    for eid in ids:
        event = d[FILES[chain][0]]["pending_alerts"][eid]
        if event["status"] != "claimed" or event.get("claim_run") != run_id:
            raise ValueError("claim not owned")
        if "send_outcome" in event:
            raise ValueError("already attempted")
        try:
            send(event["message"])
        except Exception:
            event["send_outcome"] = "send_unknown"
        else:
            event["send_outcome"] = "sent_confirmed"
    return d


def unresolved(bundle, chain):
    validate(chain, bundle)
    return [eid for eid, event in bundle[FILES[chain][0]].get("pending_alerts", {}).items()
            if event["status"] == "claimed" and
            event.get("send_outcome") != "sent_confirmed"]
