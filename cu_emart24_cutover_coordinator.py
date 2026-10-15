"""Production cutover coordinator candidate. Not wired into scheduled workflows.

Caller must hold exclusive workflow concurrency for CU+emart24 and provide a
verified state-branch checkout. The send callback is injected, never loaded
from Telegram environment by this module.
"""
from datetime import datetime,timezone
from cu_emart24_state_store import fetch,publish,claim,record_attempts,unresolved
from cu_emart24_scan_adapter import scan_with_snapshot


def scan_commit(repo,chain):
    baseline,remote=fetch(repo,chain)
    updated=scan_with_snapshot(chain,remote)
    return publish(repo,chain,baseline,updated)


def claim_and_dispatch(repo,chain,run_id,send):
    baseline,remote=fetch(repo,chain)
    when=datetime.now(timezone.utc).isoformat()
    claimed,ids=claim(remote,chain,run_id,when)
    claim_sha=publish(repo,chain,baseline,claimed)
    verified_sha,verified_doc=fetch(repo,chain)
    if claim_sha!=verified_sha:
        raise RuntimeError("claim not verified; no dispatch")
    if not ids:
        return unresolved(verified_doc,chain)
    # These IDs exist only in this process after successful own claim commit.
    # A crashed runner must never reconstruct them from claimed remote records.
    attempted=record_attempts(verified_doc,chain,ids,run_id,send)
    publish(repo,chain,claim_sha,attempted)
    return unresolved(attempted,chain)
