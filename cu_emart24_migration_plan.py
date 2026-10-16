"""Cutover backup/migration/rollback PREPARATION (read-only, no Git writes).

Production source is supplied by an operator from an immutable snapshot.
This module never fetches remote state or sends notifications.
"""
import copy
import hashlib
import json
from cu_emart24_state_store import FILES,validate,immutable_backup


def canonical(doc):
    return json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()


def prepare(source,baseline_sha):
    """Build immutable migration manifest and separate deep-copied target payload."""
    if not baseline_sha or len(baseline_sha)<7:
        raise ValueError("baseline SHA required")
    expected={}
    staged={}
    for chain in ("cu","emart24"):
        files={path:copy.deepcopy(source[path]) for path in FILES[chain]}
        validate(chain,files)
        expected[chain]=immutable_backup(files,chain,baseline_sha)
        staged.update(files)
    return {"baseline_sha":baseline_sha,"files":{
        path:{"sha256":hashlib.sha256(canonical(doc)).hexdigest(),
              "bytes":len(canonical(doc))} for path,doc in staged.items()
    }},staged


def verify(manifest,staged):
    if set(staged)!=set(manifest["files"]):
        raise ValueError("migration file set changed")
    for path,doc in staged.items():
        raw=canonical(doc)
        expected=manifest["files"][path]
        if hashlib.sha256(raw).hexdigest()!=expected["sha256"] or len(raw)!=expected["bytes"]:
            raise ValueError("state backup checksum mismatch: "+path)
    validate("cu",{p:staged[p] for p in FILES["cu"]})
    validate("emart24",{p:staged[p] for p in FILES["emart24"]})
    return True


def rollback_plan(manifest,current_claims):
    """Generate instructions, never overwrite a branch or replay a claimed alert."""
    if not isinstance(current_claims,dict):
        raise ValueError("audit snapshot required")
    return {
        "action":"manual_approval_required",
        "disable_only":["cu-stock-monitor","stock-monitor"],
        "retain_gs25":True,
        "backup_sha":manifest["baseline_sha"],
        "verify_files":list(manifest["files"]),
        "reconcile_claims":copy.deepcopy(current_claims),
        "force_push_allowed":False,
        "auto_retry_claimed":False,
    }
