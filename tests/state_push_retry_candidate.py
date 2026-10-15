"""CANDIDATE ONLY: publish one chain's state with bounded Git push retries.

Do not invoke from production workflows until separately approved.
Designed for a disposable clean checkout and a separate state artifact.
"""
import argparse
import os
import subprocess
from pathlib import Path

ALLOWED = {
    "state.json",
    "cu_stock_state.json",
    "gs25_independent/gs25_stock_state.json",
}


def git(repo, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=False,
    )
    if check and result.returncode:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result


def state_at(repo, revision, path):
    result = git(repo, "show", f"{revision}:{path}", check=False)
    if result.returncode:
        # Missing at both revisions is acceptable; a mismatch is not.
        return None
    return result.stdout.encode("utf-8")


def publish(repo, state_path, artifact, base_sha, max_attempts=3, before_push=None):
    """Return attempt count. Never rerun scans or send alerts on push retry."""
    repo = Path(repo).resolve()
    artifact = Path(artifact).resolve()
    if state_path not in ALLOWED:
        raise ValueError("state path not allowlisted")
    if not artifact.is_file() or repo in artifact.parents:
        raise ValueError("artifact must be an existing file outside the checkout")
    if not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be 1..5")
    if git(repo, "status", "--porcelain").stdout.strip():
        raise RuntimeError("checkout must be clean")
    if not git(repo, "rev-parse", "--verify", f"{base_sha}^{{commit}}", check=False).returncode == 0:
        raise RuntimeError("invalid baseline commit")
    if not (repo / ".git").exists():
        raise RuntimeError("requires a disposable normal Git checkout")

    data = artifact.read_bytes()
    # Candidate's baseline is the scan checkout commit, not a retry commit.
    original = state_at(repo, base_sha, state_path)
    for attempt in range(1, max_attempts + 1):
        git(repo, "fetch", "origin", "main")
        remote = state_at(repo, "FETCH_HEAD", state_path)
        if remote != original and remote != data:
            raise RuntimeError("same-chain state changed remotely; refusing stale overwrite")
        # Safe only in a clean, disposable checkout. Other chain states come
        # from the newest remote commit, not the original scan checkout.
        git(repo, "reset", "--hard", "FETCH_HEAD")
        target = repo / state_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        git(repo, "add", "--", state_path)
        if not git(repo, "diff", "--cached", "--quiet", check=False).returncode:
            return attempt
        git(repo, "-c", "user.name=github-actions[bot]",
            "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-m", f"Update {state_path} [skip ci]")
        if before_push is not None:
            before_push(attempt)
        pushed = git(repo, "push", "origin", "HEAD:refs/heads/main", check=False)
        if pushed.returncode == 0:
            return attempt
    raise RuntimeError(f"push retry exhausted after {max_attempts} attempts")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--state-file", required=True, choices=sorted(ALLOWED))
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    count = publish(args.repo, args.state_file, args.artifact,
                    args.base_sha, args.max_attempts)
    print(f"STATE_PUSH_SUCCESS attempts={count}")


if __name__ == "__main__":
    main()
