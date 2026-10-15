import copy
import unittest
from unittest.mock import patch
import cu_emart24_state_store as store

class ProposedProductionState(unittest.TestCase):
    def setUp(self):
        self.cu={"cu_stock_state.json":{"stores":{"S":{"stock":3}},"pending_alerts":{"e":{"status":"pending","message":"synthetic 3"}},"alert_sequence":1}}
        self.em={"state.json":{"이마트24|S|8800286275732":4,"pending_alerts":{"f":{"status":"pending","message":"synthetic 4"}},"alert_sequence":1},"stores.json":{"S":{"name":"synthetic"}}}
    def test_counts_and_exact_file_allowlist(self):
        self.assertEqual(store.validate("cu",self.cu)["cu_stock_state.json"]["stores"]["S"]["stock"],3)
        self.assertEqual(store.validate("emart24",self.em)["state.json"]["이마트24|S|8800286275732"],4)
        for chain,branch,paths in [
            ("cu","main",("cu_stock_state.json",)),
            ("emart24",store.PROPOSED_BRANCH,("state.json",)),
            ("cu",store.PROPOSED_BRANCH,("gs25_independent/gs25_stock_state.json",))]:
            with self.assertRaises(ValueError): store.check(chain,branch,paths)
    def test_claim_commit_and_ambiguous_delivery(self):
        original=copy.deepcopy(self.cu)
        claimed,ids=store.claim(self.cu,"cu","run-1","2026-10-16T00:00:00Z")
        self.assertEqual(ids,["e"])
        self.assertEqual(self.cu,original)
        with self.assertRaises(ValueError):
            store.record_attempts(claimed,"cu",ids,"other",lambda _:None)
        def timeout(_): raise TimeoutError("ambiguous")
        attempted=store.record_attempts(claimed,"cu",ids,"run-1",timeout)
        self.assertEqual(store.unresolved(attempted,"cu"),["e"])
        _,again=store.claim(attempted,"cu","run-2","2026-10-16T01:00:00Z")
        self.assertEqual(again,[])
        with self.assertRaises(ValueError):
            store.record_attempts(attempted,"cu",ids,"run-1",lambda _:None)
    def test_immutable_backup_and_conflict_fail_closed(self):
        backup=store.immutable_backup(self.em,"emart24","baseline")
        self.assertEqual(set(backup["files"]),{"state.json","stores.json"})
        self.assertEqual(len(backup["files"]["state.json"]["sha256"]),64)
        with patch.object(store,"fetch",return_value=("advanced",self.em)):
            with self.assertRaises(store.Conflict):
                store.publish("/tmp/not-used","emart24","old",self.em)
if __name__=="__main__": unittest.main()
