"""Separate GitHub-branch persistence for Asan status, with optimistic CAS.

No network occurs on import. Inject an adapter implementing read() and cas().
The adapter must implement compare-and-swap against a remote branch ref, not
merely a read-then-write of a GitHub Contents API file SHA.
"""
import hashlib
import json
import subprocess

STATE_BRANCH = "state/asan-cu-status"
STATE_PATH = "asan_status_delivery_state.json"


class PersistenceError(RuntimeError):
    pass


class GitBranchCAS:
    """Dedicated state branch CAS using immutable Git objects and a ref lease."""

    def __init__(self, repository, *, remote="origin", branch=STATE_BRANCH):
        from pathlib import Path
        self.repository = str(Path(repository).resolve())
        if not isinstance(remote, str) or not remote or remote.startswith("-") or any(c.isspace() for c in remote):
            raise ValueError("Invalid remote")
        if branch != STATE_BRANCH:
            raise ValueError("Only dedicated Asan state branch is permitted")
        self.remote, self.branch = remote, branch

    @staticmethod
    def _environment():
        import os
        return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}

    def _git(self, *args, input=None):
        try:
            result = subprocess.run(["git", "-C", self.repository, *args],
                                    input=input, text=True, capture_output=True,
                                    check=True, timeout=30, env=self._environment())
            return result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            raise PersistenceError("Git state operation failed") from exc

    def _remote_oid(self):
        lines = self._git("ls-remote", "--refs", self.remote,
                          "refs/heads/" + self.branch).splitlines()
        if len(lines) != 1:
            raise PersistenceError("Missing or ambiguous dedicated state ref")
        oid, ref = lines[0].split("\t")
        if (ref != "refs/heads/" + self.branch or len(oid) not in (40, 64)
                or not all(c in "0123456789abcdef" for c in oid)):
            raise PersistenceError("Invalid remote ref")
        return oid

    def read(self):
        oid = self._remote_oid()
        self._git("fetch", "--no-tags", self.remote, oid)
        raw = self._git("show", oid + ":" + STATE_PATH)
        try:
            state = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise PersistenceError("Invalid remote state JSON") from exc
        if not isinstance(state, dict):
            raise PersistenceError("Invalid remote state")
        return oid, state

    def cas(self, expected_revision, state):
        if not isinstance(state, dict) or state.get("state") not in ("READY", "IN_FLIGHT", "DONE"):
            raise ValueError("Invalid state")
        if not isinstance(expected_revision, str) or len(expected_revision) not in (40, 64):
            raise ValueError("Invalid expected revision")
        if self._remote_oid() != expected_revision:
            raise PersistenceError("Remote revision changed")
        if self._git("ls-tree", "--name-only", expected_revision) != STATE_PATH:
            raise PersistenceError("Dedicated branch must contain only its state file")
        blob = self._git("hash-object", "-w", "--stdin",
                         input=json.dumps(state, ensure_ascii=False, sort_keys=True) + "\n")
        tree_oid = self._git("mktree", input=f"100644 blob {blob}\t{STATE_PATH}\n")
        commit = self._git("commit-tree", tree_oid, "-p", expected_revision,
                           input="Update Asan CU status delivery journal\n")
        self._git("push", "--porcelain",
                  f"--force-with-lease=refs/heads/{self.branch}:{expected_revision}",
                  self.remote, f"{commit}:refs/heads/{self.branch}")
        return commit


def _digest(pages):
    return hashlib.sha256(json.dumps(pages, ensure_ascii=False).encode()).hexdigest()


def deliver_persistent(snapshot, pages, sender, adapter, *, enabled=False):
    """Fail closed on absent state branch, CAS failure, or uncertain delivery.

    adapter.read() -> (revision, state). A missing branch must raise.
    adapter.cas(expected_revision, state) -> new revision, or raise.
    IN_FLIGHT is intentionally never auto-retried, even after a send failure.
    """
    if not enabled:
        return "DISABLED"
    from asan_status_delivery import delivery_key
    key = delivery_key(snapshot)
    if not pages or any(not isinstance(p, str) or not p or len(p) > 4096 for p in pages):
        raise ValueError("Invalid pages")
    try:
        revision, old = adapter.read()
        if not revision or not isinstance(old, dict):
            return "STATE_UNAVAILABLE"
        if old.get("state") == "IN_FLIGHT":
            return "NEEDS_RECONCILIATION"
        if old.get("state") not in ("READY", "DONE"):
            return "INVALID_STATE"
        if old.get("state") == "DONE" and old.get("key") == key:
            return "UNCHANGED"
        revision = adapter.cas(revision, {"state": "IN_FLIGHT", "key": key,
                                          "pages_sha256": _digest(pages),
                                          "page_index": 0, "page_count": len(pages)})
    except Exception:
        return "STATE_UNAVAILABLE"
    for index, page in enumerate(pages):
        if index:
            try:
                revision = adapter.cas(revision, {"state": "IN_FLIGHT", "key": key,
                                                  "pages_sha256": _digest(pages),
                                                  "page_index": index,
                                                  "page_count": len(pages)})
            except Exception:
                return "NEEDS_RECONCILIATION"
        try:
            if sender(page) is not True:
                return "NEEDS_RECONCILIATION"
        except Exception:
            return "NEEDS_RECONCILIATION"
    try:
        adapter.cas(revision, {"state": "DONE", "key": key,
                               "pages_sha256": _digest(pages),
                               "page_count": len(pages)})
    except Exception:
        return "NEEDS_RECONCILIATION"
    return "SENT"
