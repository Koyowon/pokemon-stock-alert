# CU/emart24 final cutover implementation — operator handoff

**Status: integrated candidate tests PASS; live cutover NOT AUTHORIZED, NOT DEPLOYED.**

## Implemented in isolated branch
- `cu_emart24_state_store.py`: production path allowlist, dedicated proposed state branch `stock-state-cu-emart24`, remote SHA compare-and-swap, atomic emart24 state+cache commit, immutable checksum manifest, claim/outcome/audit.
- `cu_emart24_scan_adapter.py`: real CU and emart24 scanner entrypoints read authoritative injected snapshot, Telegram blocked during scanning, preserve existing pending/claimed events.
- `cu_emart24_cutover_coordinator.py`: scan then CAS publish; claim then CAS publish + verify before dispatch; send only own newly claimed event IDs; record outcomes; no automatic reclaims.
- `tests/test_cutover_wiring.py`, `tests/test_production_state_candidate.py`, `tests/test_final_readiness.py`: fake CU=3/emart24=4, no-send on claim CAS rejection, claimed audit and backup digest. Actions run 38826652303 passed. Earlier synthetic Git E2E run 38825665264 passed.

## Remaining release blockers (do not pretend production-ready)
1. Existing `.github/workflows/cu-stock-monitor.yml` and `.github/workflows/stock-monitor.yml` still run old schedules and main state publisher; these **must not** be changed until explicitly approved. Real replacement workflows have not been activated or exercised end-to-end.
2. The proposed state branch `stock-state-cu-emart24` has **not** been created or populated. Actual source state schema and immutable backup/rollback must be verified at cutover; current backup test is synthetic and read-only.
3. The Telegram callback and operator audit escalation are intentionally not wired to real secrets. A failed post-send outcome commit is ambiguous and requires manual reconciliation; never claim exactly-once delivery.
4. Current candidate coordinator expects a dedicated Git checkout, exclusive workflow concurrency, and approved write permissions. No production migration/rollback has been executed.
5. A verified repository owner must approve branch protections and permissions. Do not grant contents:write to scan jobs.

## Exact proposed production workflow changes (not applied)
- `.github/workflows/cu-stock-monitor.yml`: replace scan/publish pipeline with dedicated-state snapshot fetch -> CU scan adapter -> CAS state publish -> CAS claim -> Telegram dispatcher -> outcome commit -> audit. Remove Telegram secrets from scan job, disallow main state push, enforce exclusive concurrency group across both chains, preserve existing CU region settings.
- `.github/workflows/stock-monitor.yml`: same for emart24, committing `state.json` and `stores.json` together, preserving store coverage and unknown inventory behavior.
- Use only the newly created `cu_emart24_state_store.py`, `cu_emart24_scan_adapter.py`, `cu_emart24_cutover_coordinator.py` for these two chains. Leave `state_push_publisher.py`, GS25, and other workflows unchanged.

## Operator rollback protocol
1. Before any production writes: stop only CU/emart24 schedules, drain in-flight jobs, export current `cu_stock_state.json`, `state.json`, `stores.json` and their SHA256, record `main` baseline commit, dedicated state branch SHA, old workflow YAMLs and pending/claimed events.
2. Verify migration copy and checksums on dedicated branch; preserve all alert flags, sequence IDs, and cache. Reject any missing state, unknown schema, or mismatch. No force push.
3. During first pilot, reconcile `claimed` missing outcome and `send_unknown` manually. Never auto-replay.
4. Rollback: disable new CU/emart24 jobs, drain, take fresh immutable snapshot, compare with original, manually reconcile claimed/unknown; restore previous CU/emart24 workflows only with separate owner authorization. Never rewind the state branch over newer claims. Keep GS25 running.

## Change boundaries
No modification of main, PR #1, Draft PR #2, GS25, real state files, inventory APIs or Telegram. No production branch migration, merge, deployment, or activation.
