"""Executable CU/emart24 pipeline entrypoint. Disabled unless separately approved.

No import-time network. State branch access is delegated to the strict store
module. Scanner never sees Telegram secrets. A crashed claim is NOT replayed.
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from cu_emart24_state_store import fetch,publish,claim,record_attempts,unresolved
from cu_emart24_scan_adapter import scan_with_snapshot


def gate():
    if os.environ.get("CU_EMART24_LIVE_APPROVED")!="1":
        raise RuntimeError("live cutover not approved")
    if os.environ.get("GITHUB_REPOSITORY")!="Koyowon/pokemon-stock-alert":
        raise RuntimeError("unexpected repository")
    if os.environ.get("GITHUB_REF")!="refs/heads/main":
        raise RuntimeError("only approved main workflow may run live")


def telegram(message):
    token=os.environ.get("TELEGRAM_BOT_TOKEN","")
    chat=os.environ.get("TELEGRAM_CHAT_ID","")
    if not token or not chat:
        raise RuntimeError("Telegram credentials absent")
    payload=urllib.parse.urlencode({"chat_id":chat,"text":message}).encode()
    request=urllib.request.Request(
        "https://api.telegram.org/bot"+token+"/sendMessage",
        data=payload,method="POST")
    with urllib.request.urlopen(request,timeout=25) as response:
        result=json.load(response)
    if result.get("ok") is not True:
        raise RuntimeError("Telegram response not confirmed")


def scan(repo,chain):
    gate()
    sha,remote=fetch(repo,chain)
    scanned=scan_with_snapshot(chain,remote)
    return publish(repo,chain,sha,scanned)


def claim_and_send(repo,chain,run_id):
    gate()
    sha,remote=fetch(repo,chain)
    claimed,ids=claim(remote,chain,run_id,os.environ.get("GITHUB_RUN_ID",run_id))
    committed=publish(repo,chain,sha,claimed)
    verified,latest=fetch(repo,chain)
    if committed!=verified:
        raise RuntimeError("claim commit not verified; no send")
    if not ids:
        return unresolved(latest,chain)
    # Only newly claimed IDs held by this process are eligible.
    outcome=record_attempts(latest,chain,ids,run_id,telegram)
    publish(repo,chain,committed,outcome)
    return unresolved(outcome,chain)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--chain",choices=("cu","emart24"),required=True)
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--phase",choices=("scan","dispatch"),required=True)
    p.add_argument("--run-id",required=True)
    a=p.parse_args()
    if a.phase=="scan":
        scan(a.repo,a.chain)
    else:
        issues=claim_and_send(a.repo,a.chain,a.run_id)
        print("CLAIM_AUDIT_UNRESOLVED_COUNT",len(issues))
        if issues:
            raise RuntimeError("operator reconciliation required: "+str(len(issues)))


if __name__=="__main__":
    main()
