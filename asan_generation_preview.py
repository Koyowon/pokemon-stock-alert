"""Offline, append-only Asan preview generations; no network or state changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
from asan_preview_export import make_preview, REPO_ROOT
from asan_log_preview import parse_monitor_log

FILES = ("preview.txt", "preview.json")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


def _write(path, data):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def save_generation(snapshot, root, *, run_id=None, input_path=None):
    """Publish manifest only after both files are written and verified."""
    preview = make_preview(snapshot)
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid output root")
    root = root.resolve()
    if root == REPO_ROOT or root.is_relative_to(REPO_ROOT):
        raise ValueError("Output root inside repository")
    if input_path is not None and Path(input_path).resolve().is_relative_to(root):
        raise ValueError("Input overlaps output root")
    run_id = run_id if run_id is not None else uuid.uuid4().hex
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("Unsafe run ID")
    folder = root / run_id
    folder.mkdir(mode=0o700, exist_ok=False)
    data = {
        FILES[0]: ("\n\n".join(preview["pages"]) + "\n").encode("utf-8"),
        FILES[1]: (json.dumps(preview, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    }
    for name in FILES:
        _write(folder / name, data[name])
    for name in FILES:
        if (folder / name).read_bytes() != data[name]:
            raise IOError("Written preview mismatch")
    manifest = {
        "schema_version": 1, "run_id": run_id,
        "files": {name: {"sha256": hashlib.sha256(data[name]).hexdigest(), "bytes": len(data[name])} for name in FILES},
        "candidate_count": preview["candidate_count"], "page_count": preview["page_count"],
    }
    pending = folder / ".manifest.pending"
    _write(pending, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    os.replace(pending, folder / "manifest.json")
    return folder


def read_generation(folder):
    """Reject unfinished, modified, or mismatched TXT/JSON generations."""
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir() or not RUN_ID.fullmatch(folder.name):
        raise ValueError("Invalid generation directory")
    marker = folder / "manifest.json"
    if marker.is_symlink() or not marker.is_file():
        raise ValueError("Generation not complete")
    try:
        manifest = json.loads(marker.read_text(encoding="utf-8"))
        if manifest["schema_version"] != 1 or manifest["run_id"] != folder.name or set(manifest["files"]) != set(FILES):
            raise ValueError("Invalid manifest")
        data = {}
        for name in FILES:
            path = folder / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Missing or linked file")
            raw = path.read_bytes()
            meta = manifest["files"][name]
            if len(raw) != meta["bytes"] or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
                raise ValueError("Checksum mismatch")
            data[name] = raw
        preview = json.loads(data["preview.json"].decode("utf-8"))
        if preview["candidate_count"] != manifest["candidate_count"] or preview["page_count"] != manifest["page_count"]:
            raise ValueError("Summary mismatch")
        if data["preview.txt"].decode("utf-8") != "\n\n".join(preview["pages"]) + "\n":
            raise ValueError("TXT/JSON mismatch")
        if any(len(p) > 4096 for p in preview["pages"]):
            raise ValueError("Telegram page too long")
        return preview
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid generation") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline Asan CU generation preview")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    snapshot = parse_monitor_log(args.log.read_text(encoding="utf-8"))
    folder = save_generation(snapshot, args.output_root, run_id=args.run_id, input_path=args.log)
    read_generation(folder)
    print("ASAN_GENERATION_PREVIEW_OK:", folder)


if __name__ == "__main__":
    main()
