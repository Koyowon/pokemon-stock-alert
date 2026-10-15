import copy
import unittest
from experiments.stage12_candidate import blank,scan_from_latest
from experiments.stage13_state_publisher import (
    validate_target,claim_for_run,dispatch_claimed,missing_or_uncertain,
    PublishConflict,publish_if_unchanged
)
from unittest.mock import patch


class Stage13Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial=scan_from_latest(blank())

    def test_branch_and_path_allowlist(self):
        validate_target("validation/pr2-stage13-state-20261016","experiments/stage13_probe_test.json")
        for branch,path in [
            ("main","experiments/stage13_probe_test.json"),
            ("validation/pr2-stage13-state-20261016","state.json"),
            ("validation/pr2-stage13-state-20261016","experiments/stage13_probe_../../state.json")]:
            with self.assertRaises(ValueError): validate_target(branch,path)

    def test_claim_owned_only(self):
        d,ids=claim_for_run(self.initial,"r1","2026-10-16T00:00:00+00:00")
        self.assertEqual(len(ids),2)
        sent=[]
        with self.assertRaises(ValueError):
            dispatch_claimed(d,ids,"wrong",sent.append)
        self.assertEqual(sent,[])

    def test_dispatch_mock_once(self):
        d,ids=claim_for_run(self.initial,"r1","2026-10-16T00:00:00+00:00")
        sent=[]
        result=dispatch_claimed(d,ids,"r1",sent.append)
        self.assertEqual(len(sent),2)
        self.assertEqual(missing_or_uncertain(result),[])
        with self.assertRaises(ValueError):
            dispatch_claimed(result,ids,"r1",sent.append)

    def test_ambiguous_send_never_requeued(self):
        d,ids=claim_for_run(self.initial,"r1","2026-10-16T00:00:00+00:00")
        def uncertain(_): raise TimeoutError("ambiguous")
        result=dispatch_claimed(d,ids,"r1",uncertain)
        self.assertEqual(set(missing_or_uncertain(result)),set(ids))
        self.assertTrue(all(x["status"]=="send_unknown" for x in result["outcomes"].values()))
        again,ids2=claim_for_run(result,"r2","2026-10-16T01:00:00+00:00")
        self.assertEqual(ids2,[])

    def test_missing_outcome_is_audited(self):
        d,ids=claim_for_run(self.initial,"r1","2026-10-16T00:00:00+00:00")
        self.assertEqual(set(missing_or_uncertain(d)),set(ids))

    def test_git_conflict_no_send(self):
        d=copy.deepcopy(self.initial)
        with patch("experiments.stage13_state_publisher.remote_state",return_value=("remote-new",None)):
            with self.assertRaises(PublishConflict):
                publish_if_unchanged("/tmp/never-used","validation/pr2-stage13-state-20261016",
                                     "experiments/stage13_probe_test.json","old-sha",d,"test")

    def test_read_only_rollback_snapshot(self):
        before=copy.deepcopy(self.initial)
        d,ids=claim_for_run(self.initial,"r1","2026-10-16T00:00:00+00:00")
        self.assertEqual(before,self.initial)
        self.assertEqual(len(ids),2)
        self.assertEqual(len(missing_or_uncertain(d)),2)


if __name__=="__main__":unittest.main()
