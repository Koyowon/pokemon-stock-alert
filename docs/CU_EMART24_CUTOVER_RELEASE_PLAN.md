# CU + emart24 cutover: exact release change proposal (NOT DEPLOYED)

Date: 2026-10-16. Owner approval required before any production write, API request, Telegram send, merge, or workflow activation.

## Baseline and verified scope

- Existing CU schedule: `.github/workflows/cu-stock-monitor.yml`, 12 executions/hour, scanner receives Telegram secrets, publish job checks out main and invokes `state_push_publisher.py`.
- Existing emart24 schedule: `.github/workflows/stock-monitor.yml`, 12 executions/hour, scanner receives Telegram secrets, publish job checks out main and invokes `state_push_publisher.py`.
- `state_push_publisher.py` is hard-coded to main and includes GS25 code; do **not** repurpose it or change GS25 behavior in place.
- Isolated proof: Actions run 38825665264, synthetic stock 3 (CU) / 4 (emart24), state CAS, claim, mock delivery, repeat-run duplicate check, synthetic backup.
- Candidate `cutover_candidate.py` hardcodes a **validation** state branch and synthetic file paths. `cutover_candidate_runner.py` enforces `mock_only=True` and patches live network/sender. These are **not** directly deployable.
- Draft PR #2 is separate, not merged. Production state in main is not a verified, safely migratable snapshot until operator backup is completed.

## Exact proposed production diff (not yet made)

1. **New** `cu_emart24_state_store.py`: production-only allowlist for CU `cu_stock_state.json`, emart24 `state.json` and `stores.json`; a dedicated owner-approved state branch distinct from main and all validation branches; fetch remote authoritative snapshot + SHA; JSON/schema validation; fail closed if missing or corrupt; chain-local optimistic CAS push; no force push; emart24 state/cache bundled atomically. Reject any path outside these three.
2. **New** `cu_emart24_dispatch.py`: process only pending event IDs claimed in the caller's own remotely verified claim commit. Persist `claim_run`, `claimed_at`, and audit outcome. Never auto-retry `claimed` / `send_unknown`; raise an operator alert for ambiguous or missing outcomes. Sender secrets available only in the dispatcher job. A timeout can mean Telegram delivered even if the outcome commit fails: no exactly-once guarantee.
3. **Update** `cu_stock_monitor.py`: support injected state path/snapshot, no direct Telegram; preserve outbox and sequence; report store-by-store numeric stock without inventing stock on failed/unknown queries. No change to CU store-selection scope.
4. **Update** `monitor.py`: support injected emart24 state and stores cache, no direct Telegram; preserve outbox and sequence; unknown stock must not become zero; state/cache committed as one bundle. No change to approved regions/products.
5. **Update** `.github/workflows/cu-stock-monitor.yml` and `.github/workflows/stock-monitor.yml`: scan jobs have read-only permissions and no Telegram secrets; publisher/claim jobs get only necessary write permission and restrict target to the dedicated state branch; dispatcher alone gets Telegram secrets. Replace existing main publisher path only during approved cutover; ensure old and new schedules cannot run concurrently.
6. **New** `tests/test_cu_emart24_cutover.py` and one offline dry-run workflow: verify actual planned workflow/config wiring, state migration checksums, real scanner entrypoints with mocked APIs, duplicate/unknown alert behavior, failed CAS => no send, no secret leakage, and read-only rollback snapshot.
7. **New** `docs/CU_EMART24_ROLLBACK.md`: immutable backup manifest (three state files, commit SHA, SHA256, timestamp, run IDs), old/new workflow inventory, no-force rollback instructions, operator reconciliation for all claimed/send_unknown alerts.

## Required cutover sequence, separately authorized

A. **Preflight read-only**: owner confirms exact state branch name, repository branch protections, Actions permissions and dispatch secrets; inspect in-flight CU/emart24 jobs and current state schemas.
B. **Backup before writing**: freeze CU/emart24 schedules (leave GS25 running), drain in-flight jobs; save immutable copies of all three state files, baseline SHA and checksums, record old workflow refs and pending/claimed alerts.
C. **Migration**: create owner-approved dedicated production state branch; migrate the validated snapshot without changing main, preserving event IDs, sequence, flags and store cache; verify digests.
D. **Shadow**: run scanners with fake Telegram only against migrated state and compare store counts; no production alert sent.
E. **Explicit deployment approval**: update only the listed CU/emart24 files/workflows and activate one controlled pilot. Real API/Telegram usage requires explicit user approval; monitor first pilot and reconcile audit.
F. **Rollback**: disable new jobs first, drain, snapshot latest claims/outcomes, compare with immutable backup; do not reset/force-push state branch or replay claimed alerts. Restore old schedule only after reconciliation and explicit owner authorization.

## Hard NO-GO conditions

- Candidate still references validation state branch, synthetic paths, `mock_only`, or old main publisher.
- Any existing scanner/publisher job can send Telegram before remote claim verification.
- Cannot demonstrate backup SHA/digest, failed CAS => no send, state/cache atomicity, and no duplicate send on rerun.
- Missing GitHub branch protection/permissions evidence or unresolved `claimed` / `send_unknown` operator runbook.
- GS25, main, PR #1, Draft PR #2, or operational state would be modified without separate explicit approval.

## Final status

**Change plan prepared only.** The isolated proof does not constitute deployable production integration. No production merge, deployment, real inventory call, real Telegram send, or state migration has been performed.
