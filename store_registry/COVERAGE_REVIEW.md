# Stage 14: capture completeness and conservative changes

The optional `coverage` manifest field is an object:
```json
{"scope":"partial","regions":["namwon"],"evidence":"operator-capture-note"}
```
A `complete` capture must list all four monitored regions (namwon, asan,
jeonju, jeju). Missing coverage is treated as partial, not complete.

`assess()` reports the capture age and stale (>24h) status, the declared
coverage and whether it has independent verification (always false), removal
observations that require review, and repeat-capture requirements.

**No removal constitutes verified closure**, including observations in a
declared complete capture. All new stores require independent evidence.
Operator-entered evidence is a reference, not a verified authorization.

The workflow only reads the main snapshot, runs synthetic tests and compares
saved data. It does not retrieve store data from a provider or persist state.
