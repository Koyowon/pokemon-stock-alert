import copy
import unittest
from unittest.mock import patch
import cu_emart24_migration_plan as mig
import cu_emart24_workflow_proposal as wf
import cu_emart24_state_store as state

class PredeployAcceptance(unittest.TestCase):
    def setUp(self):
        self.source={
            "cu_stock_state.json":{"stores":{"S":{"stock":3}},"pending_alerts":{"cu-1":{"status":"claimed","message":"m","claim_run":"old"}},"alert_sequence":1},
            "state.json":{"emart24|S|8800286275732":4,"pending_alerts":{"em-1":{"status":"pending","message":"m"}},"alert_sequence":1},
            "stores.json":{"stores":{"S":{"name":"synthetic"}}}}
    def test_migration_preserves_every_byte_of_logical_state(self):
        original=copy.deepcopy(self.source)
        manifest,staged=mig.prepare(self.source,"abcdef123456")
        self.assertTrue(mig.verify(manifest,staged))
        self.assertEqual(self.source,original)
        self.assertEqual(staged,original)
        self.assertEqual(set(manifest["files"]),set(original))
        staged["state.json"]["emart24|S|8800286275732"]=0
        with self.assertRaises(ValueError):mig.verify(manifest,staged)
    def test_readonly_rollback_keeps_claims_and_gs25(self):
        manifest,_=mig.prepare(self.source,"abcdef123456")
        claims={"cu":["cu-1"]}
        plan=mig.rollback_plan(manifest,claims)
        self.assertFalse(plan["force_push_allowed"])
        self.assertFalse(plan["auto_retry_claimed"])
        self.assertTrue(plan["retain_gs25"])
        self.assertEqual(plan["reconcile_claims"],claims)
    def test_workflow_drafts_are_disabled_and_scoped(self):
        targets=wf.targets()
        self.assertEqual(set(targets),{".github/workflows/cu-stock-monitor.yml",".github/workflows/stock-monitor.yml"})
        for body in targets.values():
            self.assertIn("if: false",body)
            self.assertNotIn("schedule:",body)
            self.assertNotIn("state_push_publisher.py",body)
            self.assertNotIn("gs25",body.lower())
    def test_stale_git_state_blocks_before_reset(self):
        bundle={"cu_stock_state.json":self.source["cu_stock_state.json"]}
        with patch.object(state,"fetch",return_value=("new",bundle)):
            with self.assertRaises(state.Conflict):
                state.publish("/tmp/not-a-repo","cu","old",bundle)
if __name__=="__main__": unittest.main()
