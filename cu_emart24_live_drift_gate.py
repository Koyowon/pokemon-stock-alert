"""Fail closed when the read-only operating baseline changes.

A changed main SHA requires rebaseline even when workflow blob SHAs match.
Never invokes a Git write, provider API or Telegram.
"""
from dataclasses import dataclass

PINNED_MAIN="08849cf0214ae7264f25aed5f3c17885e64a9ecd"
PINNED_BLOBS={
"cu_stock_state.json":"2dbb1c0abd9adcbf613d05711c0b066a79dcdd20",
"state.json":"53941d3e6dcfbc83270a715652e6bae5a6af0dc0",
"stores.json":"8e3940981f394cc0d0dc3213840116514fe997e7",
".github/workflows/cu-stock-monitor.yml":"9fcc1c923ad335bde791cbc512242e1b2f303708",
".github/workflows/stock-monitor.yml":"05ecbbc78bb03311a69895bca775f5651422569d",
}

@dataclass(frozen=True)
class ReadonlyStatus:
    main_sha:str
    blobs:dict
    protected:bool
    state_branch_exists:bool
    actions_write_verified:bool=False
    detailed_rules_verified:bool=False
    actual_backup_verified:bool=False
    first_alert_policy_approved:bool=False

    def blockers(self):
        problems=[]
        if self.main_sha!=PINNED_MAIN:problems.append("main_commit_drift")
        for name,sha in PINNED_BLOBS.items():
            if self.blobs.get(name)!=sha:problems.append("blob_drift:"+name)
        if not self.protected:problems.append("main_not_protected")
        if not self.state_branch_exists:problems.append("dedicated_state_branch_absent")
        for name in ("actions_write_verified","detailed_rules_verified",
                     "actual_backup_verified","first_alert_policy_approved"):
            if not getattr(self,name):problems.append(name)
        return problems

    def require_go(self):
        problems=self.blockers()
        if problems:raise RuntimeError("NO-GO: "+", ".join(problems))
        return True
