# GitHub Actions state push collision mitigation (PROPOSAL ONLY)

Status: NOT APPLIED. No existing workflow has been edited.

## Problem
CU, emart24, and GS25 each have separate `concurrency.group` values and
independently commit state to `main`. GitHub Actions concurrency groups only
serialize jobs within the same group; `git pull --rebase` can still fail when
other monitors push between pull and push. Changing the three groups to one
would serialize entire inventory scans and could delay monitoring significantly.

## Recommended patch for later approval
Keep per-chain scan concurrency. Replace only the final state commit/push
step in each workflow with a shared reusable **state-write** job that serializes
state pushes, OR implement a bounded optimistic retry in each push step:

1. Run inventory scan, persist its resulting state file as a job artifact.
2. In a separate short job, fetch the latest `main` before applying that
   chain's state artifact; do not commit any other chain's state file.
3. Serialize these write jobs using the same concurrency group across chains,
   with `cancel-in-progress: false`. Use a separate job so the full scans
   remain concurrent. GitHub Actions cross-workflow concurrency semantics
   require testing; a single dedicated state-writer workflow is preferable
   if strict ordering is required.
4. On a non-fast-forward push, refetch `main`, reapply only this chain's
   state file and retry a bounded number of times with backoff.
5. Never replay inventory/API calls or resend Telegram during push retries.
6. If push still fails, fail the workflow and retain the generated state
   artifact for recovery; alert deduplication needs a separate durable outbox
   design before promising exactly-once delivery.

## Verification before any production rollout
Use a local bare Git remote with concurrent simulated writers and assert
that CU, GS25, and emart24 state changes all survive. Test repeated conflicts,
no accidental inclusion of unrelated files, and final failure handling.

The existing sixth regression test intentionally fails until a production
collision strategy is approved and implemented. It is a static policy test,
not a real Git collision simulation.
