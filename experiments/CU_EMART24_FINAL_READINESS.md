# CU / emart24 minimal pre-cutover gate — 2026-10-16

## Status
**Offline acceptance: PASS (3/3). Production cutover: NO-GO.**

Evidence: GitHub Actions run 38825039093; `tests/test_final_readiness.py`. Fake inventory: CU 3, emart24 4. Repeated scans preserve pending; ambiguous sends are recorded without automatic replay. Read-only snapshot and stale-publish rejection verified. These tests do NOT establish live inventory accuracy, real Telegram delivery, or executable production rollback.

## Exact planned production changes (NOT APPLIED)

1. `cu_stock_monitor.py` and `monitor.py`: load authoritative CU and emart24 state (plus emart24 `stores.json`) from dedicated state branch; run scan without Telegram secrets; preserve pending/claimed and event sequence; stage atomic state/outbox artifact with baseline SHA.
2. `state_push_publisher.py`: create a CU/emart24-only publisher targeting a separately approved state branch, not `main`. Explicit chain/path allowlist, validated artifact origin, optimistic concurrency on branch SHA, no force push; do not modify GS25 handling.
3. `.github/workflows/cu-stock-monitor.yml` and the actual emart24 workflow (verify exact path before editing): scanner `contents:read`, no Telegram secrets; separate publisher `contents:write` with state-branch restriction and run/manifest validation. Disable existing send-first/old publish jobs only in an approved maintenance window.
4. New reviewed CU/emart24 dispatch/audit modules and narrowly scoped workflow: claim only pending events with timestamp/run ID, commit+verify on remote before attempting Telegram; only send events from its own claim commit; record outcome; never auto-replay `send_unknown`. Keep GS25 separate.
5. Dedicated state branch and migration manifest (creation/population requires separate approval): backed-up `cu_stock_state.json`, `state.json`, `stores.json`, immutable SHA/checksum, versioned schema, preserved alert flags. No production files touched during this audit.

## Blocking acceptance gates

- A working integrated publisher + dispatch workflow with real file paths (not only `experiments/stage12_candidate.py` or `stage13_state_publisher.py` synthetic JSON) must be reviewed and pass an offline end-to-end dry run.
- GitHub permissions/rules for protected main and state branch must be confirmed by repo owner; branch-protection detail not accessible to assistant.
- Immutable backup and an actual isolated rollback procedure must be demonstrated. Previous rollback test was read-only comparison, not restoration.
- Failure between Telegram send and outcome commit remains ambiguous. Operator runbook and monitoring must handle `claimed` without outcome and `send_unknown`; no exactly-once delivery guarantee.
- After all blockers cleared, obtain separate explicit user approval before any main merge, production state migration, workflow activation, real API or Telegram.

## Non-actions

No changes to `main`, PR #1, Draft PR #2, GS25, production state, actual inventory API, or Telegram.
