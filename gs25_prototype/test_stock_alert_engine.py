"""Offline-only unit tests for v3 GS25 mock stock state and leased outbox."""
import json
import multiprocessing
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mock_outbox import (
    claim_mock_event, complete_mock_event, pending_mock_events,
    recover_expired_claims, release_mock_event,
)
from stock_alert_engine import StockAlertError, mock_notification_preview, process_mock_snapshot
from stock_state_store import StateDurabilityError, locked_state, read_state

PRODUCT = "MOCK_POKEMON_30"
NAME = "포켓몬카드 30주년 메가확장팩"
T1 = "2026-10-14T00:00:00+00:00"
T2 = "2026-10-14T00:10:00+00:00"
T3 = "2026-10-14T00:20:00+00:00"
T4 = "2026-10-14T00:30:00+00:00"


def store(quantity, code="MOCK_001", name="GS25 병점역점"):
    return {"storeCode": code, "storeName": name, "realStockQuantity": quantity}


def _worker(path, ready, start, result):
    ready.put(True)
    start.wait(5)
    try:
        events = process_mock_snapshot(path, PRODUCT, NAME, [store(2)], T2)
        result.put(len(events))
    except Exception as exc:
        result.put(type(exc).__name__)


def _hold_lock(path, ready, release):
    with locked_state(path):
        ready.put(True)
        release.wait(5)


def _claim_worker(path, identifier, ready, start, result):
    ready.put(True)
    start.wait(5)
    try:
        claim = claim_mock_event(path, identifier, T3)
        result.put(claim is not None)
    except Exception as exc:
        result.put(type(exc).__name__)


