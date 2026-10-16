# CU / emart24 — FINAL READ-ONLY PREDEPLOY AUDIT (2026-10-16)

## Decision: **NO-GO for live deployment**
Offline test success is not authorization to change operating workflows, send Telegram or call stock APIs. Final offline Actions run: 38828667785 (PASS, 22 tests).

## Read-only GitHub observations at audit time
- main SHA: `08849cf0214ae7264f25aed5f3c17885e64a9ecd`; main branch API reports `protected=true`, but protection enforcement/rules details and effective Actions token permissions were **not fully verifiable** through available read-only endpoints. Do not infer write authorization from repo owner/admin access.
- Dedicated target branch `stock-state-cu-emart24`: **does not exist** (GitHub 404). Migration not performed.
- `cu_stock_state.json`: blob SHA `2dbb1c0abd9adcbf613d05711c0b066a79dcdd20`; 164 store entries; no `pending_alerts` or `alert_sequence`.
- `state.json`: blob SHA `53941d3e6dcfbc83270a715652e6bae5a6af0dc0`; flat stock keys; no `pending_alerts` or `alert_sequence`.
- `stores.json`: blob SHA `8e3940981f394cc0d0dc3213840116514fe997e7`; `last_refresh` and 114 cached stores.
- Existing CU workflow `.github/workflows/cu-stock-monitor.yml`: cron every 5 minutes at 2,7,...; one monitor job has Telegram secrets; directly invokes `cu_stock_monitor.py`; commits state to main using git pull --rebase and git push. Workflow blob SHA `9fcc1c923ad335bde791cbc512242e1b2f303708`.
- Existing emart24 workflow `.github/workflows/stock-monitor.yml`: cron every 5 minutes; one monitor job has Telegram secrets; directly invokes `monitor.py`; commits state/cache to main. Workflow blob SHA `05ecbbc78bb03311a69895bca775f5651422569d`.
- Actual main scanners still send Telegram directly (`cu_stock_monitor.py` uses `telegram(body)`, `monitor.py` uses `notify(message)`). This differs from the isolated outbox-based scanner candidate.
- Draft PR #2 remained draft at SHA `84a4adcdb14a205e1ac0d1244ac363bf76dcd93e`.

## Offline fixes on validation branch only
- `cu_emart24_executable_workflow.py`: removed dangerous literal live approval `'1'`; requires separately configured `vars.CU_EMART24_LIVE_APPROVED`. Both proposed jobs still `if: false` and no schedule. They are **not** deployed or verified in live environment.
- `cu_emart24_release_preflight.py`: fail-closed preflight checklist and read-only legacy state audit, explicitly flags absence of outbox.
- `tests/test_release_preflight.py`: tests legacy migration shape, no-go checklist, missing file fail-closed and explicit approval variable. Final offline gate passes all 22 tests.

## Required production change files — only AFTER separate authorization
1. `.github/workflows/cu-stock-monitor.yml`: replace old direct-send/main-push schedule with approved scan/CAS-claim/dispatch/audit workflow. Preserve schedule only after migration and operator go-ahead.
2. `.github/workflows/stock-monitor.yml`: same, emart24 state/cache atomic publish.
3. `cu_stock_monitor.py`, `monitor.py`: replace main direct-send behavior with reviewed outbox code and authoritative state hydration; preserve all region and product settings.
4. New `cu_emart24_state_store.py`, `cu_emart24_scan_adapter.py`, `cu_emart24_live_entrypoint.py`, `cu_emart24_release_preflight.py`, `cu_emart24_migration_plan.py` and reviewed tests.
5. Create dedicated branch `stock-state-cu-emart24` only after immutable backup of three operating state files. No changes to GS25, PR #1, Draft PR #2 or unrelated workflows.

## Operator-controlled sequence / rollback
1. Obtain explicit approval for production writes and live pilot; verify repository Actions write token, branch protection/rules and required secrets.
2. Stop only CU/emart24 schedules, drain in-flight jobs; snapshot and export immutable bytes of three state files and old workflow definitions, record main commit and Git blob SHA + SHA256, audit outstanding alerts.
3. Migrate exact verified snapshot to dedicated state branch; add outbox metadata in a controlled migration. **Legacy direct-send history cannot be reconstructed from empty outbox**, so reconcile old alerted flags and inventory transitions before enabling dispatch. Reject missing or mismatched source baseline.
4. Verify migrated files and branch SHA; dry-run fake sends against dedicated state with read-only checks; owner reviews exact workflow diff. Only then enable real provider scans and dispatch with separately approved pilot.
5. Rollback: disable new CU/emart24 jobs first, drain, snapshot latest claims/outcomes; manually reconcile `claimed` / `send_unknown` alerts; restore previous workflows only with owner authorization. Never force push, replay claimed events or reset state branch over newer outcomes.

## Hard boundaries maintained
This audit did **not** modify main, GS25, PR #1, Draft PR #2, operating state files or operating workflows; did not call real inventory APIs or Telegram; did not create a production state branch, merge, deploy or activate alerts.
