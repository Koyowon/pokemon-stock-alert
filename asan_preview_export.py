"""Offline Asan Telegram preview export. No stock API or Telegram calls."""
import argparse
import json
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

def write_preview(snapshot, txt_path, json_path):
    """Write only explicitly requested local preview files."""
    preview = make_preview(snapshot)
    txt_path, json_path = Path(txt_path), Path(json_path)
    txt_path.write_text("\n\n".join(preview["pages"]) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return preview

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
