# Stage 17: regional read-only audit

`store_registry.regional_audit.summarize(report)` accepts an in-memory
Stage 16 review report and returns deterministic counters for each monitored
region, quarantine reason, declared evidence state, capture freshness, and
repeat-capture observations. `render_markdown(summary)` renders a human-readable
summary without disk or network activity.

Missing observations and identity changes are not evidence of closure.
Submitted evidence remains unverified. The audit refuses production-approved
candidates and never grants approval, writes state or registers stores.

Stage 16 originally ran 60 tests because importing `QueueTests` directly
into the report test module caused unittest to collect those six tests twice.
Importing the module under an alias avoids duplicate collection. The intended
suite is 49 existing unique tests + 5 report tests + 7 regional audit tests
= **61 distinct tests**. Verify the exact count from GitHub Actions logs.
