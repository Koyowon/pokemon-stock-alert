"""Offline raw-byte backup verification for a pinned Git commit.

Read-only: git show only. Writes local backup directory only, never git push.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PATHS=("cu_stock_state.json","state.json","stores.json",
       ".github/workflows/cu-stock-monitor.yml",
       ".github/workflows/stock-monitor.yml")

def git(repo,*args):
    return subprocess.run(["git","-C",str(repo),*args],check=True,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout

def backup(repo,commit,out):
    if len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit.lower()):
        raise ValueError("full immutable commit SHA required")
    if out.exists():
        raise ValueError("backup destination must not already exist")
    out.mkdir(parents=True)
    manifest={"commit":commit,"files":{}}
    for name in PATHS:
        raw=git(repo,"show",commit+":"+name)
        target=out/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(raw)
        blob=git(repo,"rev-parse",commit+":"+name).decode().strip()
        manifest["files"][name]={"git_blob_sha":blob,
            "raw_sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)}
    (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    verify(repo,out)
    return manifest

def verify(repo,out):
    manifest=json.loads((out/"manifest.json").read_text())
    if set(manifest["files"])!=set(PATHS):
        raise ValueError("missing/extra backup files")
    for name,meta in manifest["files"].items():
        raw=(out/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=meta["raw_sha256"] or len(raw)!=meta["bytes"]:
            raise ValueError("backup byte checksum mismatch: "+name)
        if raw!=git(repo,"show",manifest["commit"]+":"+name):
            raise ValueError("backup differs from pinned source: "+name)
        if git(repo,"rev-parse",manifest["commit"]+":"+name).decode().strip()!=meta["git_blob_sha"]:
            raise ValueError("Git blob mismatch: "+name)
    return True

def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("backup","verify"))
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--commit",default="")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.mode=="backup": backup(args.repo,args.commit,args.out)
    else:verify(args.repo,args.out)
if __name__=="__main__":main()
