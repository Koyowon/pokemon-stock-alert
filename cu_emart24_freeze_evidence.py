"""Pure offline freeze/drain evidence gate. Never invokes GitHub actions."""
from dataclasses import dataclass

TARGET_WORKFLOWS=frozenset(("cu-stock-monitor.yml","stock-monitor.yml"))
PROTECTED_WORKFLOWS=frozenset(("gs25-stock-monitor.yml",))

@dataclass(frozen=True)
class Freeze:
    owner_approved:bool=False
    cu_disabled:bool=False
    emart24_disabled:bool=False
    cu_inflight_zero:bool=False
    emart24_inflight_zero:bool=False
    manual_dispatch_blocked:bool=False
    gs25_untouched:bool=False
    pinned_main_rechecked:bool=False
    five_blobs_rechecked:bool=False
    raw_backup_verified:bool=False
    disposable_restore_verified:bool=False
    write_permissions_verified:bool=False
    branch_rules_verified:bool=False

    def blockers(self):
        return tuple(k for k in self.__dataclass_fields__ if not getattr(self,k))
    def require_ready(self):
        missing=self.blockers()
        if missing:raise RuntimeError("NO-GO: "+", ".join(missing))
        return True


def review_running_jobs(jobs):
    """Given read-only GitHub Actions run records, reject any active CU/emart24 run.

    Never treats unrelated GS25, Pages or registration workflows as blockers.
    Caller must fetch *all pages* of relevant jobs and avoid racing new dispatch.
    """
    active=[]
    for job in jobs:
        workflow=job.get("workflow_path","").split("/")[-1]
        if workflow in TARGET_WORKFLOWS and job.get("status") not in ("completed",):
            active.append((workflow,job.get("id")))
    return active


def require_frozen(evidence,jobs):
    evidence.require_ready()
    active=review_running_jobs(jobs)
    if active:raise RuntimeError("NO-GO: in-flight CU/emart24 jobs "+repr(active))
    return True
