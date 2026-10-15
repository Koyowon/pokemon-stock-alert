# Draft PR #2 — pre-merge operational security review

Review date: 2026-10-16. **NO-GO for merging until the remaining gates below are resolved.** This document is review-only; it does not approve deployment.

## Scope and isolation
PR #2 proposes `monitor.py`, `state_push_publisher.py`, `state_artifact_contract.py`, CU/GS25/emart24 workflow changes, and read-only offline tests. `main`, PR #1, `emart24-recovery`, and operational JSON files remain unchanged. The PR-only test runs without Telegram secrets, stock API calls, network connections from tests, or Git pushes.

## Findings and fixes on PR branch

1. **P0: scan failure must not publish stale state.** The original draft used `if: always()` for emart24 and GS25 artifact creation. This could publish a stale state after a scan failure. Fixed to `if: success()` for all three chains. The emart24 monitor now fails closed if all inventory values are unknown and atomically saves JSON. **Tradeoff:** GS25 may write valid partial results then exit nonzero; conservative fail-closed publication skips that partial state and may repeat a notification on a later scan. Requires explicit policy approval or redesign before merge.
2. **P0: artifact provenance.** The publisher verifies producer-supplied manifest SHA-256, chain, run ID, attempt, base commit and file checksums. Downloads now select the producer's `artifact-id` rather than a predictable artifact name. Producer's `artifact-digest` is present and format checked but **not independently recomputed/compared against the archive**. Artifact provenance is therefore improved but not complete cryptographic attestation. Approve threat model or add independent digest verification.
3. **Least privilege.** Scan jobs have `contents: read`, `persist-credentials: false`, Telegram secrets only on the scan step. Publisher has `contents: write`, shared concurrency group, main-only ref/repo/origin guards, trusted artifact metadata and a bounded retry. Publisher retains write checkout credentials as necessary; review branch protection and token permissions.
4. **Same-chain conflict and retry.** Publisher fetches latest main and refuses a same-chain state change since the scan baseline, except an identical update. Emart24 state and cache are one bundle. On rejected push, it retries up to 3 times; no force push, no rescan, no Telegram replay. Confirm concurrency and failure notification under real workflow semantics.
5. **Branch protection.** GET `/branches/main/protection` returned **403 Resource not accessible by integration**. GET `/rulesets` returned an empty list. This is *not* proof that main is unprotected. Repository owner must inspect Settings → Branches / Rulesets and check whether GitHub Actions token is allowed to push state commits.
6. **Rollback.** Revert only the approved workflow/helper code in a new PR/commit. Do not `reset --hard` or force-push main and do not overwrite current state JSON with old snapshots. Pause schedules first if the new publisher fails, inspect last valid per-chain JSON and failed run artifacts, and re-enable one chain at a time after an isolated recovery test. State restoration is manual and requires checking for newer valid updates.

## File-level integration map
- `.github/workflows/stock-monitor.yml`: emart24 scan and atomic `state.json`/`stores.json` bundle; fail-closed artifact gate; dedicated publisher.
- `.github/workflows/cu-stock-monitor.yml`: CU scan-success gate and CU-only state artifact.
- `.github/workflows/gs25-stock-monitor.yml`: GS25 scan-success gate; partial-state tradeoff noted.
- `monitor.py`: all-unknown API health failure and atomic state/cache file saves.
- `state_artifact_contract.py`: run-scoped metadata and checksums.
- `state_push_publisher.py`: origin/repo/ref guard, same-chain compare, bounded retry.
- `tests/test_rollout_pr_offline.py`, `.github/workflows/state-publisher-pr-offline.yml`: offline-only regression gate.

## Approval gates
- [ ] Latest PR push and PR-triggered offline checks green.
- [ ] GS25 partial-success state and duplicate-alert policy resolved or explicitly accepted.
- [ ] Actual artifact archive digest verification / provenance policy reviewed.
- [ ] Main branch protection/rulesets and GITHUB_TOKEN write permissions inspected by repository owner.
- [ ] A full disposable bare-Git integration test covers three chains, non-fast-forward retries, stale same-chain updates, failure, no-op, and rollback.
- [ ] Emart24 all-unknown and atomic state/cache regression tests run against the exact PR code.
- [ ] Production workflow schedule and alert behavior reviewed; rollout and rollback owner identified.
- [ ] Explicit user approval after these gates; only then mark PR ready and merge.

**Current decision: DO NOT MERGE.** Passing a small offline contract suite does not substitute for end-to-end publisher tests or live operational permission verification.
