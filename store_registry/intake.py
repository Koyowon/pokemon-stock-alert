"""Strict offline intake for externally captured provider discovery JSON.

The input is untrusted. No remote calls, stock operations, state writes, or
self-attested production approvals are performed.
"""
import argparse
import hashlib
import json
from pathlib import Path

from store_registry.discovery_pipeline import inspect

MAX_BYTES = 2_000_000
ALLOWED = {"schema_version", "snapshots"}
SNAPSHOT_KEYS = {"chain", "region", "source", "captured_at", "payload"}
SOURCE_BY_CHAIN = {
    "cu": {"cu_parsed_inventory"},
    "emart24": {"emart24_store_directory", "emart24_seed"},
}


def validate_document(document):
    if not isinstance(document, dict) or set(document) != ALLOWED:
        raise ValueError("expected schema_version and snapshots only")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("unsupported schema_version")
    snapshots = document["snapshots"]
    if not isinstance(snapshots, list) or len(snapshots) > 32:
        raise ValueError("snapshots must be a list with at most 32 entries")
    for index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, dict) or set(snapshot) != SNAPSHOT_KEYS:
            raise ValueError(f"snapshot {index}: unexpected/missing keys")
        chain = snapshot["chain"]
        if chain not in SOURCE_BY_CHAIN or snapshot["source"] not in SOURCE_BY_CHAIN[chain]:
            raise ValueError(f"snapshot {index}: unsupported source")
        if snapshot["region"] not in ("namwon", "asan", "jeonju", "jeju"):
            raise ValueError(f"snapshot {index}: invalid region")
        timestamp = snapshot["captured_at"]
        if not isinstance(timestamp, str) or len(timestamp) > 40 or not timestamp.endswith("Z"):
            raise ValueError(f"snapshot {index}: captured_at must be UTC ISO8601")
        from datetime import datetime
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"snapshot {index}: invalid timestamp") from exc
        payload = snapshot["payload"]
        if not isinstance(payload, dict) or set(payload) != {"stores"}:
            raise ValueError(f"snapshot {index}: payload must contain stores only")
        stores = payload["stores"]
        if not isinstance(stores, (list, dict)) or len(stores) > 2000:
            raise ValueError(f"snapshot {index}: invalid store collection")
        if chain == "cu" and not isinstance(stores, list):
            raise ValueError(f"snapshot {index}: CU stores must be list")
        if any(not isinstance(row, dict) for row in (
                stores.values() if isinstance(stores, dict) else stores)):
            raise ValueError(f"snapshot {index}: store must be object")
    return snapshots


def load_file(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("snapshot file too large")
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("snapshot file too large")
    return validate_document(json.loads(raw.decode("utf-8"))), hashlib.sha256(raw).hexdigest()


def evaluate(root, path):
    snapshots, digest = load_file(path)
    result = inspect(root, snapshots)
    result["schema_version"] = 1
    result["input_sha256"] = digest
    result["untrusted_external_input"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description="Strict offline discovery JSON intake")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.root, args.input), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
