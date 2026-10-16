"""Fail-closed workflow replacement proposal, not an enabled deployment."""
def render(chain):
    if chain not in ("cu","emart24"): raise ValueError("invalid chain")
    label="CU" if chain=="cu" else "Emart24"
    return ("name: "+label+" Proposed Cutover (DISABLED)\n"
        "on:\n  workflow_dispatch:\n"
        "permissions:\n  contents: read\n"
        "concurrency:\n  group: cu-emart24-dedicated-state\n  cancel-in-progress: false\n"
        "jobs:\n  scan:\n    if: false # requires final deployment approval\n"
        "    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n"
        "    steps:\n      - uses: actions/checkout@v4\n"
        "        with:\n          persist-credentials: false\n"
        "      - name: State branch migration required\n"
        "        run: exit 1\n"
        "  dispatch:\n    if: false # requires final deployment approval\n"
        "    runs-on: ubuntu-latest\n    needs: scan\n"
        "    permissions:\n      contents: read\n"
        "    steps:\n      - name: No real Telegram until separately approved\n"
        "        run: exit 1\n")

def targets():
    return {".github/workflows/cu-stock-monitor.yml":render("cu"),
            ".github/workflows/stock-monitor.yml":render("emart24")}
