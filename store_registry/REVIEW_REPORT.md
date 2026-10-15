# Stage 16: read-only review reports

`store_registry.review_report.build_report(root, captures, evidence=None, now=None)`
returns an in-memory JSON-compatible report. `render_json(report)` and
`render_markdown(report)` return strings; callers choose whether to display
them. Neither function writes to disk, calls APIs, sends notifications or
changes operational state.

Each row includes chain, code, name, address, region, repeated-capture
assessment, capture timestamps, freshness, declared evidence references,
quarantine reasons and next verification actions.

Evidence references are explicitly unverified. A `manual_review` status is
not a production approval. Closure candidates and production approvals remain
empty. Markdown table cells escape pipes and line breaks.
