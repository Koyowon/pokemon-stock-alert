import unittest
from cu_emart24_release_preflight import Preflight,audit_source
from cu_emart24_executable_workflow import proposed

class FinalReadOnlyAudit(unittest.TestCase):
    def setUp(self):
        self.legacy={
            "cu_stock_state.json":{"stores":{"S":{"stock":3}}},
            "state.json":{"이마트24|S|p":4},
            "stores.json":{"last_refresh":"synthetic","stores":{"S":{"name":"synthetic"}}}}
        self.blobs={p:"sha-"+p for p in self.legacy}
    def test_real_legacy_schema_shape_requires_reconciliation(self):
        result=audit_source(self.legacy,"main-sha",self.blobs)
        self.assertTrue(result["migration_requires_operator_reconciliation"])
        self.assertFalse(result["cu_outbox_present"])
        self.assertFalse(result["emart24_outbox_present"])
        self.assertEqual(result["cu_stores"],1)
        self.assertEqual(result["emart24_cache_stores"],1)
    def test_missing_file_fails_closed(self):
        missing=dict(self.legacy)
        del missing["stores.json"]
        with self.assertRaises(ValueError):audit_source(missing,"main-sha",self.blobs)
    def test_preflight_blocks_until_every_condition_verified(self):
        p=Preflight()
        self.assertIn("live_approval",p.blockers())
        with self.assertRaises(RuntimeError):p.require_ready()
        all_true={name:True for name in p.__dataclass_fields__}
        self.assertTrue(Preflight(**all_true).require_ready())
    def test_workflows_never_hardcode_live_approval(self):
        for body in proposed().values():
            self.assertEqual(body.count("if: false"),2)
            self.assertIn("vars.CU_EMART24_LIVE_APPROVED",body)
            self.assertNotIn("CU_EMART24_LIVE_APPROVED: '1'",body)
            self.assertNotIn("schedule:",body)
            self.assertNotIn("gs25",body.lower())
if __name__=="__main__":unittest.main()