class TestOfflineStockAlerts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "stock-state.json"

    def process(self, stores, time, product=PRODUCT):
        return process_mock_snapshot(self.path, product, NAME, stores, time)

    def seed_event(self):
        self.process([store(0)], T1)
        return self.process([store(2)], T2)[0]

    def test_first_snapshot_is_baseline(self):
        self.assertEqual(self.process([store(2)], T1), [])
        self.assertEqual(read_state(self.path)["items"][PRODUCT + "::MOCK_001"]["quantity"], 2)
        self.assertEqual(read_state(self.path)["version"], 3)

    def test_restock_and_duplicate_suppression(self):
        event = self.seed_event()
        self.assertEqual(event["type"], "restocked")
        self.assertTrue(event["mockOnly"])
        self.assertIn("테스트 데이터", mock_notification_preview(event))
        self.assertEqual(self.process([store(2)], T2), [])
        self.assertEqual(self.process([store(2)], T3), [])
        self.assertEqual(len(pending_mock_events(self.path)), 1)

    def test_increase_decrease_and_restock(self):
        self.process([store(2)], T1)
        self.assertEqual(self.process([store(5)], T2)[0]["type"], "increased")
        self.assertEqual(self.process([store(0)], T3), [])
        self.assertEqual(self.process([store(1)], T4)[0]["type"], "restocked")

    def test_multiple_stores_are_independent(self):
        self.process([store(0), store(0, "MOCK_002", "GS25 다른점")], T1)
        events = self.process([store(2), store(0, "MOCK_002", "GS25 다른점")], T2)
        self.assertEqual([event["storeCode"] for event in events], ["MOCK_001"])

    def test_product_separation(self):
        self.process([store(0)], T1)
        self.assertEqual(self.process([store(2)], T2, "MOCK_OTHER"), [])
        self.assertEqual(len(self.process([store(2)], T3)), 1)

    def test_stale_snapshot_ignored(self):
        self.process([store(3)], T2)
        self.assertEqual(self.process([store(9)], T1), [])
        self.assertEqual(self.process([store(3)], T3), [])

    def test_invalid_input_never_mutates_state(self):
        self.process([store(1)], T1)
        before = self.path.read_bytes()
        for invalid in [store(-1), store(True), store("2"), store(10000), store(2, "REAL_1")]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(StockAlertError):
                    self.process([invalid], T2)
                self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(StockAlertError):
            self.process([store(2), store(2)], T2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_corrupt_state_refuses_overwrite(self):
        self.path.write_text("not json")
        with self.assertRaises(StockAlertError):
            self.process([store(2)], T1)
        self.assertEqual(self.path.read_text(), "not json")

    def test_timezone_required(self):
        with self.assertRaises(StockAlertError):
            self.process([store(2)], "2026-10-14T00:00:00")
        self.assertFalse(self.path.exists())

    def test_preview_rejects_non_mock(self):
        with self.assertRaises(StockAlertError):
            mock_notification_preview({"mockOnly": False})

    def test_corrupt_stored_timestamp_preserved(self):
        state = {"version": 3, "items": {"MOCK_A::MOCK_001": {"quantity": 2, "observed_at": "not-a-date"}}, "outbox": {}}
        self.path.write_text(json.dumps(state))
        before = self.path.read_bytes()
        with self.assertRaises(StockAlertError):
            self.process([store(2)], T2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_v1_migration_preserves_stock(self):
        old = {"version": 1, "items": {PRODUCT + "::MOCK_001": {"quantity": 0, "observed_at": T1}}}
        self.path.write_text(json.dumps(old))
        self.assertEqual(len(self.process([store(2)], T2)), 1)
        state = read_state(self.path)
        self.assertEqual(state["version"], 3)
        self.assertEqual(state["items"][PRODUCT + "::MOCK_001"]["quantity"], 2)
        self.assertEqual(len(state["outbox"]), 1)

    def test_invalid_v1_migration_refused(self):
        old = {"version": 1, "items": {PRODUCT + "::MOCK_001": {"quantity": 0, "observed_at": "invalid"}}}
        self.path.write_text(json.dumps(old))
        before = self.path.read_bytes()
        with self.assertRaises(StockAlertError):
            self.process([store(2)], T2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_pending_survives_restart_and_completion(self):
        event = self.seed_event()
        self.assertEqual(len(pending_mock_events(self.path)), 1)
        claim = claim_mock_event(self.path, event["id"], T3)
        self.assertTrue(complete_mock_event(self.path, event["id"], claim["claimToken"], T3))
        self.assertEqual(pending_mock_events(self.path), [])
        self.assertEqual(self.process([store(2)], T2), [])

    def test_save_failure_does_not_replace_state(self):
        self.process([store(0)], T1)
        before = self.path.read_bytes()
        with patch("stock_state_store.os.replace", side_effect=OSError("simulated disk error")):
            with self.assertRaises(OSError):
                self.process([store(2)], T2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_lock_timeout(self):
        ctx = multiprocessing.get_context("spawn")
        ready, release = ctx.Queue(), ctx.Event()
        process = ctx.Process(target=_hold_lock, args=(self.path, ready, release))
        process.start()
        try:
            self.assertTrue(ready.get(timeout=5))
            with self.assertRaisesRegex(StockAlertError, "lock timeout"):
                with locked_state(self.path, timeout=0.01):
                    pass
        finally:
            release.set()
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join()
        self.assertEqual(process.exitcode, 0)

    def test_concurrent_same_event_queued_once(self):
        self.process([store(0)], T1)
        ctx = multiprocessing.get_context("spawn")
        ready, start, result = ctx.Queue(), ctx.Event(), ctx.Queue()
        processes = [ctx.Process(target=_worker, args=(self.path, ready, start, result)) for _ in range(2)]
        for proc in processes:
            proc.start()
        try:
            self.assertTrue(ready.get(timeout=5))
            self.assertTrue(ready.get(timeout=5))
            start.set()
            self.assertEqual(sorted(result.get(timeout=10) for _ in processes), [0, 1])
            self.assertEqual(len(pending_mock_events(self.path)), 1)
        finally:
            start.set()
            for proc in processes:
                proc.join(5)
                if proc.is_alive():
                    proc.terminate()
                    proc.join()
        self.assertTrue(all(proc.exitcode == 0 for proc in processes))

    def test_post_rename_fsync_failure_distinguished(self):
        self.process([store(0)], T1)
        real_fsync = __import__("os").fsync
        calls = [0]
        def fail_directory(fd):
            calls[0] += 1
            if calls[0] == 2:
                raise OSError("directory fsync failure")
            return real_fsync(fd)
        with patch("stock_state_store.os.fsync", side_effect=fail_directory):
            with self.assertRaises(StateDurabilityError) as caught:
                self.process([store(2)], T2)
        self.assertEqual(caught.exception.observed_state["items"][PRODUCT + "::MOCK_001"]["quantity"], 2)

    def test_v2_migration(self):
        event = self.seed_event()
        state = json.loads(self.path.read_text())
        state["version"] = 2
        for entry in state["outbox"].values():
            for field in ("attempts", "claimToken", "claimExpiresAt"):
                del entry[field]
        self.path.write_text(json.dumps(state))
        self.assertEqual(read_state(self.path)["outbox"][event["id"]]["attempts"], 0)
        self.process([store(2)], T3)
        self.assertEqual(json.loads(self.path.read_text())["version"], 3)

    def test_event_id_tampering_rejected(self):
        event = self.seed_event()
        state = json.loads(self.path.read_text())
        state["outbox"][event["id"]]["currentQuantity"] = 3
        self.path.write_text(json.dumps(state))
        before = self.path.read_bytes()
        with self.assertRaises(StockAlertError):
            pending_mock_events(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_claim_wrong_token_and_expiry(self):
        event = self.seed_event()
        claim = claim_mock_event(self.path, event["id"], T3, lease_seconds=5)
        with self.assertRaises(StockAlertError):
            complete_mock_event(self.path, event["id"], "wrong", T3)
        with self.assertRaises(StockAlertError):
            complete_mock_event(self.path, event["id"], claim["claimToken"], T4)

    def test_expiry_recovery_and_fencing(self):
        event = self.seed_event()
        first = claim_mock_event(self.path, event["id"], T3, lease_seconds=5)
        self.assertTrue(recover_expired_claims(self.path, T4))
        second = claim_mock_event(self.path, event["id"], T4)
        self.assertNotEqual(first["claimToken"], second["claimToken"])
        with self.assertRaises(StockAlertError):
            complete_mock_event(self.path, event["id"], first["claimToken"], T4)

    def test_max_three_attempts_failed(self):
        event = self.seed_event()
        for attempt in range(3):
            now = (datetime.fromisoformat(T3) + timedelta(seconds=attempt * 10)).isoformat()
            claim = claim_mock_event(self.path, event["id"], now)
            expected = "failed" if attempt == 2 else "pending"
            self.assertEqual(release_mock_event(self.path, event["id"], claim["claimToken"], now), expected)
        self.assertIsNone(claim_mock_event(self.path, event["id"], T4))
        self.assertEqual(read_state(self.path)["outbox"][event["id"]]["status"], "failed")

    def test_concurrent_claim_only_one(self):
        event = self.seed_event()
        ctx = multiprocessing.get_context("spawn")
        ready, start, result = ctx.Queue(), ctx.Event(), ctx.Queue()
        procs = [ctx.Process(target=_claim_worker, args=(self.path, event["id"], ready, start, result)) for _ in range(2)]
        for proc in procs:
            proc.start()
        try:
            self.assertTrue(ready.get(timeout=5))
            self.assertTrue(ready.get(timeout=5))
            start.set()
            self.assertEqual(sorted(result.get(timeout=10) for _ in procs), [False, True])
        finally:
            start.set()
            for proc in procs:
                proc.join(5)
                if proc.is_alive():
                    proc.terminate()
                    proc.join()
        self.assertTrue(all(proc.exitcode == 0 for proc in procs))

    def test_invalid_lock_timeout(self):
        for timeout in (True, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(StockAlertError):
                    with locked_state(self.path, timeout=timeout):
                        pass


if __name__ == "__main__":
    unittest.main()
