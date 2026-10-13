"""Conservative offline cleanup of abandoned Asan preview generations."""
import argparse
import stat
import time
from pathlib import Path
from asan_generation_preview import RUN_ID
from asan_preview_export import REPO_ROOT

ALLOWED = frozenset({"preview.txt", "preview.json", ".manifest.pending"})


def inspect(root, *, min_age_seconds=86400, now=None):
    """Select only aged, unmarked, regular-file-only run directories."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid cleanup root")
    root = root.resolve()
    if root == REPO_ROOT or root.is_relative_to(REPO_ROOT):
        raise ValueError("Cannot clean inside repository")
    if min_age_seconds < 3600:
        raise ValueError("Minimum age must be at least one hour")
    now = time.time() if now is None else now
    results = []
    for folder in sorted(root.iterdir()):
        if folder.is_symlink() or not folder.is_dir() or not RUN_ID.fullmatch(folder.name):
            continue
        marker = folder / "manifest.json"
        if marker.exists() or marker.is_symlink():
            continue
        children = list(folder.iterdir())
        if not children or any(
            child.name not in ALLOWED
            or not stat.S_ISREG(child.lstat().st_mode)
            or child.stat().st_nlink != 1
            for child in children
        ):
            continue
        if now - max([folder.stat().st_mtime] + [p.stat().st_mtime for p in children]) < min_age_seconds:
            continue
        results.append(folder)
    return results


def cleanup(root, *, apply=False, min_age_seconds=86400, now=None):
    """Dry-run by default; recheck candidates before deletion."""
    candidates = inspect(root, min_age_seconds=min_age_seconds, now=now)
    if not apply:
        return {"dry_run": True, "candidates": [str(p) for p in candidates], "deleted": []}
    deleted = []
    for folder in candidates:
        if folder not in inspect(root, min_age_seconds=min_age_seconds, now=now):
            continue
        children = list(folder.iterdir())
        try:
            for child in children:
                if (child.name not in ALLOWED
                    or not stat.S_ISREG(child.lstat().st_mode)
                    or child.stat().st_nlink != 1):
                    raise ValueError("Candidate changed")
            for child in children:
                child.unlink()
            folder.rmdir()
            deleted.append(str(folder))
        except (OSError, ValueError):
            continue
    return {"dry_run": False, "candidates": [str(p) for p in candidates], "deleted": deleted}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline Asan incomplete generation cleanup (dry-run default)")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--min-age-seconds", type=int, default=86400)
    args = parser.parse_args(argv)
    print(cleanup(args.root, apply=args.apply, min_age_seconds=args.min_age_seconds))


if __name__ == "__main__":
    main()
