# Stage 13: official store-directory discovery (offline handoff)

Official consumer-facing store directories:
- CU: https://cu.bgfretail.com/store/list.do?category=store
- emart24: https://m.emart24.co.kr/store

Both support store searches. This does **not** establish permission to scrape,
republish, automate, or call undocumented endpoints. Confirm terms and request
provider authorization before any unattended retrieval. The current stage
makes no provider requests and implements no scraper.

An operator may prepare a locally captured, permitted JSON payload with
`stores` rows, then attach a manifest containing `chain`, exact
`source_page`, `captured_at` (UTC Z), `capture_method` set to
`operator_supplied_export`, `authorization_reference`, and `payload`.
`authorization_reference` is a claim only, **not independently validated**.

`store_registry.source_audit.assess(root, manifest, previous=None)` returns:
- canonical converted rows and rejected rows via `conversion_report`
- a read-only `current` snapshot for an optional future comparison
- `changes`: added, removed, and changed codes between two supplied snapshots
- SHA-256 hashes of the supplied inputs, and `approved_for_production: 0`

Snapshots must represent the same coverage and provider. A removed code
means absent from that supplied snapshot, **not a verified store closure**.
Rejected rows are not added to `current`; review rejection counts alongside
deltas. No file persistence, Telegram, stock APIs or production admission.
