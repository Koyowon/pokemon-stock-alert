"""Stage9 offline stability tests using actual CU/emart24 main entrypoints."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import cu_stock_monitor as cu
import monitor as em
from experiments.stage9_stability import preserve_alerts, cas_publish, claimed_audit, ConcurrentUpdate
from experiments.isolated_state_outbox import queue_transition, claim_event, dispatch_once


class FakeGit:
    def __init__(self, state):
        self.state = copy.deepcopy(state)
        self.version = 0
        self.failures = 0
        self.fetches = 0

    def load(self):
        self.fetches += 1
        return self.version, copy.deepcopy(self.state)

    def cas(self, candidate, version):
        if self.failures:
            self.failures -= 1
            self.version += 1
            return False
        if version != self.version:
            return False
        self.state = copy.deepcopy(candidate)
        self.version += 1
        return True


class StabilityTests(unittest.TestCase):
    def test_cu_repeat_scan_does_not_duplicate_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"cu.json"
            p.write_text('{"stores":{}}')
            item={"code":"FAKE-CU-01","name":"테스트점","city":"아산",
                  "address":"충청남도 아산시 테스트로 12","stock":3}
            with patch.object(cu,"STATE_FILE",p),patch.object(cu,"POINTS",{"아산":[(36.79,127.0)]}),patch.object(cu,"query",return_value=[item]),patch.object(cu,"telegram",side_effect=AssertionError("direct send")),patch("unified_settings.enabled",return_value={"asan"}),patch("cu_asan_registry.summarize_observations",return_value=None):
                cu.main()
                first=json.loads(p.read_text())
                cu.main()
                second=json.loads(p.read_text())
            self.assertEqual(len(first["pending_alerts"]),1)
            self.assertEqual(first["pending_alerts"],second["pending_alerts"])

    def test_emart_repeat_scan_does_not_duplicate_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"state.json"
            stores=Path(tmp)/"stores.json"
            p.write_text('{}')
            stores.write_text('{}')
            fake={"FAKE-EM-01":{"name":"가상점","address":"충청남도 아산시 테스트로 20"}}
            with patch.object(em,"STATE_FILE",p),patch.object(em,"STORES_FILE",stores),patch.object(em,"get_stores",return_value=fake),patch.object(em,"stock",return_value=({"FAKE-EM-01":4},{"FAKE-EM-01":"OK"})),patch.object(em,"notify",side_effect=AssertionError("direct send")),patch("unified_settings.enabled",return_value={"asan"}):
                em.main()
                first=json.loads(p.read_text())
                em.main()
                second=json.loads(p.read_text())
            self.assertEqual(len(first["pending_alerts"]),1)
            self.assertEqual(first["pending_alerts"],second["pending_alerts"])

    def test_preserve_claimed_pending(self):
        s,e=queue_transition({},"cu","test")
        claimed=claim_event(s,e)
        newer=preserve_alerts(claimed,{"stock":{"fake":2}})
        self.assertEqual(newer["pending_alerts"][e]["status"],"claimed")
        self.assertEqual(newer["alert_sequence"],1)

    def test_conflicting_claim_not_overwritten(self):
        s,e=queue_transition({},"emart24","test")
        with self.assertRaises(ValueError):
            preserve_alerts(claim_event(s,e),s)

    def test_cas_retry_refreshes_latest(self):
        git=FakeGit({"stock":{}})
        git.failures=1
        state,retries=cas_publish(git.load,git.cas,lambda x:dict(x,marker=True))
        self.assertEqual(retries,1)
        self.assertEqual(git.fetches,2)
        self.assertTrue(state["marker"])

    def test_cas_exhaustion_blocks_send(self):
        git=FakeGit({})
        git.failures=3
        sent=[]
        with self.assertRaises(ConcurrentUpdate):
            cas_publish(git.load,git.cas,lambda x:x,retries=3)
        self.assertEqual(sent,[])

    def test_failed_claim_no_send(self):
        s,e=queue_transition({},"cu","test")
        git=FakeGit(s)
        git.failures=1
        sent=[]
        self.assertFalse(dispatch_once(git.load,git.cas,sent.append,e))
        self.assertEqual(sent,[])

    def test_claimed_audit_old_and_missing_time(self):
        now=datetime(2026,10,16,tzinfo=timezone.utc)
        old=(now-timedelta(hours=2)).isoformat()
        state={"pending_alerts":{"old":{"status":"claimed","claimed_at":old},
             "missing":{"status":"claimed"},"fresh":{"status":"claimed","claimed_at":now.isoformat()},
             "pending":{"status":"pending"}}}
        self.assertEqual(set(claimed_audit(state,now)),{"old","missing"})

    def test_read_only_rollback_snapshot(self):
        s,e=queue_transition({},"cu","test")
        before=copy.deepcopy(s)
        after=claim_event(s,e)
        self.assertEqual(before["pending_alerts"][e]["status"],"pending")
        self.assertEqual(after["pending_alerts"][e]["status"],"claimed")
        self.assertEqual(s,before)


if __name__=="__main__":
    unittest.main()
