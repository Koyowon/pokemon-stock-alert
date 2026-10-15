"""CANDIDATE ONLY: publish one chain's state with bounded Git push retries.

Do not invoke from production workflows until separately approved.
Designed for a disposable clean checkout and a separate state artifact.
"""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ALLOWED = {
    "state.json",
    "stores.json",
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
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{revision}:{path}"],
        capture_output=True, check=False,
    )
    if result.returncode:
        exists = git(repo, "cat-file", "-e", f"{revision}^{{commit}}", check=False)
        if exists.returncode:
            raise RuntimeError("cannot resolve git revision")
        tracked = git(repo, "ls-tree", "-r", "--name-only", revision)
        if path in tracked.stdout.splitlines():
            raise RuntimeError("cannot read tracked state file")
        return None
    return result.stdout


def validate_artifact(artifact, expected_digest=None):
    if artifact.is_symlink() or not artifact.is_file():
        raise ValueError("artifact must be a regular file")
    data = artifact.read_bytes()
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid JSON artifact") from exc
    if not isinstance(parsed, dict):
        raise ValueError("JSON state must be an object")
    if expected_digest is not None and hashlib.sha256(data).hexdigest() != expected_digest:
        raise ValueError("artifact checksum mismatch")
    return data


def publish_bundle(repo, artifacts, base_sha, max_attempts=3,
                   before_push=None, expected_digests=None):
    """Publish exactly one chain's validated state bundle; return attempt count."""
    repo = Path(repo).resolve()
    paths = set(artifacts)
    if not paths or not (paths <= ALLOWED):
        raise ValueError("state path not allowlisted")
    if "stores.json" in paths and paths != {"state.json", "stores.json"}:
        raise ValueError("emart24 cache must be bundled with inventory state")
    if "state.json" in paths and paths != {"state.json", "stores.json"}:
        raise ValueError("emart24 state requires stores.json")
    if len(paths) > 1 and paths != {"state.json", "stores.json"}:
        raise ValueError("mixed-chain state bundle rejected")
    if not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be 1..5")
    if not (repo / ".git").is_dir():
        raise RuntimeError("requires a disposable normal Git checkout")
    if git(repo, "status", "--porcelain").stdout.strip():
        raise RuntimeError("checkout must be clean")
    if git(repo, "rev-parse", "--verify", f"{base_sha}^{{commit}}", check=False).returncode:
        raise RuntimeError("invalid baseline commit")
    data = {}
    for name, artifact in artifacts.items():
        source = Path(artifact)
        if not source.is_absolute():
            raise ValueError("artifact path must be absolute")
        if repo == source.resolve() or repo in source.resolve().parents:
            raise ValueError("artifact must be outside checkout")
        data[name] = validate_artifact(
            source, (expected_digests or {}).get(name)
        )
    original = {name: state_at(repo, base_sha, name) for name in paths}
    for attempt in range(1, max_attempts + 1):
        git(repo, "fetch", "origin", "main")
        remote = {name: state_at(repo, "FETCH_HEAD", name) for name in paths}
        for name in paths:
            if remote[name] != original[name] and remote[name] != data[name]:
                raise RuntimeError(f"same-chain state changed remotely; refusing stale overwrite: {name}")
        git(repo, "reset", "--hard", "FETCH_HEAD")
        for name in sorted(paths):
            target = repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data[name])
        git(repo, "add", "--", *sorted(paths))
        if git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0:
            return attempt
        git(repo, "-c", "user.name=github-actions[bot]",
            "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-m", "Update isolated chain state [skip ci]")
        if before_push is not None:
            before_push(attempt)
        if git(repo, "push", "origin", "HEAD:refs/heads/main", check=False).returncode == 0:
            return attempt
    raise RuntimeError(f"push retry exhausted after {max_attempts} attempts")


def publish(repo, state_path, artifact, base_sha, max_attempts=3, before_push=None):
    if state_path == "state.json":
        raise ValueError("emart24 requires state.json and stores.json bundle")
    return publish_bundle(repo, {state_path: artifact}, base_sha,
                          max_attempts=max_attempts, before_push=before_push)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--state-file", required=True, choices=sorted(ALLOWED))
    parser.add_argument("--artifact")
    parser.add_argument("--stores-artifact")
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    if args.state_file == "state.json":
        if not args.artifact or not args.stores_artifact:
            parser.error("emart24 requires --artifact and --stores-artifact")
        count = publish_bundle(args.repo, {"state.json": args.artifact,
                                           "stores.json": args.stores_artifact},
                               args.base_sha, args.max_attempts)
    else:
        if not args.artifact or args.stores_artifact or args.state_file == "stores.json":
            parser.error("single-chain publish requires --artifact only")
        count = publish(args.repo, args.state_file, args.artifact,
                        args.base_sha, args.max_attempts)
    print(f"STATE_PUSH_SUCCESS attempts={count}")


if __name__ == "__main__":
    main()
