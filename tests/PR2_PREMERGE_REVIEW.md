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

## Follow-up remediation (2026-10-16)

- Added `tests/test_publisher_bare_git_offline.py`: CU/GS25/emart24 real candidate publisher against **disposable file:// bare Git remotes only**, including same-chain races, unrelated-chain preservation, non-fast-forward retry, no-op, and stale rollback. A special offline-only origin exception requires both `STATE_PUBLISH_OFFLINE_TEST=1` and `GIT_ALLOW_PROTOCOL=file`; the production GitHub origin allowlist remains.
- Added `state_artifact_platform.py`: uses GitHub Actions artifact REST metadata to check producer artifact ID, archive `sha256:` digest, workflow run ID, artifact name and expiry. Publisher downloads by artifact ID, flattens the bundle, and checks independently provided manifest digest and each JSON file hash. The GitHub metadata digest validates platform provenance; it is not an independent recomputation of the compressed archive bytes. Requires publisher `actions: read`.
- Updated GS25 partial-success logic: successfully completed regions can be persisted and published even if another region failed, while incomplete regions retain their prior baseline. Added a fake API/Telegram test verifying that an already-persisted alert is not resent on the next successful scan.
- **Residual GS25 limitation:** Telegram delivery happens before the Git push transaction. If Telegram succeeds but the later artifact upload or Git push fails, the next run may resend the alert. Exactly-once external notifications are **not guaranteed**. A durable outbox with idempotency keys or equivalent architecture is required to eliminate this failure window; do not claim duplicate-alert prevention is complete.
- **Main protection is unverified:** `GET /repos/Koyowon/pokemon-stock-alert/branches/main/protection` returned HTTP 403 (integration permission denied). Repository rulesets list was empty, but that does not prove the branch is unprotected. Owner verification remains mandatory.
- **Rollback drill:** local bare Git simulation proves stale emart24 state/cache cannot overwrite a newer remote update; this is not a production rollback exercise. Never force-push or restore old JSON automatically.
- **Approval status remains NO-GO** pending owner verification of branch protection and GS25 notification idempotency/failure-window policy, plus an explicit user sign-off. No production actions performed.

## GS25 durable notification outbox (2026-10-16)

Implemented on this PR branch only:
- `gs25_independent/gs25_auto_monitor.py` now records deterministic pending alert events in the GS25 state JSON, and does not call Telegram during scan. Completed regions advance while failed regions retain the previous baseline.
- The GS25 workflow publishes the validated state artifact first; a new `notify` job then calls `gs25_alert_dispatcher.py`.
- The dispatcher fetches current main, atomically changes pending events to `claimed` via a normal non-force Git commit/push, and only then calls Telegram. Git push failure causes zero sends. Claims are not automatically retried after crashes or ambiguous Telegram timeouts.
- `tests/test_gs25_outbox_offline.py` covers durable claim before delivery, crash after claim, ambiguous Telegram result, and blocked Git push, all using fake messages and local disposable bare Git.
- **Important delivery semantics:** at-most-once automatic send *attempts*, not exactly-once delivery. If the process crashes after the claim or Telegram times out, the alert may be lost. Operators must inspect claimed entries before any manual replay.
- **Further risk:** the event key hashes product, region, store, old and new quantities. A later legitimate return to the same transition may reuse an old key and be suppressed. Event lifecycle and retention/rotation need a dedicated test and policy before merge.
- **Further risk:** the outbox lives inside the same state file and can grow indefinitely. Add bounded retention with a safe event lifecycle before production.
- **Further risk:** GitHub branch protection could prevent the dispatcher from committing claims; this is intentionally fail-closed (no Telegram send), but needs repository-owner verification.
- **Test status:** GitHub Actions run 38817324918 completed successfully with 37/37 unittest invocations. Inherited base test cases are repeated in the GS25 outbox subclass, so 37 is the invocation count, not 37 unique scenarios.

### Owner checklist for main branch protection (unverified: API HTTP 403)
1. Open repository Settings → Branches and Settings → Rules → Rulesets; identify every rule targeting `main`.
2. Check whether `GITHUB_TOKEN` can push normal commits to `main`, whether pull-request-only changes are enforced, and whether Actions bypass is permitted.
3. Check Actions → General → Workflow permissions and organization policy: `contents: write` and `actions: read` for the publisher/notify jobs.
4. Verify required status checks, signed commits, allowed actors, linear history, and push restrictions; do not weaken protection just to make state publication work.
5. If token pushes are blocked, redesign persistence outside protected `main` (e.g., dedicated state branch/storage) before merging.
6. Confirm repository owner approves at-most-once semantics and operational handling of `claimed` alerts with uncertain delivery.

**Decision remains NO-GO.** No main merge, production API, Telegram, or production Git push was performed.

### Event lifecycle follow-up
The scan now uses a monotonic `alert_sequence` in its state to distinguish repeated legitimate transitions. It retains at most 1,000 historical `claimed` entries, never discards a pending event silently, and fails closed if more than 1,000 events are pending. An offline regression test exercises a 1→3→1→3 stock sequence. These changes address the earlier event-key reuse and unbounded claimed-history findings. Pending capacity still requires operational monitoring.

The at-most-once choice remains deliberate: ambiguous delivery and post-claim crashes can cause missed notifications. `main` protection is still unverified (403). These are explicit sign-off blockers, not a green-light to merge.

## GS25 scan/publish versus notification-claim concurrency (2026-10-16)

The race was reproduced with actual candidate Git publication and dispatcher against disposable `file://` bare Git remotes, never the production remote. A scan based on the previous GS25 state can encounter a concurrent `pending → claimed` notification commit.

Remediation:
- `state_push_publisher.merge_gs25_claim_only` allows a rebase only when the remote GS25 change relative to the scan base consists **exclusively** of pending-to-claimed transitions with identical event messages. It carries claimed status into the new candidate state, so an already-claimed notification is never reopened. New inventory changes, event removal, event message changes, and other remote modifications still fail closed.
- The existing bounded push retry handles a claim that lands after fetch but before push. Both pre-existing claim and mid-push collision have real bare-Git regression tests.
- GS25 `notify` uses `always()` and depends on both `scan` and `publish`, so previously published pending events may be claimed even when the current scan or publication fails. The claim-before-send rule still applies.
- Tests assert each fake Telegram message is attempted once, claimed entries survive, and the new pending event is eventually delivered without resending the earlier claimed event.
- Caveats: exactly-once Telegram delivery is impossible with this Git/Telegram split; an ambiguous Telegram timeout or post-claim crash can still lose an alert. Branch protection API remains 403/unverified. No production publish/Telegram/API was attempted.

**NO-GO:** remain Draft; await owner review of main branch protection and explicit acceptance of at-most-once delivery semantics.
