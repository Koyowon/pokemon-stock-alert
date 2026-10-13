"""Offline synthetic evidence state transitions, no operational imports."""
import unittest
from cu_evidence_transition_policy import assess, CASES, HOLD, APPROVED


def sufficient(case_id):
    code, topic = CASES[case_id]
    return dict(source_verified=True, dated=True, code=code, topic=topic,
                address_link_verified=True, unit_or_building_verified=True,
                independent_review=True)


def approval(case_id):
    return dict(decision="APPROVE", case_id=case_id, code=CASES[case_id][0],
                reviewer="offline-reviewer", approval_reference="fixture-approval",
                explicit=True)


class EvidenceTransitionTests(unittest.TestCase):
    def test_no_evidence(self):
        for cid in CASES:
            self.assertEqual(assess(cid, {})["evidence_grade"], "NONE")
            self.assertEqual(assess(cid, {})["state"], HOLD)

    def test_partial(self):
        for cid in CASES:
            r = assess(cid, {"source_verified": True}, approval(cid))
            self.assertEqual((r["evidence_grade"], r["state"]), ("PARTIAL", HOLD))

    def test_conflict_overrides_sufficiency(self):
        for cid in CASES:
            r = assess(cid, dict(sufficient(cid), conflicting=True), approval(cid))
            self.assertEqual((r["evidence_grade"], r["state"]), ("CONFLICTING", HOLD))

    def test_sufficient_without_approval_stays_hold(self):
        for cid in CASES:
            r = assess(cid, sufficient(cid))
            self.assertEqual((r["evidence_grade"], r["state"]), ("SUFFICIENT", HOLD))

    def test_explicit_approval_after_sufficient(self):
        for cid in CASES:
            r = assess(cid, sufficient(cid), approval(cid))
            self.assertEqual(r["state"], APPROVED)
            self.assertFalse(r["production_activation"])
            self.assertFalse(r["same_location_confirmed"])

    def test_wrong_case_approval_rejected(self):
        for cid in CASES:
            bad = approval(cid)
            bad["case_id"] = "ASAN-CU-OTHER"
            self.assertEqual(assess(cid, sufficient(cid), bad)["state"], HOLD)

    def test_wrong_code_evidence_rejected(self):
        for cid in CASES:
            bad = dict(sufficient(cid), code="00000")
            self.assertEqual(assess(cid, bad, approval(cid))["state"], HOLD)

    def test_wrong_topic_evidence_rejected(self):
        for cid in CASES:
            bad = dict(sufficient(cid), topic="OTHER")
            self.assertEqual(assess(cid, bad, approval(cid))["state"], HOLD)

    def test_missing_independent_review(self):
        for cid in CASES:
            bad = dict(sufficient(cid), independent_review=False)
            self.assertEqual(assess(cid, bad, approval(cid))["state"], HOLD)

    def test_missing_approval_reference(self):
        for cid in CASES:
            bad = dict(approval(cid), approval_reference="")
            self.assertEqual(assess(cid, sufficient(cid), bad)["state"], HOLD)

    def test_approval_is_not_production_authorization(self):
        for cid in CASES:
            r = assess(cid, sufficient(cid), approval(cid))
            self.assertFalse(r["production_activation"])

    def test_unknown_case_rejected(self):
        with self.assertRaises(ValueError):
            assess("ASAN-CU-999", {})


if __name__ == "__main__":
    unittest.main()
