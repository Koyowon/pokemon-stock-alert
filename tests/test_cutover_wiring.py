import copy
import unittest
from unittest.mock import patch
from cu_emart24_scan_adapter import scan_with_snapshot
from cu_emart24_cutover_coordinator import claim_and_dispatch
from cu_emart24_state_store import Conflict

class CutoverWiring(unittest.TestCase):
    def test_actual_cu_scanner_uses_snapshot_and_no_telegram(self):
        base={"cu_stock_state.json":{"stores":{},"pending_alerts":{},"alert_sequence":0}}
        fake={"code":"FAKE-CU-01","name":"테스트점","address":"충청남도 아산시 테스트로 12","city":"아산","stock":3}
        with patch("cu_stock_monitor.POINTS",{"아산":[(36.79,127.0)]}), \
             patch("cu_stock_monitor.query",return_value=[fake]), \
             patch("unified_settings.enabled",return_value={"asan"}), \
             patch("cu_asan_registry.summarize_observations",return_value=None):
            result=scan_with_snapshot("cu",base)
        self.assertEqual(result["cu_stock_state.json"]["stores"]["FAKE-CU-01"]["stock"],3)
        self.assertEqual(len(result["cu_stock_state.json"]["pending_alerts"]),1)
        self.assertEqual(base["cu_stock_state.json"]["stores"],{})
    def test_actual_emart_scanner_uses_snapshot_and_no_telegram(self):
        base={"state.json":{"pending_alerts":{},"alert_sequence":0},"stores.json":{}}
        fake={"FAKE-EM-01":{"name":"가상점","address":"충청남도 아산시 테스트로 20"}}
        with patch("monitor.get_stores",return_value=fake), \
             patch("monitor.stock",return_value=({"FAKE-EM-01":4},{"FAKE-EM-01":"OK"})), \
             patch("unified_settings.enabled",return_value={"asan"}):
            result=scan_with_snapshot("emart24",base)
        self.assertEqual(result["state.json"]["이마트24|FAKE-EM-01|8800286275732"],4)
        self.assertEqual(len(result["state.json"]["pending_alerts"]),1)
    def test_claim_push_failure_never_sends(self):
        d={"cu_stock_state.json":{"stores":{},"pending_alerts":{"e":{"status":"pending","message":"mock"}},"alert_sequence":1}}
        with patch("cu_emart24_cutover_coordinator.fetch",return_value=("base",d)), \
             patch("cu_emart24_cutover_coordinator.publish",side_effect=Conflict("stale")):
            called=[]
            with self.assertRaises(Conflict):
                claim_and_dispatch("/tmp/no-repo","cu","run",called.append)
            self.assertEqual(called,[])
    def test_claim_verification_mismatch_never_sends(self):
        d={"cu_stock_state.json":{"stores":{},"pending_alerts":{"e":{"status":"pending","message":"mock"}},"alert_sequence":1}}
        with patch("cu_emart24_cutover_coordinator.fetch",side_effect=[("base",d),("other",d)]), \
             patch("cu_emart24_cutover_coordinator.publish",return_value="claimed"):
            called=[]
            with self.assertRaises(RuntimeError):
                claim_and_dispatch("/tmp/no-repo","cu","run",called.append)
            self.assertEqual(called,[])
if __name__=="__main__": unittest.main()
