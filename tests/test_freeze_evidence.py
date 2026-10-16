import unittest
from cu_emart24_freeze_evidence import Freeze,review_running_jobs,require_frozen

class FreezeSafety(unittest.TestCase):
    def test_default_no_go(self):
        with self.assertRaisesRegex(RuntimeError,"NO-GO"):Freeze().require_ready()
    def test_drain_only_target_workflows(self):
        jobs=[
          {"id":1,"workflow_path":".github/workflows/cu-stock-monitor.yml","status":"in_progress"},
          {"id":2,"workflow_path":".github/workflows/stock-monitor.yml","status":"queued"},
          {"id":3,"workflow_path":".github/workflows/gs25-stock-monitor.yml","status":"in_progress"},
          {"id":4,"workflow_path":".github/workflows/pages.yml","status":"in_progress"}]
        self.assertEqual(review_running_jobs(jobs),[("cu-stock-monitor.yml",1),("stock-monitor.yml",2)])
        jobs[0]["status"]="completed";jobs[1]["status"]="completed"
        self.assertEqual(review_running_jobs(jobs),[])
    def test_fully_approved_still_blocks_inflight(self):
        evidence=Freeze(**{k:True for k in Freeze.__dataclass_fields__})
        with self.assertRaisesRegex(RuntimeError,"in-flight"):
            require_frozen(evidence,[{"id":4,"workflow_path":".github/workflows/stock-monitor.yml","status":"queued"}])
        self.assertTrue(require_frozen(evidence,[{"id":4,"workflow_path":".github/workflows/gs25-stock-monitor.yml","status":"in_progress"}]))
    def test_partial_backup_or_missing_manual_dispatch_block(self):
        values={k:True for k in Freeze.__dataclass_fields__}
        values["raw_backup_verified"]=False
        with self.assertRaisesRegex(RuntimeError,"raw_backup_verified"):Freeze(**values).require_ready()
        values["raw_backup_verified"]=True
        values["manual_dispatch_blocked"]=False
        with self.assertRaisesRegex(RuntimeError,"manual_dispatch_blocked"):Freeze(**values).require_ready()
if __name__=="__main__":unittest.main()
