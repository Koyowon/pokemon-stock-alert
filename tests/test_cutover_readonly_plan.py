import unittest
from cu_emart24_cutover_readonly_plan import FreezeEvidence,offline_plan

class ReadonlyCutoverPlanTests(unittest.TestCase):
    def setUp(self):
        self.state={
          "cu_stock_state.json":{"stores":{"A":{"stock":3,"alerted":False},"B":{"stock":0,"alerted":False}}},
          "state.json":{"emart24|S|P":3,"emart24|T|P":0},
          "stores.json":{"last_refresh":"offline","stores":{"S":{"name":"synthetic"}}}}
        self.blobs={p:"a"*40 for p in self.state}
    def test_fail_closed_for_any_missing_approval(self):
        with self.assertRaisesRegex(RuntimeError,"NO-GO"):FreezeEvidence().require_go()
        values={k:True for k in FreezeEvidence.__dataclass_fields__}
        self.assertTrue(FreezeEvidence(**values).require_go())
        values["owner_authorized_live_pilot"]=False
        with self.assertRaisesRegex(RuntimeError,"NO-GO"):FreezeEvidence(**values).require_go()
    def test_offline_plan_preserves_legacy_and_requires_first_scan_review(self):
        original=str(self.state)
        plan=offline_plan(self.state,"a"*40,self.blobs)
        self.assertEqual(str(self.state),original)
        self.assertEqual(plan["status"],"NO-GO")
        self.assertEqual(plan["initial_outbox_alerts"],0)
        self.assertFalse(plan["legacy_delivery_reconstructed"])
        self.assertFalse(plan["raw_backup_exported"])
        self.assertEqual(len(plan["backup_paths"]),5)
        self.assertIn("first_scan_rule",plan)
    def test_invalid_baseline_fails_closed(self):
        with self.assertRaises(ValueError):offline_plan(self.state,"short",self.blobs)
if __name__=="__main__":unittest.main()
