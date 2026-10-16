# CU/emart24 legacy-state migration — isolated acceptance

**Result:** offline migration compatibility PASS; live deployment remains **NO-GO** until the listed prerequisites are met. GitHub Actions run 38829112712 passed 26 tests.

## Read-only production schema baseline (observed at audit)
- main commit: `08849cf0214ae7264f25aed5f3c17885e64a9ecd`.
- CU `cu_stock_state.json` Git blob `2dbb1c0abd9adcbf613d05711c0b066a79dcdd20`: 164 stores, per-store `stock`, `alerted`, `name`, `address`, `city`; no outbox.
- emart24 `state.json` Git blob `53941d3e6dcfbc83270a715652e6bae5a6af0dc0`: flat product/store stock keys; no outbox.
- emart24 `stores.json` Git blob `8e3940981f394cc0d0dc3213840116514fe997e7`: `last_refresh` and 114 cached stores.

## New implementation
- `cu_emart24_legacy_migration.py`: pure in-memory migration; preserves every legacy field and CU `alerted` boolean, every emart24 quantity/key and the exact store cache; adds only empty `pending_alerts` and `alert_sequence=0` to CU and emart24 state. Rejects already-migrated states to avoid clearing an existing outbox. Records source commit, Git blob IDs, canonical SHA256 of source and migrated documents, and explicit requirement for manual historical alert reconciliation. Verifies every field and detects tampering; `rollback_snapshot` validates backup and returns a copy, never pushes to Git.
- `tests/test_legacy_migration.py`: verifies flagged CU positive stock, zero stock, unknown stock, emart24 mixed key prefixes and numeric stock, checksum corruption, missing file, existing outbox refusal, no new pending alerts and backup restoration.
- Offline workflow `.github/workflows/cu-emart24-legacy-migration-offline.yml`: 26 passing tests, no secrets, no production state writes.

## Important remaining risk
- Legacy CU `alerted` flag and emart24 quantity baselines are preserved, but historical Telegram delivery status cannot be reconstructed from them. The migration creates **zero** new alerts; no immediate replay. A future real scan may queue new alerts if its logic treats an existing positive quantity as a transition or an unalerted baseline. Operator must compare and approve behavior before live pilot.
- No production snapshot was copied to the new branch. The state branch `stock-state-cu-emart24` did not exist at last check. GitHub branch rules and Actions write token access were not fully verifiable via read-only endpoints.
- Workflow candidates are disabled, with no live API or Telegram pilot. A separate approval is required for freeze, backup, migration, production workflow replacement and live activation.

## Required next authorization
Authorize a narrowly scoped production cutover only after the owner confirms GitHub branch protections, write token and secrets; the approval must explicitly allow stopping CU/emart24 schedules, immutable backup of current files, creation/migration of dedicated state branch, and separate real API/Telegram pilot. Never touch GS25, PR #1, Draft PR #2 or unrelated workflows. Do not activate without an operator-verified rollback and alert reconciliation plan.
