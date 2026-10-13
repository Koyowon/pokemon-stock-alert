# Asan CU 123-store status: offline operating policy

## Unknown stock
- Include all 123 unique registry IDs in each status snapshot.
- `IN_STOCK` means positive observed stock; `ZERO_STOCK` means an observed zero.
- `NOT_OBSERVED` and `NO_VALID_STOCK_VALUE` are **unknown**, never zero.
- An unknown row may be displayed as unknown only when all configured Asan coordinate queries succeeded, no observation conflict occurred, and `query_succeeded=True`.
- Any `NOT_QUERIED` row, failed coordinate query, missing/duplicate registry ID, or ambiguous observation must block status delivery.
- Registry completeness is **not** proof of observation coverage. An unknown row is not an assertion of stock availability.
- If the desired policy is to require a real stock observation for all 123 stores, do not enable this channel until the monitor can prove that stronger condition.

## Dedicated Git state branch
- The state ref is `refs/heads/state/asan-cu-status` and the only state file is `asan_status_delivery_state.json`.
- Missing or unreadable branch => fail closed. Never auto-create it in the delivery path.
- A compare-and-swap lease protects the remote ref from stale concurrent writers; an `IN_FLIGHT` state blocks automatic retries.
- A successful Telegram API acknowledgement followed by a failed state write still requires manual reconciliation. Exactly-once Telegram delivery is not guaranteed.
- The current workflow is read-only (`contents: read`, `persist-credentials: false`) and **cannot operate this delivery path as configured**.

## Least-privilege authentication design (not installed)
1. Create a dedicated GitHub App installed only on `Koyowon/pokemon-stock-alert` with **Contents: read/write** repository permission, without Actions/administration permissions.
2. GitHub App Contents permission is repository-wide, **not branch-scoped**. Use an enforced repository ruleset or branch protection to limit writes to the dedicated state branch and ensure the App cannot modify `main` or other branches. Validate the actual ruleset bypass and permission behavior before issuing credentials. A ruleset alone cannot magically grant branch-specific Contents tokens.
3. Provision a short-lived installation token only in a separately approved future workflow step, and use an isolated Git remote with that token. Never log the token, persist credentials in checkout, or expose it to pull-request code.
4. Keep status sending disabled by default. Require an explicit opt-in, an existing initialized state branch, valid credentials, and a successful state read/CAS before any Telegram call.
5. Keep the existing CU monitor workflow, legacy alerts and `cu_stock_state.json` unchanged until separately approved.

## Acceptance checklist
- No changes to `main`, existing workflow or legacy state.
- Offline tests cover unknown-vs-zero, `NOT_QUERIED` rejection, CAS conflicts, missing state branch, failed CAS and partial sends.
- A future separate authorization review must check whether the App can write only the intended branch under the actual repository ruleset. Do not claim this property based on token scopes alone.
