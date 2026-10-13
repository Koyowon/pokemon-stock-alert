"""Offline security regression: review-only approval is not authenticated authority.

Tests intentionally document the current trust boundary; they do not activate production.
"""
import unittest
from cu_evidence_transition_policy import assess, CASES, HOLD, APPROVED


def complete(cid):
    code, topic = CASES[cid]
    return dict(source_verified=True, dated=True, code=code, topic=topic,
                address_link_verified=True, unit_or_building_verified=True,
                independent_review=True)


def forged(cid):
    return dict(decision="APPROVE", case_id=cid, code=CASES[cid][0],
                reviewer="any-unverified-name", approval_reference="self-asserted",
                explicit=True)


class ApprovalBoundarySafetyTests(unittest.TestCase):
    def test_unauthenticated_reviewer_can_trigger_review_only_status(self):
        # Current behavior is a documented risk, not proof of authenticated approval.
        for cid in CASES:
            result = assess(cid, complete(cid), forged(cid))
            self.assertEqual(result["state"], APPROVED)
            self.assertFalse(result["production_activation"])
            self.assertFalse(result["same_location_confirmed"])

    def test_review_only_status_never_sets_production_activation(self):
        for cid in CASES:
            for evidence, approval in (({}, None), (complete(cid), None),
                                       (complete(cid), forged(cid)),
                                       (dict(complete(cid), conflicting=True), forged(cid))):
                result = assess(cid, evidence, approval)
                self.assertIs(result["production_activation"], False)
                self.assertIs(result["same_location_confirmed"], False)

    def test_blank_reviewer_fails_closed(self):
        for cid in CASES:
            approval = dict(forged(cid), reviewer="  ")
            self.assertEqual(assess(cid, complete(cid), approval)["state"], HOLD)

    def test_nonexplicit_approval_fails_closed(self):
        for cid in CASES:
            approval = dict(forged(cid), explicit="true")
            self.assertEqual(assess(cid, complete(cid), approval)["state"], HOLD)

    def test_mismatched_approval_code_fails_closed(self):
        for cid in CASES:
            approval = dict(forged(cid), code="00000")
            self.assertEqual(assess(cid, complete(cid), approval)["state"], HOLD)

    def test_conflicting_evidence_overrides_forged_approval(self):
        for cid in CASES:
            result = assess(cid, dict(complete(cid), conflicting=True), forged(cid))
            self.assertEqual(result["state"], HOLD)
            self.assertEqual(result["evidence_grade"], "CONFLICTING")


if __name__ == "__main__":
    unittest.main()
