"""Read-only preflight policy for CU/emart24 production cutover.

This module never writes state or calls a provider. It fails closed until
operator-supplied facts are explicitly verified at deployment time.
"""
from dataclasses import dataclass
from cu_emart24_state_store import FILES,validate

@dataclass(frozen=True)
class Preflight:
    old_jobs_paused: bool=False
    in_flight_drained: bool=False
    backup_exported: bool=False
    backup_sha_verified: bool=False
    migrated_branch_exists: bool=False
    migration_verified: bool=False
    branch_write_permission_verified: bool=False
    secrets_dispatch_only: bool=False
    live_approval: bool=False

    def blockers(self):
        return [field for field in self.__dataclass_fields__ if not getattr(self,field)]

    def require_ready(self):
        missing=self.blockers()
        if missing:
            raise RuntimeError("NO-GO: "+", ".join(missing))
        return True


def audit_source(source, main_sha, expected_blob_shas):
    """Validate *read-only* source shape; never assume legacy outbox exists."""
    if not main_sha or set(expected_blob_shas)!=set(source):
        raise ValueError("missing immutable source baseline")
    if set(source)!={"cu_stock_state.json","state.json","stores.json"}:
        raise ValueError("missing or unexpected production state file")
    for chain in FILES:
        validate(chain,{p:source[p] for p in FILES[chain]})
    cu=source["cu_stock_state.json"]
    em=source["state.json"]
    cache=source["stores.json"]
    if not isinstance(cache.get("stores"),dict):
        raise ValueError("emart24 store cache schema invalid")
    if not isinstance(cu["stores"],dict):
        raise ValueError("CU store schema invalid")
    # Legacy states without outbox are allowed only as an explicit migration,
    # not evidence that old direct-send notifications have been reconciled.
    return {
        "main_sha":main_sha,
        "source_blobs":dict(expected_blob_shas),
        "cu_stores":len(cu["stores"]),
        "emart24_cache_stores":len(cache["stores"]),
        "cu_outbox_present":"pending_alerts" in cu,
        "emart24_outbox_present":"pending_alerts" in em,
        "cu_sequence_present":"alert_sequence" in cu,
        "emart24_sequence_present":"alert_sequence" in em,
        "migration_requires_operator_reconciliation":(
            "pending_alerts" not in cu or "pending_alerts" not in em
        ),
    }
