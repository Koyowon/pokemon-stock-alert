# CU / emart24 final operator approval conditions — 2026-10-16

## Decision: NO-GO for production cutover

Offline GitHub Actions run 38829550259 passed all 29 tests. This is an offline candidate result only. No approval was granted for production state writes, workflow changes, live inventory APIs, Telegram or branch migration.

### Current read-only Git baseline
- main commit `08849cf0214ae7264f25aed5f3c17885e64a9ecd`, protected=true.
- `cu_stock_state.json` blob `2dbb1c0abd9adcbf613d05711c0b066a79dcdd20`: 164 stores; 0 records with `alerted=true` at inspection time; no pending outbox.
- `state.json` blob `53941d3e6dcfbc83270a715652e6bae5a6af0dc0`: 103 flat product/store stock entries, no pending outbox.
- `stores.json` blob `8e3940981f394cc0d0dc3213840116514fe997e7`: 114 cached stores.
- Workflow blobs: `cu-stock-monitor.yml` `9fcc1c923ad335bde791cbc512242e1b2f303708`, `stock-monitor.yml` `05ecbbc78bb03311a69895bca775f5651422569d`; existing schedules and direct-send pipelines still active.
- Target `stock-state-cu-emart24` absent (404). Detailed branch rules/protection endpoint 403, Actions permission endpoints not accessible by this integration; cannot assert sufficient write privileges or rules.
- GS25, main, PR #1, Draft PR #2 not modified by this work.

### Implemented isolated improvements
- `cu_emart24_approval_policy.py`: 16 independent operator prerequisites, fail-closed GO gate and read-only snapshot migration validation. Default decision is NO-GO.
- `cu_emart24_live_entrypoint.py`: fixed persisted `claimed_at` to actual timezone-aware UTC ISO timestamp, rather than GitHub run ID.
- `tests/test_approval_policy.py`: explicit approval rejection, read-only migration scope and UTC claim timestamp checks.
- Existing `cu_emart24_legacy_migration.py` preserves every CU `alerted` flag and stock, all emart24 stock keys/values and store cache, initializes empty outboxes without generating historical alerts; validates canonical SHA256 and rejects repeat migration.
- 29 offline tests passed; **no actual production backup/export or rollback performed**.

### Mandatory owner approvals before GO
1. Authorize *separately* the maintenance window, stopping CU/emart24 schedules, draining jobs and reading/exporting immutable real state/workflow backups. GS25 continues unchanged.
2. Verify current source main commit and five blob SHAs immediately before freeze, and validate raw-byte backup plus SHA256, restoring it in a disposable worktree. If any drift, stop and recapture.
3. Reconcile legacy notification semantics: CU has 0 `alerted=true` at baseline, so preserve flags but **do not infer absence of already-sent Telegram messages**; emart24's 103 stock entries are not delivery receipts. Approve first-scan suppression/baseline behavior and manual handling of `claimed` and `send_unknown` outcomes.
4. Verify actual Actions write token access to the dedicated state branch, branch protection/rules, secrets only in dispatch, and exclusive concurrency; permission endpoints are unavailable in this read-only session.
5. Authorize creation and population of `stock-state-cu-emart24`, verifying all three migrated files and source SHA; no forced pushes.
6. Review and approve executable *real* workflow replacement diff for only `.github/workflows/cu-stock-monitor.yml` and `.github/workflows/stock-monitor.yml`, and associated CU/emart24 scanner/state modules. Current proposed workflows still contain `if: false` and no schedule; they cannot be treated as live-ready.
7. Approve live inventory API and Telegram pilot separately after migration, with audit, rollback, and explicit decision on first alerts. If outcome push fails after Telegram delivery, do not auto-replay.

### Cutover / rollback boundaries
After all approvals: freeze CU/emart24 only -> drain -> immutable backups -> migrate dedicated state branch -> validate SHA/checksums and old flags -> review final workflow diff -> separately approved live pilot -> audit. On failure, stop only new CU/emart24 jobs, snapshot current claims, reconcile manually and restore workflows only with owner approval. Never reset the branch over newer claims or replay claimed alerts.

**Conclusion:** Approval requirements are fully enumerated, not satisfied. The operator must explicitly authorize production operations in a future turn. Do not deploy or merge on the basis of offline test success.
