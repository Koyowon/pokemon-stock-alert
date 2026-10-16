import unittest
from cu_emart24_live_drift_gate import ReadonlyStatus,PINNED_MAIN,PINNED_BLOBS
class DriftGateAcceptance(unittest.TestCase):
    def test_current_main_and_cu_blob_drift_block(self):
        b=dict(PINNED_BLOBS)
        b["cu_stock_state.json"]="8736cbd47da11a84b5001a07ddd0949d44dc4ed3"
        s=ReadonlyStatus("78fafed9ddd84ca1a8aafc3b16158b636c86d40a",b,True,False)
        self.assertIn("main_commit_drift",s.blockers())
        self.assertIn("blob_drift:cu_stock_state.json",s.blockers())
        with self.assertRaisesRegex(RuntimeError,"NO-GO"):s.require_go()
    def test_permissions_and_backup_not_assumed(self):
        s=ReadonlyStatus(PINNED_MAIN,dict(PINNED_BLOBS),True,True)
        self.assertIn("actions_write_verified",s.blockers())
        self.assertIn("actual_backup_verified",s.blockers())
        self.assertIn("first_alert_policy_approved",s.blockers())
    def test_all_verified_only_then_go(self):
        s=ReadonlyStatus(PINNED_MAIN,dict(PINNED_BLOBS),True,True,True,True,True,True)
        self.assertTrue(s.require_go())
    def test_workflow_drift_blocks_even_if_main_same(self):
        b=dict(PINNED_BLOBS)
        b[".github/workflows/stock-monitor.yml"]="0"*40
        s=ReadonlyStatus(PINNED_MAIN,b,True,True,True,True,True,True)
        self.assertIn("blob_drift:.github/workflows/stock-monitor.yml",s.blockers())
if __name__=="__main__":unittest.main()
