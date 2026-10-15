# Final pre-production security and integrity review (isolated branch only)

**Decision: NO-GO.** Review date: 2026-10-16. This document does not authorize deployment. No production workflow, state, main, emart24-recovery, or PR #1 change is part of this review.

## Verified facts

- The isolated test workflow has `permissions: contents: read` and `persist-credentials: false`. Its two-job `actions/upload-artifact@v4` → `actions/download-artifact@v4` transfer succeeded in run 38815264238; metadata mismatch, missing artifact and post-upload byte tampering were rejected. The old production workflow collision-policy test remains failing, as expected.
- The three **production** workflows still declare `contents: write` at workflow scope, use credential-persisting checkout and commit/push from their scan jobs. Their concurrency groups differ (`pokemon-stock-monitor`, `cu-stock-monitor`, `gs25-stock-monitor`), so no cross-chain serialization is guaranteed.
- Candidate publisher uses a temporary clean checkout, compares remote same-chain state with scan baseline, commits only allowlisted paths and retries rejected pushes up to 3 times. The emart24 bundle must contain both `state.json` and `stores.json`.
- Candidate artifact verifier validates `schema`, chain, run ID, attempt, base SHA, allowlisted file paths and SHA-256. **The manifest is NOT cryptographically signed**: a malicious writer could replace both the files and their manifest digests. SHA-256 alone detects accidental changes or a modified file against an unchanged manifest, not a fully forged artifact.

## P0 blockers (must be closed before approval)

1. **Trust binding and artifact provenance.** Pin download to the producer job within the same workflow run, use unique run-scoped artifact name and immutable artifact ID/digest when available. Verify the artifact's platform-provided digest against trusted job output; do not rely on manifest fields supplied by the artifact alone. Bind expected `run_id`, `run_attempt`, `github.sha`, chain and producer identity to GitHub Actions context, not to artifact metadata. Decide whether provenance attestation is required by the threat model. The current `prepare` comment/step calling the manifest 'signed' is inaccurate.
2. **Publisher permissions.** Scope `contents: write` only to the dedicated publishing job; scan and test jobs use `contents: read`. Publisher must not receive Telegram secrets; checkout should default to `persist-credentials: false` outside the controlled publishing job. Limit push to `refs/heads/main` and verify `origin` resolves to the intended repository before granting write credentials. Review branch protection/rulesets and token behavior.
3. **Stale run and same-chain race.** Preserve the fail-closed same-chain comparison for both files of the emart24 bundle. Reject a stale artifact if another writer has advanced its chain. Require a deterministic retry/backoff cap and alert on exhaustion; no forced push or `git pull --rebase` that implicitly merges unrelated state.
4. **Recovery safety.** Recovery reuses the original artifact and revalidates run identity, checksum and base SHA; never rescan or resend Telegram. A failed publish followed by a newer same-chain state must be rejected, not replayed. Manual recovery requires operator review of baseline and current remote state.
5. **Rollback safety.** Revert only approved workflow/helper code using a new commit; never reset/force-push `main` or automatically restore old state JSON. Preserve the latest valid per-chain state and emart24 store cache. Require a restore drill on a disposable local bare repository.

## P1 code and integration gaps

- The `state_push_retry_candidate.py` CLI accepts a single `--state-file` but `publish()` rejects `state.json` without `stores.json`. Implement a reviewed bundle-aware CLI before wiring emart24.
- The artifact verifier accepts self-consistent metadata and SHA-256 hashes; test forged manifest + matching forged file to demonstrate the provenance gap. Reject unknown manifest keys/extra downloaded files if the contract requires an exact artifact layout.
- Verify `base_sha` is an ancestor of the target branch, not merely a commit that exists in the local checkout; ensure expected ref is `main` and source repo identity is fixed.
- Explicitly test artifact producer failure, download action failure, job `needs` / `if` policies, malformed `files` type, invalid UTF-8, symlinks, path traversal, partial cache bundles and no-op publication.
- The candidate reset is destructive; only run it in a newly created disposable checkout. Avoid secret leakage in action logs and set explicit `timeout-minutes`, `GIT_TERMINAL_PROMPT=0` and `GIT_ALLOW_PROTOCOL` policy for local-only tests.
- Test-only workflow uses floating action tags `@v4`; production deployment should pin actions to reviewed commit SHAs, subject to repository policy.

## Proposed production change inventory — NOT APPLIED

| File | Proposed change |
|---|---|
| `.github/workflows/stock-monitor.yml` | Replace `Save stock and store cache` with producer artifact and dedicated publisher job; preserve valid emart24 `state.json` + `stores.json` pair and all-unknown failure policy |
| `.github/workflows/cu-stock-monitor.yml` | Replace `Save CU stock state only` with CU artifact and publisher; preserve scan-success guard |
| `.github/workflows/gs25-stock-monitor.yml` | Replace `Save GS25 state` with GS25 artifact and publisher; explicitly define partial-success / `always()` behavior |
| New reviewed helper (location TBD) | Bundle-aware CLI, trusted run context verification, allowlisted path publish, bounded retry and same-chain stale rejection |
| New tests / documentation | CI negative tests, permissions review, rollback runbook and operational monitoring |

Do not copy the isolated `tests/` candidate directly to production without addressing P0 blockers.

## Approval gates

- [ ] All P0 blockers closed with evidence from isolated tests.
- [ ] A reviewer verifies artifact provenance independent of attacker-controlled manifest content.
- [ ] Each production workflow's read/write permission split, secrets scope and guards reviewed.
- [ ] CU, GS25 and emart24 integration tests pass; emart24 cache is preserved.
- [ ] Same-chain conflict, non-fast-forward exhaustion and rollback drills pass.
- [ ] Production diff contains only explicitly approved files; protected `main` remains unchanged until approval.
- [ ] Explicit human approval of rollout window, one-chain-at-a-time order, monitoring thresholds and rollback owner.

**No-go if any checkbox remains unchecked.**

## Recommended next isolated validation

Add a test that forges **both** the manifest checksum and the JSON payload, proving the current verifier accepts self-consistent but untrusted artifacts. Then design a trusted provenance binding (producer artifact ID/digest and expected GitHub context) and test rejection of mismatched provenance, plus a publisher CLI dry-run that cannot access network, Telegram or the real repository.
