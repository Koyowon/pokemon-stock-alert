"""Validate GitHub-hosted artifact metadata independently of downloaded manifest.

The GitHub REST API is used only by the approved production publisher job.
Offline tests mock the HTTP request; no API is called in test runs.
"""
import json
import re
import urllib.request


def validate_platform_artifact(artifact_id, digest, run_id, expected_name, token,
                               repository="Koyowon/pokemon-stock-alert", opener=None):
    if not str(artifact_id).isdigit() or int(artifact_id) <= 0:
        raise ValueError("invalid trusted artifact ID")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest or ""):
        raise ValueError("invalid trusted archive digest")
    if not str(run_id).isdigit() or not token:
        raise ValueError("missing trusted run context")
    if repository != "Koyowon/pokemon-stock-alert":
        raise ValueError("untrusted repository")
    url = "https://api.github.com/repos/" + repository + "/actions/artifacts/" + str(artifact_id)
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
    })
    fetch = opener or urllib.request.urlopen
    with fetch(request, timeout=15) as response:
        info = json.load(response)
    if (str(info.get("id")) != str(artifact_id) or
        info.get("name") != expected_name or
        info.get("expired") is not False or
        info.get("digest") != digest or
        str((info.get("workflow_run") or {}).get("id")) != str(run_id)):
        raise ValueError("GitHub artifact provenance/digest mismatch")
    return True
