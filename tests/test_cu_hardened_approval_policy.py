"""Offline synthetic tests; no network, production imports or credentials."""
import unittest
from datetime import datetime, timezone
from cu_hardened_approval_policy import CASES, HOLD, REVIEW_ONLY, assess, evidence_digest

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
TRUSTED = {"reviewer-083": {"can_review": True, "cases": ["ASAN-CU-083"]},
           "reviewer-all": {"can_review": True, "cases": list(CASES)},
           "inactive": {"can_review": False, "cases": list(CASES)}}

def evidence(cid):
    code, topic = CASES[cid]
    return dict(code=code, topic=topic, source_verified=True, dated=True,
                address_link_verified=True, unit_or_building_verified=True,
                independent_review=True, conflicting=False)

def approval(cid, ev=None, reviewer="reviewer-all"):
    ev = evidence(cid) if ev is None else ev
    return dict(decision="APPROVE", explicit=True, reviewer=reviewer,
                case_id=cid, code=CASES[cid][0], evidence_sha256=evidence_digest(ev),
                approval_id="fixture-" + cid, issued_at="2026-10-12T00:00:00+00:00",
                expires_at="2026-10-14T00:00:00+00:00")

class HardenedApprovalTests(unittest.TestCase):
    def check(self, cid, ev=None, ap=None, used=(), now=NOW):
        ev = evidence(cid) if ev is None else ev
        ap = approval(cid, ev) if ap is None else ap
        return assess(cid, ev, ap, TRUSTED, used, now)

    def test_review_only_with_explicit_scoped_approval(self):
        for cid in CASES:
            r = self.check(cid)
            self.assertEqual(r["state"], REVIEW_ONLY)
            self.assertFalse(r["production_activation"])
            self.assertFalse(r["same_location_confirmed"])

    def test_missing_approval(self):
        for cid in CASES:
            self.assertEqual(self.check(cid, ap={})["state"], HOLD)

    def test_unknown_reviewer(self):
        for cid in CASES:
            self.assertEqual(self.check(cid, ap=approval(cid, reviewer="unknown"))["reason"], "UNAUTHORIZED_REVIEWER")

    def test_disabled_reviewer(self):
        for cid in CASES:
            self.assertEqual(self.check(cid, ap=approval(cid, reviewer="inactive"))["state"], HOLD)

    def test_reviewer_scope(self):
        self.assertEqual(self.check("ASAN-CU-092", ap=approval("ASAN-CU-092", reviewer="reviewer-083"))["state"], HOLD)
        self.assertEqual(self.check("ASAN-CU-083", ap=approval("ASAN-CU-083", reviewer="reviewer-083"))["state"], REVIEW_ONLY)

    def test_code_binding(self):
        cid = "ASAN-CU-083"
        self.assertEqual(self.check(cid, ap=dict(approval(cid), code="00000"))["state"], HOLD)

    def test_case_binding(self):
        cid = "ASAN-CU-083"
        self.assertEqual(self.check(cid, ap=dict(approval(cid), case_id="ASAN-CU-092"))["state"], HOLD)

    def test_evidence_hash_changed(self):
        cid = "ASAN-CU-083"
        ev = dict(evidence(cid), extra_note="changed")
        self.assertEqual(self.check(cid, ev=ev, ap=approval(cid))["reason"], "EVIDENCE_CHANGED_OR_UNBOUND")

    def test_missing_evidence_hash(self):
        cid = "ASAN-CU-083"
        self.assertEqual(self.check(cid, ap=dict(approval(cid), evidence_sha256=""))["state"], HOLD)

    def test_expired_approval(self):
        cid = "ASAN-CU-083"
        self.assertEqual(self.check(cid, ap=dict(approval(cid), expires_at="2026-10-13T11:59:59+00:00"))["state"], HOLD)

    def test_future_approval(self):
        cid = "ASAN-CU-083"
        self.assertEqual(self.check(cid, ap=dict(approval(cid), issued_at="2026-10-13T13:00:00+00:00"))["state"], HOLD)

    def test_timezone_required(self):
        cid = "ASAN-CU-083"
        self.assertEqual(self.check(cid, ap=dict(approval(cid), expires_at="2026-10-14T00:00:00"))["state"], HOLD)

    def test_replay_rejected(self):
        cid = "ASAN-CU-083"
        self.assertEqual(self.check(cid, used={"fixture-ASAN-CU-083"})["reason"], "APPROVAL_REPLAY")

    def test_conflict_overrides_valid_approval(self):
        cid = "ASAN-CU-083"
        ev = dict(evidence(cid), conflicting=True)
        self.assertEqual(self.check(cid, ev=ev, ap=approval(cid, ev))["reason"], "CONFLICTING_EVIDENCE")

    def test_incomplete_evidence(self):
        cid = "ASAN-CU-083"
        ev = dict(evidence(cid), independent_review=False)
        self.assertEqual(self.check(cid, ev=ev, ap=approval(cid, ev))["state"], HOLD)

    def test_approval_requires_literal_true(self):
        cid = "ASAN-CU-083"
        self.assertEqual(self.check(cid, ap=dict(approval(cid), explicit="true"))["state"], HOLD)

    def test_missing_approval_id(self):
        cid = "ASAN-CU-083"
        self.assertEqual(self.check(cid, ap=dict(approval(cid), approval_id=""))["state"], HOLD)

    def test_unknown_case(self):
        with self.assertRaises(ValueError):
            assess("ASAN-CU-999", {}, {}, TRUSTED, set(), NOW)

    def test_no_state_mutation(self):
        cid = "ASAN-CU-083"
        consumed = set()
        self.check(cid, used=consumed)
        self.assertEqual(consumed, set())

    def test_missing_conflict_flag_fails_closed(self):
        cid = "ASAN-CU-083"
        ev = evidence(cid)
        ev.pop("conflicting")
        self.assertEqual(self.check(cid, ev=ev, ap=approval(cid, ev))["state"], HOLD)

if __name__ == "__main__":
    unittest.main()
