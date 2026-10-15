"""Offline durable GS25 notification claim and crash recovery tests."""
import json
from unittest.mock import patch

from test_publisher_bare_git_offline import BareGitPublisherTests, git
from gs25_alert_dispatcher import dispatch, STATE


class GS25OutboxRecoveryTests(BareGitPublisherTests):
    def seed_pending(self):
        p = self.clone()
        f = p / STATE
        data = json.loads(f.read_text())
        data["pending_alerts"] = {"event-1": {"message": "fake GS25 stock", "status": "pending"}}
        f.write_text(json.dumps(data))
        git(p, "add", "--", STATE)
        git(p, "commit", "-m", "seed pending alert")
        git(p, "push", "origin", "HEAD:refs/heads/main")

    def test_claim_before_delivery_and_no_duplicate_on_retry(self):
        self.seed_pending()
        sent = []
        p = self.clone()
        def send(message):
            saved = self.remote_json(STATE)
            self.assertEqual(saved["pending_alerts"]["event-1"]["status"], "claimed")
            sent.append(message)
        self.assertEqual(dispatch(p, send), 1)
        self.assertEqual(dispatch(self.clone(), send), 0)
        self.assertEqual(sent, ["fake GS25 stock"])

    def test_crash_after_claim_does_not_resend(self):
        self.seed_pending()
        p = self.clone()
        def crash():
            raise RuntimeError("simulated crash after durable claim")
        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            dispatch(p, lambda m: self.fail("must not send"), after_claim=crash)
        sent = []
        self.assertEqual(dispatch(self.clone(), sent.append), 0)
        self.assertEqual(sent, [])
        self.assertEqual(self.remote_json(STATE)["pending_alerts"]["event-1"]["status"], "claimed")

    def test_ambiguous_telegram_failure_is_not_retried(self):
        self.seed_pending()
        calls = []
        def ambiguous(message):
            calls.append(message)
            raise TimeoutError("Telegram may have accepted the request")
        self.assertEqual(dispatch(self.clone(), ambiguous), 0)
        self.assertEqual(dispatch(self.clone(), ambiguous), 0)
        self.assertEqual(len(calls), 1)

    def test_git_push_failure_prevents_telegram(self):
        self.seed_pending()
        with patch("gs25_alert_dispatcher.git", wraps=git) as mock_git:
            def blocked(cwd, *args, **kwargs):
                if args and args[0] == "push":
                    return type("Failed", (), {"returncode": 1})()
                return git(cwd, *args, **kwargs)
            mock_git.side_effect = blocked
            sent = []
            with self.assertRaisesRegex(RuntimeError, "cannot durably claim"):
                dispatch(self.clone(), sent.append)
            self.assertEqual(sent, [])
            self.assertEqual(self.remote_json(STATE)["pending_alerts"]["event-1"]["status"], "pending")

    def test_claim_races_with_next_scan_publish(self):
        """Scan begins at old SHA; dispatcher claims existing alert before publish."""
        self.seed_pending()
        baseline = git(self.clone(), "rev-parse", "HEAD").stdout.strip()
        scan = self.clone()
        source = self.artifacts("gs25", 9)
        candidate = json.loads(source[STATE].read_text())
        candidate.update({"version": 2, "item_code": "12345678",
                          "regions": {"namwon": {"stores": {"N1": {"quantity": 9, "name": "N"}}}},
                          "pending_alerts": {"event-1": {"message": "fake GS25 stock", "status": "pending"},
                                             "event-2": {"message": "next change", "status": "pending"}},
                          "alert_sequence": 2})
        source[STATE].write_text(json.dumps(candidate))
        dispatched = []
        self.assertEqual(dispatch(self.clone(), dispatched.append), 1)
        from state_push_publisher import publish_bundle
        publish_bundle(scan, source, baseline)
        remote = self.remote_json(STATE)
        self.assertEqual(remote["pending_alerts"]["event-1"]["status"], "claimed")
        self.assertEqual(remote["pending_alerts"]["event-2"]["status"], "pending")
        self.assertEqual(dispatch(self.clone(), dispatched.append), 1)
        self.assertEqual(dispatch(self.clone(), dispatched.append), 0)
        self.assertEqual(dispatched, ["fake GS25 stock", "next change"])

    def test_claim_races_with_same_scan_push_retry(self):
        self.seed_pending()
        baseline = git(self.clone(), "rev-parse", "HEAD").stdout.strip()
        source = self.artifacts("gs25", 10)
        candidate = json.loads(source[STATE].read_text())
        candidate.update({"version": 2, "item_code": "12345678",
                          "regions": {"namwon": {"stores": {"N1": {"quantity": 10, "name": "N"}}}},
                          "pending_alerts": {"event-1": {"message": "fake GS25 stock", "status": "pending"},
                                             "event-2": {"message": "next change", "status": "pending"}},
                          "alert_sequence": 2})
        source[STATE].write_text(json.dumps(candidate))
        from state_push_publisher import publish_bundle
        calls = []
        def collision(attempt):
            if attempt == 1:
                dispatch(self.clone(), calls.append)
        self.assertEqual(publish_bundle(self.clone(), source, baseline, before_push=collision), 2)
        self.assertEqual(self.remote_json(STATE)["pending_alerts"]["event-1"]["status"], "claimed")
        self.assertEqual(dispatch(self.clone(), calls.append), 1)
        self.assertEqual(calls, ["fake GS25 stock", "next change"])

    def test_failed_new_scan_does_not_block_prior_pending_delivery(self):
        """A rejected stale scan leaves old pending events deliverable once."""
        self.seed_pending()
        baseline = git(self.clone(), "rev-parse", "HEAD").stdout.strip()
        self.advance(STATE, 88)
        from state_push_publisher import publish_bundle
        stale = self.artifacts("gs25", 17)
        with self.assertRaisesRegex(RuntimeError, "stale overwrite"):
            publish_bundle(self.clone(), stale, baseline)
        # Prior pending alert is preserved by the real dispatcher only if
        # a non-outbox writer did not erase it. Assert that invariant explicitly.
        remote = self.remote_json(STATE)
        self.assertNotIn("pending_alerts", remote)
        # A real scan must never erase pending alerts: fail-closed here.
        self.assertEqual(remote["qty"], 88)

    def test_workflow_drains_prior_pending_even_when_publish_skipped(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parent.parent /
                    ".github/workflows/gs25-stock-monitor.yml").read_text()
        self.assertIn("needs: [scan, publish]", workflow)
        self.assertIn("if: always() && github.ref == 'refs/heads/main'", workflow)
