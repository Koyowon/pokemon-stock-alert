"""Generate executable but DISABLED proposed CU/emart24 workflow YAMLs.

These are proposals, not replacements of the operating workflow files.
"""
def render(chain):
    if chain not in ("cu","emart24"): raise ValueError("unsupported chain")
    label="CU" if chain=="cu" else "Emart24"
    lines=[
        "name: "+label+" Dedicated State Cutover (PROPOSED)",
        "on:",
        "  workflow_dispatch:",
        "permissions:",
        "  contents: read",
        "concurrency:",
        "  group: cu-emart24-dedicated-state",
        "  cancel-in-progress: false",
        "jobs:",
        "  scan:",
        "    if: false # requires separate owner deployment approval",
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 12",
        "    permissions:",
        "      contents: write",
        "    steps:",
        "      - uses: actions/checkout@v4",
        "        with:",
        "          fetch-depth: 0",
        "          persist-credentials: true",
        "      - name: Checkout disposable state worktree",
        "        run: |",
        "          git fetch origin stock-state-cu-emart24",
        "          git worktree add --detach \"$RUNNER_TEMP/chain-state\" FETCH_HEAD",
        "      - name: Scan and commit authoritative state",
        "        env:",
        "          CU_EMART24_LIVE_APPROVED: ${{ vars.CU_EMART24_LIVE_APPROVED }}",
        "        run: python cu_emart24_live_entrypoint.py --chain "+chain+" --repo \"$RUNNER_TEMP/chain-state\" --phase scan --run-id \"$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT\"",
        "  dispatch:",
        "    if: false # requires separate owner deployment approval",
        "    needs: scan",
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 8",
        "    permissions:",
        "      contents: write",
        "    steps:",
        "      - uses: actions/checkout@v4",
        "        with:",
        "          fetch-depth: 0",
        "          persist-credentials: true",
        "      - name: Checkout disposable state worktree",
        "        run: |",
        "          git fetch origin stock-state-cu-emart24",
        "          git worktree add --detach \"$RUNNER_TEMP/chain-state\" FETCH_HEAD",
        "      - name: Commit claim, dispatch, and audit",
        "        env:",
        "          CU_EMART24_LIVE_APPROVED: ${{ vars.CU_EMART24_LIVE_APPROVED }}",
        "          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}",
        "          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}",
        "        run: python cu_emart24_live_entrypoint.py --chain "+chain+" --repo \"$RUNNER_TEMP/chain-state\" --phase dispatch --run-id \"$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT\"",
    ]
    return "\n".join(lines)+"\n"

def proposed():
    return {"cu":render("cu"),"emart24":render("emart24")}
