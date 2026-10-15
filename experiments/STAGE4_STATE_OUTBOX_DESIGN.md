# Stage 4 isolated design evaluation (2026-10-16)

**Scope:** disposable branch only; no main, Draft PR #2, production state, API or Telegram changes.

## Compared options

| Architecture | Duplicate risk after Telegram succeeds but Git publish fails | Lost-alert risk | Protected main | Decision |
|---|---|---|---|---|
| Current CU/emart24: send, save, publish | High: next run may resend | Network/timeout ambiguity | Publisher targets protected main | NO-GO |
| Save state before send without outbox | Lower duplicate risk but a crash before send silently loses the event | High | Still needs state storage | NO-GO |
| Durable outbox, claim-before-send on dedicated state branch | At-most-once automatic send attempt; claim commit must succeed before send | A crash/timeout after claim may lose an alert | No state writes to main | Candidate |
| Send-before-claim with automatic retry | Duplicate risk under crash/ambiguous response | Lower loss in some cases | Can use separate branch | NO-GO for strict duplicate avoidance |

## Prototype
- `experiments/isolated_state_outbox.py`: pure queue, claim, CAS commit-before-send and state-branch path guard.
- `tests/test_isolated_state_outbox.py`: CU/emart24 fake events, failed claim, two writers, post-claim crash, repeated transitions, capacity and path isolation.
- `.github/workflows/isolated-state-outbox-offline.yml`: read-only test job; no network, real Git push, inventory API, or Telegram.

## Required integration design (not implemented)

1. Create a **dedicated state branch** (name to be agreed), initialized with validated current state at cutover. Do not weaken main branch protection.
2. Ensure every scan reads the **latest state branch** at run start, not stale state from `main`; scan code and config continue to come from reviewed main.
3. For each chain, atomically publish state+outbox as one compare-and-swap Git transaction; on non-fast-forward, fetch/reconcile or fail closed. CU and emart24 state must not be marked committed until the durable push succeeds.
4. Dispatch job loads the state branch, claims a pending event via an atomic non-force Git push, then calls Telegram **once**. If claim fails, send nothing. If Telegram fails or times out after claim, do not automatically retry without operator inspection.
5. Keep CU and emart24 events separate by chain, bounded pending queues, deterministic unique IDs, and retention policy. Detect state corruption, missing state branch, stale scans, and invalid producer artifacts.
6. Require isolated GitHub Actions end-to-end simulation and explicit rollback/runbook before production switch. Preserve the previous state and audit claimed-but-undelivered events.

## Important limitations

The prototype is **not wired into production CU/emart24 scanners or PR #2**. It validates policy and algorithmic invariants only. It does not prove protected-main write access, cross-branch artifact publication, or Telegram delivery. It prioritizes no automatic duplicate attempts over guaranteed delivery; exactly-once delivery is not possible with a simple Git/Telegram split.

**Decision: NO-GO for operational deployment until full integration tests, state migration design and explicit approval.**
