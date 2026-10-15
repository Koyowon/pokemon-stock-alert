"""GS25 at-most-once alert dispatcher.

Claims are committed to Git BEFORE Telegram is invoked. Ambiguous sends are
never automatically retried. This prevents duplicate automatic notifications
but can lose an alert if the process fails after claim and before delivery.
"""
import json
import os
from pathlib import Path
from state_push_publisher import git

STATE = "gs25_independent/gs25_stock_state.json"


def dispatch(repo, send, max_attempts=3, after_claim=None):
    repo = Path(repo).resolve()
    if os.environ.get("STATE_PUBLISH_APPROVED") != "1" or os.environ.get("GITHUB_REPOSITORY") != "Koyowon/pokemon-stock-alert" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("GS25 dispatcher not authorized")
    remote = git(repo, "remote", "get-url", "origin").stdout.strip()
    offline = (os.environ.get("STATE_PUBLISH_OFFLINE_TEST") == "1"
               and os.environ.get("GIT_ALLOW_PROTOCOL") == "file"
               and remote.startswith("file://"))
    if not offline and remote not in ("https://github.com/Koyowon/pokemon-stock-alert",
                                     "https://github.com/Koyowon/pokemon-stock-alert.git"):
        raise RuntimeError("untrusted Git remote")
    if not (repo / ".git").is_dir() or git(repo, "status", "--porcelain").stdout.strip():
        raise RuntimeError("requires clean checkout")
    claimed = []
    for attempt in range(max_attempts):
        git(repo, "fetch", "origin", "main")
        git(repo, "reset", "--hard", "FETCH_HEAD")
        target = repo / STATE
        state = json.loads(target.read_text(encoding="utf-8"))
        pending = state.get("pending_alerts", {})
        if not isinstance(pending, dict):
            raise ValueError("invalid alert outbox")
        keys = sorted(k for k, v in pending.items()
                      if isinstance(v, dict) and v.get("status") == "pending")
        if not keys:
            return 0
        for key in keys:
            if not isinstance(pending[key].get("message"), str):
                raise ValueError("invalid alert message")
            pending[key]["status"] = "claimed"
        target.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        git(repo, "add", "--", STATE)
        git(repo, "-c", "user.name=github-actions[bot]",
            "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-m", "Claim GS25 notifications before sending [skip ci]")
        if git(repo, "push", "origin", "HEAD:refs/heads/main", check=False).returncode == 0:
            claimed = [(key, pending[key]["message"]) for key in keys]
            break
    else:
        raise RuntimeError("cannot durably claim GS25 alerts; no sends performed")
    if after_claim:
        after_claim()
    sent = 0
    for key, message in claimed:
        try:
            send(message)
            sent += 1
        except Exception as exc:
            # Fail closed: no retry, since delivery may have succeeded.
            print("GS25_DELIVERY_AMBIGUOUS key=" + key[:12] + " error=" + type(exc).__name__, flush=True)
    return sent


def main():
    from gs25_independent.gs25_auto_monitor import telegram
    count = dispatch(os.environ["GITHUB_WORKSPACE"], telegram)
    print("GS25_DISPATCHED=" + str(count))


if __name__ == "__main__":
    main()
