# CU/emart24 executable workflow candidate — final isolated report

## Verified
- GitHub Actions run 38827602278 PASS: proposed executable scan/dispatch job structures, disabled deployment gates, blocked unauthorized entrypoint, no send on CAS failure, immutable migration checksum and rollback plan, previous scanner/offline acceptance tests.
- New files: `cu_emart24_live_entrypoint.py`, `cu_emart24_executable_workflow.py`, `tests/test_executable_workflow.py`, `.github/workflows/cu-emart24-executable-offline.yml`.
- Prior files: `cu_emart24_state_store.py`, `cu_emart24_scan_adapter.py`, `cu_emart24_cutover_coordinator.py`, `cu_emart24_migration_plan.py`.
- Operating `.github/workflows/cu-stock-monitor.yml` and `.github/workflows/stock-monitor.yml` remain unchanged. Proposed replacement workflow is generated as text, with `if: false` for both jobs and no schedule; not deployed.

## Deployment blockers requiring owner approval and work
1. The generated workflow proposal is executable *in structure* but not activated, and its scan/dispatch jobs have not been tested with real GitHub state branch credentials or Telegram.
2. A dedicated production branch `stock-state-cu-emart24` has not been created or populated. Real source files must be backed up, migrated, verified and branch permissions reviewed separately.
3. GitHub Actions job token permissions, branch rules and state-branch write access must be reviewed; `main` and Draft PR #2 untouched.
4. **Concurrency flaw to fix before live cutover**: workflow-level concurrency group only serializes workflow runs; scan and dispatch jobs inside one run can use separate checkouts but CAS handles concurrent state writes. Ensure the state branch policy permits the required CAS pushes and audit failures are surfaced.
5. **Safety trade-off**: if Telegram send succeeds but the outcome push fails, claimed alert remains ambiguous; never auto-retry. Manual reconciliation and audit is mandatory.
6. Scanner may run with existing code's provider APIs only after explicit real-API approval. A real scan must not be triggered from validation branch.

## Required cutover sequence
Pause only CU/emart24 schedules -> drain in-flight jobs -> immutable backup and checksum of 3 files -> create and populate owner-approved dedicated branch -> verify schema and checksums -> review real workflow diff and branch protections -> separate approval for main merge and live API/Telegram pilot -> monitor claims and uncertain outcomes. Rollback disables new jobs, drains, snapshots latest claims, reconciles manually, and restores old workflows only with separate approval; never force-push or automatically resend claimed alerts.

## Strict boundaries
No change to main, PR #1, Draft PR #2, GS25, operational state, actual inventory API, Telegram. No merge/deployment/activation.
