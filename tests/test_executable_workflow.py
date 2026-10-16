import os
import unittest
from unittest.mock import patch
import cu_emart24_live_entrypoint as entry
from cu_emart24_executable_workflow import proposed
from cu_emart24_migration_plan import prepare,verify,rollback_plan

class ExecutableProposal(unittest.TestCase):
    def test_workflows_have_real_steps_but_are_disabled(self):
        workflows=proposed()
        self.assertEqual(set(workflows),{"cu","emart24"})
        for chain,body in workflows.items():
            self.assertIn("git worktree add",body)
            self.assertIn("--phase scan",body)
            self.assertIn("--phase dispatch",body)
            self.assertIn("if: false",body)
            self.assertNotIn("schedule:",body)
            self.assertIn("stock-state-cu-emart24",body)
            self.assertIn("CU_EMART24_LIVE_APPROVED",body)
            self.assertIn("TELEGRAM_BOT_TOKEN",body)
            self.assertNotIn("state_push_publisher.py",body)
            self.assertNotIn("gs25",body.lower())
    def test_unapproved_entrypoint_rejects_before_io(self):
        with patch.dict(os.environ,{"CU_EMART24_LIVE_APPROVED":"0"}):
            with patch.object(entry,"fetch",side_effect=AssertionError("network forbidden")):
                with self.assertRaises(RuntimeError):entry.scan("/tmp/none","cu")
                with self.assertRaises(RuntimeError):entry.claim_and_send("/tmp/none","cu","run")
    def test_claim_commit_conflict_prevents_real_send(self):
        state={"cu_stock_state.json":{"stores":{},"pending_alerts":{"e":{"status":"pending","message":"fake"}},"alert_sequence":1}}
        env={"CU_EMART24_LIVE_APPROVED":"1","GITHUB_REPOSITORY":"Koyowon/pokemon-stock-alert","GITHUB_REF":"refs/heads/main"}
        with patch.dict(os.environ,env), \
             patch.object(entry,"fetch",return_value=("sha",state)), \
             patch.object(entry,"publish",side_effect=RuntimeError("CAS failed")), \
             patch.object(entry,"telegram",side_effect=AssertionError("send blocked")):
            with self.assertRaises(RuntimeError):entry.claim_and_send("/tmp/none","cu","run")
    def test_backup_restore_plan_is_readonly(self):
        source={"cu_stock_state.json":{"stores":{},"pending_alerts":{}},
                "state.json":{"pending_alerts":{}},
                "stores.json":{}}
        manifest,copy=prepare(source,"abcdef123456")
        self.assertTrue(verify(manifest,copy))
        plan=rollback_plan(manifest,{"cu":[],"emart24":[]})
        self.assertFalse(plan["force_push_allowed"])
        self.assertFalse(plan["auto_retry_claimed"])
if __name__=="__main__":unittest.main()
