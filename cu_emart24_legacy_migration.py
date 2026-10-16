"""Pure, offline legacy-state migration. NEVER modifies its input or sends alerts.

Retain every legacy key/value; initialize an empty outbox with sequence zero.
The original Git blobs must be backed up separately before a real cutover.
"""
import copy
import hashlib
import json
from cu_emart24_state_store import FILES,validate

EXPECTED_PATHS=frozenset(("cu_stock_state.json","state.json","stores.json"))
METADATA=("pending_alerts","alert_sequence")


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def check_legacy(source):
    if set(source)!=EXPECTED_PATHS:
        raise ValueError("legacy source must have exactly three state files")
    cu=source["cu_stock_state.json"]
    em=source["state.json"]
    stores=source["stores.json"]
    if not isinstance(cu,dict) or not isinstance(cu.get("stores"),dict):
        raise ValueError("invalid CU legacy state")
    if not isinstance(em,dict) or not isinstance(stores,dict) or not isinstance(stores.get("stores"),dict):
        raise ValueError("invalid emart24 legacy state")
    if any(key in cu or key in em for key in METADATA):
        raise ValueError("outbox already present; do not reinitialize")
    for code,record in cu["stores"].items():
        if not isinstance(code,str) or not isinstance(record,dict):
            raise ValueError("invalid CU store record")
        if type(record.get("alerted")) is not bool:
            raise ValueError("CU alerted flag must be boolean")
        qty=record.get("stock")
        if qty is not None and (type(qty) is not int or qty<0):
            raise ValueError("invalid CU stock quantity")
    for key,value in em.items():
        if not isinstance(key,str) or type(value) is not int or value<0:
            raise ValueError("invalid emart24 stock entry")
    return True


def migrate(source,source_commit,source_blob_shas):
    check_legacy(source)
    if not isinstance(source_commit,str) or len(source_commit)!=40:
        raise ValueError("full source commit required")
    if set(source_blob_shas)!=EXPECTED_PATHS or not all(
        isinstance(v,str) and len(v)==40 for v in source_blob_shas.values()
    ):
        raise ValueError("source Git blob SHAs required")
    original=copy.deepcopy(source)
    staged=copy.deepcopy(source)
    for chain in FILES:
        state=staged[FILES[chain][0]]
        state["pending_alerts"]={}
        state["alert_sequence"]=0
        validate(chain,{path:staged[path] for path in FILES[chain]})
    manifest={
        "source_commit":source_commit,
        "source_blobs":copy.deepcopy(source_blob_shas),
        "source_sha256":{path:digest(original[path]) for path in sorted(EXPECTED_PATHS)},
        "migrated_sha256":{path:digest(staged[path]) for path in sorted(EXPECTED_PATHS)},
        "cu_store_count":len(original["cu_stock_state.json"]["stores"]),
        "emart24_cache_count":len(original["stores.json"]["stores"]),
        "requires_operator_reconciliation":True,
        "historical_telegram_delivery_inferred":False,
    }
    verify(source,staged,manifest)
    return staged,manifest


def verify(source,staged,manifest):
    check_legacy(source)
    if set(staged)!=EXPECTED_PATHS or set(manifest["source_sha256"])!=EXPECTED_PATHS:
        raise ValueError("file set mismatch")
    for path in EXPECTED_PATHS:
        if digest(source[path])!=manifest["source_sha256"][path]:
            raise ValueError("source checksum mismatch: "+path)
        if digest(staged[path])!=manifest["migrated_sha256"][path]:
            raise ValueError("migration checksum mismatch: "+path)
        expected=copy.deepcopy(source[path])
        if path in (FILES["cu"][0],FILES["emart24"][0]):
            expected["pending_alerts"]={}
            expected["alert_sequence"]=0
        if staged[path]!=expected:
            raise ValueError("legacy fields were modified: "+path)
    return True


def rollback_snapshot(source,manifest):
    check_legacy(source)
    if any(digest(source[p])!=manifest["source_sha256"][p] for p in EXPECTED_PATHS):
        raise ValueError("backup integrity failure")
    return copy.deepcopy(source)
