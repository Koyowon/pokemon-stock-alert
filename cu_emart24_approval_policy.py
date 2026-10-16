"""Strict operator approval preflight; never mutates a repository.

This policy must be satisfied against freshly captured Git state before any
separately authorized production cutover. A passing synthetic test is not GO.
"""
from dataclasses import dataclass
from cu_emart24_legacy_migration import check_legacy, migrate, verify

STATE_PATHS=frozenset(("cu_stock_state.json","state.json","stores.json"))
WORKFLOW_PATHS=frozenset((".github/workflows/cu-stock-monitor.yml",
                          ".github/workflows/stock-monitor.yml"))

@dataclass(frozen=True)
class ApprovalFacts:
    owner_approved: bool=False
    live_api_approved: bool=False
    telegram_pilot_approved: bool=False
    old_jobs_paused: bool=False
    old_jobs_drained: bool=False
    source_sha_current: bool=False
    immutable_backup_exported: bool=False
    backup_restoration_verified: bool=False
    legacy_alerts_reconciled: bool=False
    state_branch_migrated: bool=False
    state_branch_checksums_verified: bool=False
    token_write_verified: bool=False
    branch_rules_verified: bool=False
    secrets_scope_verified: bool=False
    workflows_reviewed: bool=False
    gs25_unaffected_verified: bool=False

    def blockers(self):
        return tuple(k for k in self.__dataclass_fields__ if not getattr(self,k))

    def require_go(self):
        missing=self.blockers()
        if missing:
            raise RuntimeError("NO-GO: "+", ".join(missing))
        return True


def validate_readonly_snapshot(source, commit, blobs):
    check_legacy(source)
    staged,manifest=migrate(source,commit,blobs)
    verify(source,staged,manifest)
    return {
        "decision":"NO-GO",
        "source_commit":commit,
        "source_blob_shas":dict(blobs),
        "source_sha256":dict(manifest["source_sha256"]),
        "staged_sha256":dict(manifest["migrated_sha256"]),
        "cu_stores":manifest["cu_store_count"],
        "emart24_cached_stores":manifest["emart24_cache_count"],
        "historical_delivery_reconstructed":False,
        "state_files_to_migrate":sorted(STATE_PATHS),
        "workflow_files_to_replace":sorted(WORKFLOW_PATHS),
    }
