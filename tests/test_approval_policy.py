import unittest
from unittest.mock import patch
from datetime import datetime
from cu_emart24_approval_policy import ApprovalFacts,validate_readonly_snapshot
import cu_emart24_live_entrypoint as live

class ApprovalAcceptance(unittest.TestCase):
    def setUp(self):
        self.source={
          "cu_stock_state.json":{"stores":{"11258":{"stock":0,"alerted":False},"11704":{"stock":2,"alerted":True}}},
          "state.json":{"emart24|21598|8809945338207":0,"emart24|22612|8809945338207":4},
          "stores.json":{"last_refresh":"2026-10-16","stores":{"20365":{"name":"sample"}}}}
        self.blobs={k:"a"*40 for k in self.source}
    def test_fail_closed_until_all_independent_approvals(self):
        facts=ApprovalFacts()
        self.assertIn("token_write_verified",facts.blockers())
        self.assertIn("legacy_alerts_reconciled",facts.blockers())
        with self.assertRaisesRegex(RuntimeError,"NO-GO"):
            facts.require_go()
        approved={k:True for k in facts.__dataclass_fields__}
        self.assertTrue(ApprovalFacts(**approved).require_go())
    def test_readonly_legacy_snapshot_and_exact_change_scope(self):
        original=str(self.source)
        result=validate_readonly_snapshot(self.source,"f"*40,self.blobs)
        self.assertEqual(result["decision"],"NO-GO")
        self.assertFalse(result["historical_delivery_reconstructed"])
        self.assertEqual(result["cu_stores"],2)
        self.assertEqual(result["emart24_cached_stores"],1)
        self.assertEqual(str(self.source),original)
        self.assertNotIn("gs25"," ".join(result["workflow_files_to_replace"]).lower())
    def test_claim_timestamp_is_utc_iso(self):
        state={"cu_stock_state.json":{"stores":{},"pending_alerts":{},"alert_sequence":0}}
        captured=[]
        def claim(data,chain,run_id,when):
            captured.append(when)
            return data,[]
        with patch.object(live,"gate"),patch.object(live,"fetch",side_effect=[("base",state),("saved",state)]),patch.object(live,"claim",side_effect=claim),patch.object(live,"publish",return_value="saved"):
            live.claim_and_send("/tmp/mock","cu","run")
        parsed=datetime.fromisoformat(captured[0])
        self.assertIsNotNone(parsed.tzinfo)
if __name__=="__main__":unittest.main()
