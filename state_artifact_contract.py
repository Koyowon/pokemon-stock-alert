"""OFFLINE CANDIDATE: verify run-scoped state artifacts and safely recover publication.

This models upload/download via local directories, not GitHub artifact service.
"""
import hashlib
import json
import re
import shutil
from pathlib import Path
from state_push_publisher import publish_bundle, ALLOWED

CHAINS = {
    "cu": ("cu_stock_state.json",),
    "gs25": ("gs25_independent/gs25_stock_state.json",),
    "emart24": ("state.json", "stores.json"),
}
SHA = re.compile(r"^[0-9a-f]{40}$")


def prepare(source, destination, chain, run_id, attempt, base_sha):
    if chain not in CHAINS or not str(run_id).isdigit() or int(run_id) < 1:
        raise ValueError("invalid artifact metadata")
    if not isinstance(attempt, int) or attempt < 1 or not SHA.fullmatch(base_sha):
        raise ValueError("invalid artifact metadata")
    destination = Path(destination)
    if destination.exists():
        raise ValueError("artifact upload target already exists")
    destination.mkdir(parents=True)
    try:
        files = {}
        for name in CHAINS[chain]:
            src = Path(source) / name
            if src.is_symlink() or not src.is_file():
                raise ValueError("missing or linked artifact file")
            raw = src.read_bytes()
            if not isinstance(json.loads(raw.decode("utf-8")), dict):
                raise ValueError("invalid state JSON object")
            dst = destination / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(raw)
            files[name] = hashlib.sha256(raw).hexdigest()
        manifest = dict(schema=1, chain=chain, run_id=str(run_id),
                        attempt=attempt, base_sha=base_sha, files=files)
        (destination / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True), encoding="utf-8")
        return manifest
    except Exception:
        shutil.rmtree(destination)
        raise


def verify(directory, chain, run_id, attempt, base_sha, expected_manifest_sha256=None):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("missing download artifact")
    manifest_path = directory / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("missing artifact manifest")
    if expected_manifest_sha256 is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256):
            raise ValueError("invalid trusted manifest digest")
        if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != expected_manifest_sha256:
            raise ValueError("trusted manifest digest mismatch")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid artifact manifest") from exc
    if not isinstance(manifest, dict) or (
        manifest.get("schema") != 1 or manifest.get("chain") != chain or
        manifest.get("run_id") != str(run_id) or manifest.get("attempt") != attempt or
        manifest.get("base_sha") != base_sha or
        set(manifest.get("files", {})) != set(CHAINS.get(chain, ()))
    ):
        raise ValueError("artifact metadata mismatch")
    artifacts = {}
    for name, expected in manifest["files"].items():
        if name not in ALLOWED or not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("invalid artifact digest")
        p = directory / name
        if p.is_symlink() or not p.is_file():
            raise ValueError("missing or linked downloaded file")
        raw = p.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("artifact checksum mismatch")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("invalid JSON artifact") from exc
        if not isinstance(parsed, dict):
            raise ValueError("invalid state JSON object")
        artifacts[name] = p
    return artifacts, manifest["files"]


def recover(repo, directory, chain, run_id, attempt, base_sha, expected_manifest_sha256=None):
    """Retry publication only after full verification; never repeat scan/alerts."""
    artifacts, digests = verify(directory, chain, run_id, attempt, base_sha, expected_manifest_sha256)
    return publish_bundle(repo, artifacts, base_sha, expected_digests=digests)
