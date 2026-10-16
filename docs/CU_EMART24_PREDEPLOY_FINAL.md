# CU/emart24 predeployment handoff — offline final gate

**Result:** offline acceptance PASS, Actions 38827038277. **Live deployment NOT approved and NOT ready to activate without the gates below.**

## Implemented only on this validation branch
- `cu_emart24_state_store.py`: chain allowlist, remote SHA CAS, clean-checkout precondition, owned claims, outcomes.
- `cu_emart24_scan_adapter.py` and `cu_emart24_cutover_coordinator.py`: actual scanner entrypoints against injected snapshots, no Telegram in scan stage, CAS before send.
- `cu_emart24_migration_plan.py`: immutable logical JSON SHA256 manifests, no-write staging, tamper detection and non-destructive rollback instruction generator.
- `cu_emart24_workflow_proposal.py`: exact two workflow replacement **placeholders**, disabled and manual-only; **not functioning live workflows**. They are deliberately fail-closed and must not be copied into main as-is.
- Tests: `test_predeploy_acceptance.py`, `test_cutover_wiring.py`, `test_production_state_candidate.py`, `test_final_readiness.py`. No real inventory or Telegram.

## Remaining critical gates for a real deployment
1. Write owner-reviewed *executable* CU/emart24 replacement workflow YAMLs. Current placeholders do not run scan/publish/dispatch; cannot call them complete. Split scan (no secrets) and dispatch (secrets only) with verified commit ownership and exclusive concurrency.
2. Create a separately approved production state branch `stock-state-cu-emart24` and migrate backed-up real three state files. No state migration has been done. Confirm schema, alert sequence, old notified flags and unknown stock handling.
3. Operator verifies branch permissions/protection and state backup source SHA and checksums. Exercise rollback in a **disposable clone**, not by modifying operating files or branch.
4. Explicitly authorize live API and Telegram pilot after a dry-run; alert reconciliation required for `claimed` without outcome and `send_unknown`.
5. Resolve operational monitoring and manual escalation; exactly-once Telegram delivery cannot be guaranteed after a timeout.

## Release order — all gated by separate approval
Freeze only CU/emart24 jobs -> drain -> immutable backup + manifests -> create dedicated production state branch -> migrate and verify -> owner-approved workflow merge -> controlled pilot -> audit. If rollback: disable new jobs -> drain -> audit claims -> restore old workflows only with explicit approval, no force-push and no automatic resend.

## Boundaries
No main, PR #1, Draft PR #2, GS25, real state file, real inventory API or Telegram changes. No merge/deployment/activation.
