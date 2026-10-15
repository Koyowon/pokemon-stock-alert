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
