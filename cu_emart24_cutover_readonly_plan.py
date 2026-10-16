"""Pure offline cutover plan; never performs Git writes, API calls or Telegram sends."""
from dataclasses import dataclass
from cu_emart24_legacy_migration import migrate,verify,rollback_snapshot

STATE=("cu_stock_state.json","state.json","stores.json")
WORKFLOWS=(".github/workflows/cu-stock-monitor.yml",".github/workflows/stock-monitor.yml")

@dataclass(frozen=True)
class FreezeEvidence:
    schedules_disabled: bool=False
    in_flight_jobs_drained: bool=False
    source_sha_rechecked: bool=False
    source_blob_shas_rechecked: bool=False
    raw_backups_exported: bool=False
    raw_sha256_verified: bool=False
    restore_in_disposable_clone_passed: bool=False
    github_token_write_verified: bool=False
    state_branch_rules_verified: bool=False
    secrets_dispatch_only_verified: bool=False
    first_scan_suppression_reviewed: bool=False
    owner_authorized_state_migration: bool=False
    owner_authorized_workflow_replacement: bool=False
    owner_authorized_live_pilot: bool=False

    def require_go(self):
        missing=[name for name in self.__dataclass_fields__ if not getattr(self,name)]
        if missing:
            raise RuntimeError("NO-GO: "+", ".join(missing))
        return True


def offline_plan(source,main_sha,blobs):
    """Preserves legacy alerts and all quantities; returns *in-memory* copies."""
    migrated,manifest=migrate(source,main_sha,blobs)
    verify(source,migrated,manifest)
    restored=rollback_snapshot(source,manifest)
    if restored!=source:
        raise ValueError("rollback mismatch")
    return {
        "status":"NO-GO",
        "source_main_sha":main_sha,
        "source_git_blobs":dict(blobs),
        "source_json_sha256":dict(manifest["source_sha256"]),
        "staged_json_sha256":dict(manifest["migrated_sha256"]),
        "backup_paths":list(STATE)+list(WORKFLOWS),
        "restore_validated_in_memory":True,
        "raw_backup_exported":False,
        "initial_outbox_alerts":0,
        "legacy_delivery_reconstructed":False,
        "first_scan_rule":"do not dispatch until operator confirms no replay of existing positive stock",
    }
