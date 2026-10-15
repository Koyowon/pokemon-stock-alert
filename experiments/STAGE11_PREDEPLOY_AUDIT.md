# Stage 11 — Pre-deployment audit and cutover plan (2026-10-16)

**Decision: NO-GO.** This is an audit only. No main/PR #1/Draft PR #2/production state/Telegram/API changes. Stage 1–10 isolated results demonstrate mechanisms, not an integrated production-ready service.

## Critical blockers, grounded in candidate source

1. **Publisher hard-coded to protected main.** `state_push_publisher.py` lines 114–117 demand `GITHUB_REF=refs/heads/main`; lines 152,157 fetch main and line 179 pushes main. Candidate CU/emart24 workflow publish jobs also check out main and use `state-publisher-main`. Branch `main` is marked protected; branch protection details API returns 403. No claim of main write permission.
2. **Scanner baseline and atomicity.** CU `cu_stock_monitor.py` loads `cu_stock_state.json` locally and calls `save_state` at end; emart24 `monitor.py` loads `state.json`, caches `stores.json`, then saves locally. Neither scanner fetches the latest dedicated state branch before scan. A scanner must read an authoritative state snapshot and record its Git SHA; publication must CAS/reconcile stock and outbox as a single transaction. Emart24 state + stores must publish atomically.
3. **Prototype is not production dispatch.** `experiments/stage10_integrated.py` claims a synthetic probe file. `mock_dispatch_from_committed` simply returns *every* claimed event each invocation; if wired directly to Telegram it would attempt repeats. Do NOT reuse as production sender. A real sender needs the *just-claimed event IDs from a successful unique Git commit*, remote commit verification, and idempotent orchestration.
4. **Claimed is not delivered.** `experiments/isolated_state_outbox.py` claim_event only writes `status=claimed`, without `claimed_at`, attempt ID, outcome, or acknowledgement. `claimed_audit` flags missing timestamps indefinitely; cannot distinguish sent vs lost. Need claim timestamp, claim commit SHA, sender run ID, durable outcome records, retention, escalation and explicit operator action. Telegram ambiguous timeout may mean delivered; no automatic replay of claimed events.
5. **Reconciliation is prototype-only.** `preserve_alerts` detects conflicting claimed/pending state but is not integrated into scanner/publisher. Any stale scanner must fail closed rather than silently reset claimed to pending. Test same-store concurrent stock changes, both chains, multiple artifacts and max retry exhaustion.
6. **No real cutover/rollback yet.** Prior stages tested synthetic migration and read-only rollback snapshot comparison; they did not migrate real operational state or execute an operational rollback. Avoid resetting branch or reverting claimed records; rollback should disable new dispatcher, preserve an immutable state snapshot, and explicitly reconcile unacknowledged events.
7. **Permissions and source trust.** Separate scanner read-only permissions and artifact upload; publisher/dispatcher use `contents:write` only for narrow jobs, no Telegram token in scan/publish, secrets only in dispatcher. Check artifact run ID, workflow SHA, base SHA, path allowlist, manifest digests, immutable artifact ID, protected environment approvals, branch policy, GitHub Actions default permissions, and untrusted PR execution. Do not give write token to unreviewed workflow code.
8. **Tests do not establish delivery.** Stages 1–10 used fake inventory and mock Telegram; no real external delivery, no real state migration, no protected-main write test. At-most-once automatic *attempt* is achievable; exactly-once delivery is not guaranteed.

## Proposed target workflow

- **Scan:** reviewed code from protected main; `contents:read`; read latest dedicated state branch (state SHA and per-chain baseline); fake/offline validation first; create per-chain inventory + outbox artifact; no Telegram.
- **Publish:** separate `contents:write` job, branch target allowlisted dedicated state branch, no force push, validated artifact origin/manifest, compare-and-swap commit with bounded retries. CU state single file; emart24 state+store cache atomic. If any failure, no send.
- **Dispatch:** separate trusted job reads remote pending events, atomically claims one or bounded batch on state branch with timestamp and unique claim ID; only after successful Git push + remote verification attempts Telegram once; store outcome as audit data without changing claimed back to pending. Distinguish `claimed`, `sent_confirmed`, `send_failed`, `send_unknown` in an append-only audit (carefully avoid duplicate retry).
- **Watch:** report stale pending, stale claimed/unknown, scan failures, failed publish, and outbox capacity. Escalate to operator, never auto-replay ambiguous claims.

## Proposed cutover sequence — requires separate approval for EACH operational write

1. Freeze and record main SHA, workflow IDs, PR SHA, current state SHA, and current running jobs. Read and validate CU `cu_stock_state.json`, emart24 `state.json` + `stores.json`; capture immutable backups and checksums. Never copy secrets into artifacts/logs.
2. Validate branch protection and Actions token rules manually (Settings > Branches; Rules > Rulesets; Actions > General). Keep main protected; create dedicated production state branch only after approval.
3. Prepare an isolated, read-only dry-run using sanitized snapshot; compare per-store counts, keys, alert flags and pending/claimed histories. Record explicit migration schema version, rollback marker and manifest. Ensure no duplicate first-positive alerts.
4. On approved maintenance window, pause old CU/emart24 scheduled scans, drain in-flight jobs, snapshot again and verify SHA unchanged, initialize dedicated state branch with validated state, then deploy reviewed workflows. Do not enable dispatcher yet.
5. Run scan+publish shadow mode with mock Telegram; verify state and inventory against baseline. Enable real dispatcher only with separate explicit authorization and a small pilot; observe audit and alerts before expanding.
6. Rollback: disable new dispatcher and scans, stop further state writes, retain all claimed/outcome history, restore old workflow only after reconciling any newer inventory state and outstanding alerts. Do not force-push or auto-replay ambiguous sends. Record operator sign-off.

## Required final acceptance gates

- Protected main settings/permissions verified by repo owner.
- Reviewed production publisher targets state branch, never main, with source/path authorization and CAS.
- Scanner consumes latest state branch and preserves pending/claimed and sequence; CU/emart24 state files correct.
- Dispatcher sends only events claimed in *its own successful commit*, never every claimed event; durable outcome and alert audit; no auto retry on unknown.
- Multi-job race, crash windows, partial cache writes, corrupt artifacts, stale baselines, retry exhaustion, reruns, and rollback exercised in isolated Actions.
- Complete runbook, snapshot checksum, backout test, monitoring, access control and explicit production deployment/merge approval.

**Current gate: NO-GO.** Do not merge Draft PR #2 or activate any operational workflow based on this audit.
