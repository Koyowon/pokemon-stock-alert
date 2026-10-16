# CU/emart24 read-only cutover preparation — FINAL

## Decision: NO-GO (production not authorized)
Offline Actions run 38830038233 passed 32 tests. The cutover is **not** deployed, and live workflows, inventory API and Telegram are unchanged.

## Read-only baseline, 2026-10-16
- main SHA: `08849cf0214ae7264f25aed5f3c17885e64a9ecd`; branch protected=true. Before any cutover, recapture SHA and compare; if drift, stop and restart the backup window.
- State Git blobs: `cu_stock_state.json` = `2dbb1c0abd9adcbf613d05711c0b066a79dcdd20`; `state.json` = `53941d3e6dcfbc83270a715652e6bae5a6af0dc0`; `stores.json` = `8e3940981f394cc0d0dc3213840116514fe997e7`.
- Workflow Git blobs: `.github/workflows/cu-stock-monitor.yml` = `9fcc1c923ad335bde791cbc512242e1b2f303708`; `.github/workflows/stock-monitor.yml` = `05ecbbc78bb03311a69895bca775f5651422569d`.
- CU state 164 stores, 0 `alerted=true` at snapshot, no outbox. emart24 flat stock state 103 keys, cache 114 stores, no outbox. **Never infer historical Telegram deliveries from this data**.
- Existing workflows schedule CU at minutes 2,7,... and emart24 at */5; each has Telegram secrets and direct sends, then pushes state to main. They must be drained and frozen before migrating.
- `stock-state-cu-emart24` absent (404). Main branch protection reports enabled; detailed rules API 403 and Actions permission endpoint inaccessible. Effective state branch write permission and protections **not verified**.

## Backup manifest contract
Before any separately authorized migration, capture raw bytes (not only canonicalized JSON) of the five files above at one pinned commit, record source commit, each Git blob SHA and raw SHA256; save copies outside the repository with restricted access. Export is not performed in this read-only phase; Git blob SHA is **not** a raw SHA256 checksum. Restore in a disposable clone and compare byte-for-byte. No force push. If any file SHA changes before freeze, rebaseline.

## First-alert suppression rule
Preserve CU `alerted` flags and every emart24 stock baseline exactly. Add empty outboxes only, without generating alerts from existing positive stock. At the first post-cutover scan, do not dispatch unless an owner-reviewed dry-run proves that baseline positive stock is not replayed as a new transition. Reconcile legacy direct-send history manually; unknown `claimed` or `send_unknown` events are never automatically resent. Telegram cannot guarantee exactly-once delivery after ambiguous timeouts.

## Cutover order (NOT executed)
1. Owner explicitly approves maintenance window and stopping CU/emart24 only.
2. Freeze schedules and drain running jobs; pin main commit and five Git blobs.
3. Export raw backups + SHA256, verify restore in disposable clone.
4. Owner verifies effective Actions token write rights, state branch rules and secret scope via repository settings; verify concurrency serializes both chains.
5. Owner separately approves creating `stock-state-cu-emart24`, migrate exact three state files, verify SHA and preservation.
6. Review exact workflow replacement diff, explicitly approve live API/Telegram pilot; enable only after first-scan suppression check.
7. Monitor claims and reconcile uncertain outcomes; rollback by stopping new jobs, draining, preserving latest state, reconciling claims and restoring old workflows with separate approval.

## Added in this isolated branch
- `cu_emart24_cutover_readonly_plan.py`: fail-closed freeze/backup/permissions/alert/approval prerequisites and in-memory migration/rollback plan.
- `tests/test_cutover_readonly_plan.py`: safety and baseline tests.
- `.github/workflows/cu-emart24-cutover-preparation-offline.yml`: 32 passing tests, read-only and no secrets.

**No modifications** to main, GS25, PR #1, Draft PR #2, live state files, live workflows; no live API or Telegram use.
