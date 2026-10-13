"""Offline Asan Telegram preview export. No stock API or Telegram calls."""
import argparse
import json
import os
from collections import Counter
from pathlib import Path
from asan_stock_chunks import preview_asan_stock_messages, TELEGRAM_TEXT_LIMIT
from asan_stock_message import format_asan_stock_message

def make_preview(snapshot):
    """Validate 123 stores and build Telegram-safe text pages."""
    rows = snapshot["candidates"]
    if len(rows) != 123 or snapshot.get("candidate_count") != 123:
        raise ValueError("Expected 123 Asan registry candidates")
    ids = [row["registry_id"] for row in rows]
    if len(set(ids)) != 123:
        raise ValueError("Duplicate registry ID")
    original = format_asan_stock_message(snapshot)
    pages = preview_asan_stock_messages(snapshot)
    if any(len(page) > TELEGRAM_TEXT_LIMIT for page in pages):
        raise ValueError("Telegram page length exceeded")
    restored = pages[0] if len(pages) == 1 else "\n".join(page.split("\n", 1)[1] for page in pages)
    if restored != original:
        raise ValueError("Preview pages do not reconstruct original message")
    for rid in ids:
        if original.count(f"[{rid}]") != 1:
            raise ValueError(f"Missing or duplicate registry ID: {rid}")
    counts = Counter(row["status"] for row in rows)
    categories = {
        "in_stock": counts["IN_STOCK"],
        "zero_stock": counts["ZERO_STOCK"],
        "not_observed": counts["NOT_OBSERVED"],
        "not_queried": counts["NOT_QUERIED"],
        "invalid_stock": counts["NO_VALID_STOCK_VALUE"],
    }
    if sum(categories.values()) != 123:
        raise ValueError("Unexpected snapshot status")
    return {
        "barcode": snapshot["barcode"],
        "candidate_count": 123,
        "page_count": len(pages),
        "page_lengths": [len(page) for page in pages],
        "categories": categories,
        "missing_registry_ids": [],
        "pages": pages,
    }

PROTECTED_NAMES = frozenset({
    "cu_stock_state.json", "asan_cu_watch_registry.json",
    "cu_stock_monitor.py", "asan_preview_export.py", "asan_log_preview.py",
    "asan_stock_snapshot.py", "asan_stock_message.py", "asan_stock_chunks.py",
    ".gitignore", "README.md",
})
REPO_ROOT = Path(__file__).resolve().parent


def validate_output_paths(txt_path, json_path, *, input_path=None):
    """Fail closed on protected, linked, or overlapping output paths."""
    targets = [Path(txt_path), Path(json_path)]
    protected = [Path(input_path)] if input_path is not None else []
    protected += [REPO_ROOT / name for name in PROTECTED_NAMES]
    resolved = []
    for target in targets:
        if target.is_symlink():
            raise ValueError("Symlink output path forbidden")
        canonical = target.resolve()
        if target.name in PROTECTED_NAMES:
            raise ValueError("Protected repository/state filename")
        if canonical.is_relative_to(REPO_ROOT) and (
            canonical.suffix in {".py", ".yml", ".yaml", ".toml", ".ini", ".sh"}
            or ".git" in canonical.relative_to(REPO_ROOT).parts
        ):
            raise ValueError("Repository source/config output forbidden")
        for item in protected:
            if canonical == item.resolve() or (
                target.exists() and item.exists() and target.samefile(item)
            ):
                raise ValueError("Output collides with protected input or state")
        resolved.append(canonical)
    if resolved[0] == resolved[1] or (
        targets[0].exists() and targets[1].exists()
        and targets[0].samefile(targets[1])
    ):
        raise ValueError("TXT and JSON output paths overlap")
    return targets


def write_preview(snapshot, txt_path, json_path, *, input_path=None):
    """Stage both outputs and roll back if a commit fails (not crash-atomic)."""
    import os
    import shutil
    import tempfile

    preview = make_preview(snapshot)
    txt_path, json_path = validate_output_paths(txt_path, json_path, input_path=input_path)
    payloads = (
        (txt_path, ("\n\n".join(preview["pages"]) + "\n").encode("utf-8")),
        (json_path, (json.dumps(preview, ensure_ascii=False, indent=2) + "\n").encode("utf-8")),
    )
    staged, backups, committed = {}, {}, []
    preserve_backups = False
    try:
        for target, payload in payloads:
            if not target.parent.is_dir() or (target.exists() and not target.is_file()):
                raise ValueError("Invalid preview output path")
            fd, name = tempfile.mkstemp(prefix=".asan-preview-", dir=target.parent)
            staged[target] = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if target.exists():
                fd, name = tempfile.mkstemp(prefix=".asan-backup-", dir=target.parent)
                os.close(fd)
                backups[target] = Path(name)
                shutil.copy2(target, backups[target])
        try:
            for target, _ in payloads:
                os.replace(staged[target], target)
                committed.append(target)
        except OSError as commit_error:
            rollback_errors = []
            for target in reversed(committed):
                try:
                    if target in backups:
                        os.replace(backups[target], target)
                    else:
                        target.unlink(missing_ok=True)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            if rollback_errors:
                preserve_backups = True
                raise RuntimeError(
                    'Preview commit failed; rollback failed; backup files preserved'
                ) from commit_error
            raise
        return preview
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)
        if not preserve_backups:
            for path in backups.values():
                path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline-only Asan CU preview exporter")
    parser.add_argument("--snapshot", required=True, type=Path, help="Local snapshot JSON; no API access")
    parser.add_argument("--txt", required=True, type=Path)
    parser.add_argument("--json", required=True, type=Path)
    args = parser.parse_args(argv)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    report = write_preview(snapshot, args.txt, args.json)
    print("ASAN_PREVIEW_OK:", report["candidate_count"], "stores,", report["page_count"], "pages")

if __name__ == "__main__":
    main()
