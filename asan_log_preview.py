"""Offline-only conversion of completed CU monitor logs to previews."""
import argparse
import json
import re
from pathlib import Path
from asan_preview_export import make_preview, write_preview
from cu_asan_registry import load_registry, PRODUCT_BARCODE

MARKER = "ASAN_CU_STOCK_SNAPSHOT:"
MAX_LOG_BYTES = 8_000_000

def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key: " + key)
        result[key] = value
    return result

def parse_monitor_log(log_text):
    """Reject missing, ambiguous, incomplete or partial Asan observations."""
    if not isinstance(log_text, str) or len(log_text.encode("utf-8")) > MAX_LOG_BYTES:
        raise ValueError("Invalid or oversized log")
    lines = log_text.splitlines()
    markers = [line.split(MARKER, 1)[1].strip() for line in lines if MARKER in line]
    if len(markers) != 1:
        raise ValueError("Expected exactly one Asan snapshot log entry")
    if sum(line.strip() == "CU STOCK MONITOR FINISHED" for line in lines) != 1:
        raise ValueError("Monitor run is incomplete")
    if any("ASAN_CU_DIAGNOSTIC_ERROR:" in line for line in lines):
        raise ValueError("Asan diagnostic failed")
    success = sum(bool(re.match(r"^QUERY_OK:\s+아산\s", line.strip())) for line in lines)
    failed = sum(bool(re.match(r"^QUERY_ERROR:\s+아산\s", line.strip())) for line in lines)
    if success != 7 or failed:
        raise ValueError("Incomplete Asan coordinate queries")
    try:
        snapshot = json.loads(markers[0], object_pairs_hook=_unique_pairs)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Malformed snapshot JSON") from exc
    if not isinstance(snapshot, dict) or snapshot.get("barcode") != PRODUCT_BARCODE:
        raise ValueError("Invalid snapshot barcode")
    if snapshot.get("query_succeeded") is not True:
        raise ValueError("Snapshot was not successfully queried")
    rows = snapshot.get("candidates")
    if not isinstance(rows, list) or len(rows) != 123 or snapshot.get("candidate_count") != 123:
        raise ValueError("Snapshot must contain 123 candidates")
    expected = {s["registry_id"] for s in load_registry()}
    actual = [r.get("registry_id") for r in rows if isinstance(r, dict)]
    if len(actual) != 123 or set(actual) != expected or len(set(actual)) != 123:
        raise ValueError("Registry ID set differs from approved registry")
    if any(r.get("status") == "NOT_QUERIED" for r in rows):
        raise ValueError("Partial observation contains NOT_QUERIED")
    make_preview(snapshot)
    return snapshot

def convert_monitor_log(log_path, txt_path, json_path):
    """Write only requested preview files after complete validation."""
    snapshot = parse_monitor_log(Path(log_path).read_text(encoding="utf-8"))
    return write_preview(snapshot, txt_path, json_path)

def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline CU monitor log to preview converter")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--txt", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)
    report = convert_monitor_log(args.log, args.txt, args.json)
    print("ASAN_LOG_PREVIEW_OK:", report["candidate_count"], report["page_count"])

if __name__ == "__main__":
    main()
