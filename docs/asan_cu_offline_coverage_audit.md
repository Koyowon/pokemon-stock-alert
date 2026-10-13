# Asan CU candidate coverage audit (offline)

Date: 2026-10-13
Scope: 119 candidates in `asan_cu_watch_registry.json`, 7 Asan geographic query points in `cu_stock_monitor.py`.
This is an offline inventory audit, NOT proof of CU API coverage. No network queries, Telegram sends, workflow runs, or production changes.

## Source-derived counts

- Candidate entries: **119**.
- Non-empty address: **113**; empty address: **6**.
- CU store code (digit-only, after normalization): **28**; missing: **91**.
- Both CU code and address: **22**; code without address: **6**.
- Non-empty latitude AND longitude: **3**; no coordinate pair: **116**.
- Missing CU code but address present: **91**.
- Product barcode in registry: `8800286275732`.
- Initial product status: `NOT_QUERIED`; do not interpret missing observations as zero stock.

### Candidate area labels (raw `area` field)

| Area label | Count |
|---|---:|
| 배방읍 | 21 |
| 주소 미확인 | 17 |
| 둔포면 | 13 |
| 음봉면 | 10 |
| 모종동 | 7 |
| 신창면 | 7 |
| 탕정면 | 7 |
| 온천동 | 6 |
| blank | 6 |
| 인주면 | 5 |
| 영인면 | 4 |
| 삼동 | 3 |
| 송악면 | 3 |
| 용화동 | 3 |
| 풍기동 | 2 |
| 배미동 | 1 |
| 법곡동 | 1 |
| 읍내동 | 1 |
| 권곡동 | 1 |
| 방축동 | 1 |

Area labels are not verified against the full address. The label `주소 미확인` may appear even when an address exists.

### Existing seven Asan search points (lat, lon)

1. (36.790, 127.000)
2. (36.775, 127.050)
3. (36.795, 127.065)
4. (36.805, 127.095)
5. (36.798, 127.115)
6. (36.830, 127.070)
7. (36.920, 127.065)

### Only three candidates have coordinates

| Registry ID | Name | Latitude | Longitude |
|---|---|---:|---:|
| ASAN-CU-066 | 씨유 아산신정호공원점 | 36.77106 | 126.9832 |
| ASAN-CU-090 | CU 온양제일호텔점 | 36.78211 | 126.9994672 |
| ASAN-CU-092 | CU 아산팬더점 | 36.7901843 | 126.9938723 |

Even for these, distance to a search point does not prove API inclusion: the API search radius, ranking, pagination and store visibility are not established.

### Six candidates with missing address

- ASAN-CU-093: CU 아산배방한성점
- ASAN-CU-096: CU 선문대학교오렌지점
- ASAN-CU-098: CU 선문대학교기숙사점
- ASAN-CU-099: CU 아산온천마을점
- ASAN-CU-102: CU 아산권곡주공점
- ASAN-CU-107: CU 아산모산점

## Potential geographic blind spots (not confirmed omissions)

Prioritize reviewing **송악면** (southern area), **인주면/영인면** (northwestern area), **신창면** (western area), **둔포면/음봉면** (northern area), and the spread of **배방읍/탕정면** against the seven search coordinates. Administrative labels alone cannot establish API coverage.

## Remediation plan (offline first)

1. Preserve all 119 candidates; keep unknown stock as `NOT_QUERIED` or `NOT_OBSERVED`, never `ZERO_STOCK`.
2. Resolve the six empty addresses and normalize all area labels using existing source addresses. Mark unverified or partial addresses rather than inventing them.
3. For the 91 entries without store codes, prioritize **address/name crosswalk** against archived local state and already recorded API results; use exact store code as the stable identifier, and treat renamed/duplicate candidates as unresolved until evidence exists.
4. Geocode only from verified addresses using a separately authorized source/process; do not infer coordinates from area names. Record provenance and precision.
5. Build an offline distance-to-nearest-search-point report for all candidates with verified coordinates; distance is a planning heuristic, NOT an API inclusion test.
6. Establish API response radius, pagination, maximum returned records and geographic filter behavior only after explicit approval for controlled live queries.
7. Add new search points only after evidence-based gap analysis, deduplication and rate-limit assessment. Do not claim 119/119 coverage until observed and reconciled against the registry.
8. Keep existing Namwon, Jeonju, Jeju and Telegram logic unchanged; all experimental changes stay on `permission-test-20261013-cu`.

## Operational safety

This document is analysis only; it is not imported by the monitor, contains no executable calls, and does not modify the scheduled workflow or `main`.
