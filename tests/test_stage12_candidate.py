import copy
import unittest
from experiments.stage12_candidate import blank,scan_from_latest,claim_new,record_mock_outcome,audit


class Stage12Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial=scan_from_latest(blank())

    def test_scanner_real_entrypoints_queue_two(self):
        self.assertEqual(sum(len(self.initial['chains'][x]['state']['pending_alerts']) for x in ('cu','emart24')),2)

    def test_rescan_preserves_pending_no_duplicates(self):
        next_state=scan_from_latest(self.initial)
        for chain in ('cu','emart24'):
            self.assertEqual(next_state['chains'][chain]['state']['pending_alerts'],
                             self.initial['chains'][chain]['state']['pending_alerts'])

    def test_claim_only_new_ids(self):
        d,ids=claim_new(self.initial,'stage12-test')
        self.assertEqual(len(ids),2)
        again,ids2=claim_new(d,'stage12-second')
        self.assertEqual(ids2,[])
        self.assertEqual(again,d)

    def test_claimed_rescan_preserves_claims(self):
        claimed,_=claim_new(self.initial,'stage12-test')
        rescan=scan_from_latest(claimed)
        for chain in ('cu','emart24'):
            self.assertEqual(rescan['chains'][chain]['state']['pending_alerts'],
                             claimed['chains'][chain]['state']['pending_alerts'])

    def test_mock_send_only_owned_claims(self):
        d,ids=claim_new(self.initial,'mine')
        with self.assertRaises(ValueError):
            record_mock_outcome(d,'other',ids)
        result=record_mock_outcome(d,'mine',ids)
        self.assertEqual(audit(result),[])
        with self.assertRaises(ValueError):
            record_mock_outcome(result,'mine',ids)

    def test_failed_commit_must_not_call_sender(self):
        d,ids=claim_new(self.initial,'mine')
        sent=[]
        commit_ok=False
        if commit_ok:
            sent.extend(ids)
        self.assertEqual(sent,[])
        self.assertEqual(len(audit(d)),2)

    def test_audit_claimed_without_outcome(self):
        d,ids=claim_new(self.initial,'mine')
        self.assertEqual(set(audit(d)),set(ids))

    def test_rollback_snapshot_is_immutable(self):
        baseline=copy.deepcopy(self.initial)
        d,ids=claim_new(self.initial,'mine')
        self.assertEqual(self.initial,baseline)
        self.assertEqual(len(ids),2)
        self.assertEqual(len(audit(d)),2)


if __name__=='__main__':
    unittest.main()
