# Stage 15: manual review queue

`manual_review_queue.queue(root, captures, evidence=None, now=None)`
accepts exactly two offline CU or emart24 source manifests with increasing
UTC capture timestamps. It never performs provider requests or file writes.

Candidate evaluation requires the same store identity in both captures, region
coverage in both, no quarantined conversion rows, fresh capture timestamps,
and at least two distinct operator-declared evidence sources whose identity
fields match the candidate. The evidence declarations are **not independently
authenticated**. `manual_review` is a human-review queue only, not an
approval. Source authorization remains unverified.

Missing or changed stores are quarantined, never marked closed.
Registered stores are quarantined rather than re-added. The result explicitly
sets `approved_for_production: 0`, `automatic_registration: false`,
`closure_candidates: []`, and `read_only: true`.

All tests use synthetic provider rows and an offline main snapshot. No stock
API, Telegram, production state, or runtime workflows are accessed.
