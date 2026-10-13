"""Deterministic offline thread regression for atomic binding and approval consume."""
import threading
import unittest
from datetime import datetime, timezone
from cu_hardened_approval_policy import CASES, HOLD, REVIEW_ONLY, evidence_digest
from cu_shared_memory_approval_ledger import SharedMemoryApprovalLedger
from cu_atomic_binding_gateway import AtomicBindingGateway

NOW = datetime(2026, 10, 13, 1, tzinfo=timezone.utc)
TRUSTED = {"fixture-reviewer": {"can_review": True, "cases": list(CASES)}}
CID = "ASAN-CU-083"


def fixture():
    code, topic = CASES[CID]
    ev = dict(code=code, topic=topic, source_verified=True, dated=True,
              address_link_verified=True, unit_or_building_verified=True,
              independent_review=True, conflicting=False)
    ap = dict(decision="APPROVE", explicit=True, reviewer="fixture-reviewer",
              case_id=CID, code=code, evidence_sha256=evidence_digest(ev),
              approval_id="atomic-fixture", issued_at="2026-10-12T00:00:00+00:00",
              expires_at="2026-10-14T00:00:00+00:00")
    return ev, ap


def fresh():
    ledger = SharedMemoryApprovalLedger()
    return AtomicBindingGateway(ledger, "ledger-A", "epoch-1"), ledger


class AtomicGatewayTests(unittest.TestCase):
    def review(self, gateway):
        ev, ap = fixture()
        return gateway.review(CID, ev, ap, TRUSTED, NOW)

    def test_healthy_review_only(self):
        gateway, ledger = fresh()
        self.assertEqual(self.review(gateway)["state"], REVIEW_ONLY)
        self.assertEqual(ledger.consumed_count(), 1)

    def test_replay_blocked(self):
        gateway, _ = fresh()
        self.review(gateway)
        self.assertEqual(self.review(gateway)["reason"], "APPROVAL_REPLAY")

    def test_four_mutations_before_review_hold(self):
        scenarios = [({"ledger": SharedMemoryApprovalLedger()}, "LEDGER_GENERATION_MISMATCH"),
                     ({"ready": False}, "LEDGER_UNAVAILABLE"),
                     ({"generation": "epoch-2"}, "LEDGER_GENERATION_MISMATCH"),
                     ({"identity": "ledger-B"}, "LEDGER_IDENTITY_MISMATCH")]
        for kwargs, reason in scenarios:
            with self.subTest(reason=reason, kwargs=str(kwargs)):
                gateway, original = fresh()
                gateway.mutate(**kwargs)
                self.assertEqual(self.review(gateway)["reason"], reason)
                self.assertEqual(original.consumed_count(), 0)

    def test_four_mutations_during_review_are_serialized(self):
        scenarios = [{"ledger": SharedMemoryApprovalLedger()}, {"ready": False},
                     {"generation": "epoch-2"}, {"identity": "ledger-B"}]
        for kwargs in scenarios:
            with self.subTest(kwargs=str(kwargs)):
                gateway, original = fresh()
                inside = threading.Event()
                resume = threading.Event()
                attempted = threading.Event()
                finished = threading.Event()
                errors = []
                result = []

                def hook():
                    inside.set()
                    if not resume.wait(timeout=5):
                        raise RuntimeError("hook timeout")

                gateway._before_consume = hook

                def reviewer():
                    try:
                        result.append(self.review(gateway))
                    except BaseException as exc:
                        errors.append(exc)

                def mutator():
                    try:
                        attempted.set()
                        gateway.mutate(**kwargs)
                    except BaseException as exc:
                        errors.append(exc)
                    finally:
                        finished.set()

                t1 = threading.Thread(target=reviewer)
                t2 = threading.Thread(target=mutator)
                t1.start()
                try:
                    self.assertTrue(inside.wait(timeout=5))
                    t2.start()
                    self.assertTrue(attempted.wait(timeout=5))
                    # Do not rely on sleep or scheduling to assert mutation timing.
                    self.assertFalse(finished.is_set())
                finally:
                    resume.set()
                    t1.join(timeout=5)
                    if t2.ident is not None:
                        t2.join(timeout=5)
                self.assertFalse(t1.is_alive())
                self.assertFalse(t2.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(result[0]["state"], REVIEW_ONLY)
                self.assertEqual(original.consumed_count(), 1)
                self.assertEqual(self.review(gateway)["state"], HOLD)
                self.assertFalse(result[0]["production_activation"])

    def test_unavailable_never_consumes(self):
        gateway, ledger = fresh()
        gateway.mutate(ready=False)
        result = self.review(gateway)
        self.assertEqual(result["state"], HOLD)
        self.assertEqual(ledger.consumed_count(), 0)
        self.assertFalse(result["same_location_confirmed"])

    def test_evidence_changed_still_holds(self):
        gateway, ledger = fresh()
        ev, ap = fixture()
        result = gateway.review(CID, dict(ev, revision="changed"), ap, TRUSTED, NOW)
        self.assertEqual(result["reason"], "EVIDENCE_CHANGED_OR_UNBOUND")
        self.assertEqual(ledger.consumed_count(), 0)

    def test_conflicting_evidence_still_holds(self):
        gateway, ledger = fresh()
        ev, ap = fixture()
        result = gateway.review(CID, dict(ev, conflicting=True), ap, TRUSTED, NOW)
        self.assertEqual(result["reason"], "CONFLICTING_EVIDENCE")
        self.assertEqual(ledger.consumed_count(), 0)

    def test_uninitialized_holds(self):
        gateway, _ = fresh()
        gateway.mutate(initialized=False)
        self.assertEqual(self.review(gateway)["reason"], "LEDGER_UNINITIALIZED")


if __name__ == "__main__":
    unittest.main()
