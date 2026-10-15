"""Final minimal NO-DEPLOY gate for CU and emart24.

No production network, state or Telegram. Three user-approved criteria only.
"""
import copy
import unittest
from unittest.mock import patch

from experiments.stage12_candidate import blank,scan_from_latest
from experiments.stage13_state_publisher import (
    claim_for_run,dispatch_claimed,missing_or_uncertain,
    validate_target,publish_if_unchanged,PublishConflict,
)


class FinalReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first=scan_from_latest(blank())

    def test_inventory_counts_and_chain_separation(self):
        d=self.first
        self.assertEqual(d["chains"]["cu"]["state"]["stores"]["FAKE-CU-01"]["stock"],3)
        self.assertEqual(d["chains"]["emart24"]["state"]["이마트24|FAKE-EM-01|8800286275732"],4)
        self.assertEqual(len(d["chains"]["cu"]["state"]["pending_alerts"]),1)
        self.assertEqual(len(d["chains"]["emart24"]["state"]["pending_alerts"]),1)

    def test_duplicate_and_uncertain_delivery(self):
        initial=copy.deepcopy(self.first)
        repeated=scan_from_latest(initial)
        for chain in ("cu","emart24"):
            self.assertEqual(repeated["chains"][chain]["state"]["pending_alerts"],
                             initial["chains"][chain]["state"]["pending_alerts"])
        claimed,ids=claim_for_run(repeated,"final-test","2026-10-16T00:00:00+00:00")
        self.assertEqual(len(ids),2)
        def unknown(_): raise TimeoutError("synthetic ambiguous")
        after=dispatch_claimed(claimed,ids,"final-test",unknown)
        self.assertEqual(set(missing_or_uncertain(after)),set(ids))
        _,reclaimed=claim_for_run(after,"rerun","2026-10-16T01:00:00+00:00")
        self.assertEqual(reclaimed,[])
        self.assertEqual(len(after["outcomes"]),2)

    def test_backup_and_rollback_are_readonly(self):
        backup=copy.deepcopy(self.first)
        candidate,ids=claim_for_run(self.first,"rollback-test","2026-10-16T00:00:00+00:00")
        self.assertEqual(self.first,backup)
        self.assertEqual(len(ids),2)
        self.assertEqual(len(missing_or_uncertain(candidate)),2)
        with self.assertRaises(ValueError):
            validate_target("main","state.json")
        with patch("experiments.stage13_state_publisher.remote_state",return_value=("newer",None)):
            with self.assertRaises(PublishConflict):
                publish_if_unchanged("/tmp/no-op","validation/pr2-stage13-state-20261016",
                    "experiments/stage13_probe_test.json","stale",candidate,"test")


if __name__=="__main__":
    unittest.main()
