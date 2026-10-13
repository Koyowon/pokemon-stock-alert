# Asan CU 119-candidate offline cross-reference and priority report

Date: 2026-10-13
Branch: `permission-test-20261013-cu`
Barcode: `8800286275732`

## Sources reviewed

- `asan_cu_watch_registry.json` — 119 candidate rows, initial status `NOT_QUERIED`
- `cu_stock_state.json` — 164 stored CU store records, including 28 with `city == "아산"`
- `stores.json` — 114 records, but chain-specific CU provenance is not established from the file alone; **not suitable as proof of CU store codes**
- `cu_stock_monitor.py` — CU API parses digit-only `storeCode` and monitors seven Asan geographic points
- Existing `docs/asan_cu_offline_coverage_audit.md`

All comparisons used saved repository content only; no live CU API, Telegram or Actions execution.

## Results

| Metric | Count |
|---|---:|
| Candidate rows | 119 |
| Codes already in candidate registry | 28 |
| Those 28 codes present in saved CU state under Asan | 28 |
| Missing codes before cross-reference | 91 |
| **New CU codes proven by offline cross-reference** | **0** |
| Missing codes after cross-reference | **91** |
| Candidate rows with a nonempty address | 113 |
| Candidate rows with missing address | 6 |
| Rows in two exact-address collision groups | 4 |

The existing 28 codes are historical observations in the saved CU state, **not proof of current store operation, current stock, or coverage**. No unknown code was assigned from `stores.json` because its entries cannot be independently established as CU records.

### Exact-address collision groups (possible rename, duplicate or distinct units)

- `ASAN-CU-008` 씨유 아산관대점 ↔ `ASAN-CU-089` CU 아산퍼스트점; both list **충청남도 아산시 둔포면 충무로 1396**.
- `ASAN-CU-078` 씨유아산테크노밸리2호점 ↔ `ASAN-CU-079` 씨유 아산제2테크노밸리점; both list **충청남도 아산시 둔포면 운용길 73**.

Exact shared address does not establish that these are the same active store. **Do not merge or delete candidates without further evidence.**

### Missing address despite a known historical CU code

- `ASAN-CU-093` CU 아산배방한성점
- `ASAN-CU-096` CU 선문대학교오렌지점
- `ASAN-CU-098` CU 선문대학교기숙사점
- `ASAN-CU-099` CU 아산온천마을점
- `ASAN-CU-102` CU 아산권곡주공점
- `ASAN-CU-107` CU 아산모산점

The saved `cu_stock_state.json` contains addresses for these known codes; those can be reviewed separately for provenance and freshness before copying into the registry. This review does not modify candidate addresses.

## Per-candidate prioritization

See [`asan_cu_candidate_review_priorities.csv`](asan_cu_candidate_review_priorities.csv) for **all 119** entries.

- **P0_ADDRESS_COLLISION (4):** investigate exact-address alias/duplicate/rename risk; all four still lack codes.
- **P1_MISSING_CODE (87):** remaining missing-code candidates, prioritized for CU-only archival matching, address validation, and controlled verification later.
- **P2_CODE_KNOWN_ADDRESS_MISSING (6):** review existing historical CU state address and confirm currency.
- **P3_CODE_KNOWN (22):** historical code and candidate address available; still no proof of current API inclusion.

## Next safe actions

1. Preserve all 119 candidates and 91 unknown codes as unresolved. Do not substitute `stores.json` codes without chain provenance.
2. For six code-known/address-missing entries, review saved CU state addresses and record provenance; do not silently overwrite.
3. Investigate two address-collision pairs using offline saved evidence, including potential renamed store or multiple units.
4. Create a CU-only crosswalk with explicit `registry_id`, `cu_store_code`, source file, observation timestamp (if known), match type and confidence; require strong evidence for any newly assigned code.
5. Only with separate authorization, perform controlled API/official-source checks to establish live identity and search coverage.
6. Never turn `NOT_OBSERVED` or `NOT_QUERIED` into `ZERO_STOCK` without an explicit observed quantity.

## Safety

This report and its CSV are non-executable review artifacts. No production CU monitor, scheduled workflow, Telegram logic, GitHub Actions run, or `main` branch was changed.


## Follow-up: saved-state address backfill and duplicate review (2026-10-13)

Six previously blank candidate addresses were copied **verbatim** from `cu_stock_state.json` using both the existing digit-only `cu_store_code` and normalized store name. Each candidate's `review_note` now names the saved-state source. This establishes provenance, **not current location or operational status**.

| Candidate | CU code | Saved-state address |
|---|---|---|
| ASAN-CU-093 | 27959 | 충청남도 아산시 배방읍 아산시 배방읍 공수리 1480 1층 102호호 |
| ASAN-CU-096 | 32601 | 충청남도 아산시 탕정면 선문로221번길 70 선문대학교 (갈산리) 선문대학교 |
| ASAN-CU-098 | 37980 | 충청남도 아산시 선문로221번길 70 (탕정면) 선문대학교 아산캠퍼스 생활관친교관1층 |
| ASAN-CU-099 | 40839 | 충청남도 아산시 시장길15번길 13 |
| ASAN-CU-102 | 42772 | 충청남도 아산시 박물관로 13 (권곡동, 주공아파트) 1층 상가동 102호 |
| ASAN-CU-107 | 54071 | 충청남도 아산시 배방읍 모산로 151-1 (공수리) |

The ASAN-CU-093 saved address appears to repeat `아산시 배방읍` and the `호` suffix. It was intentionally **not silently corrected**. Other copied addresses also require freshness and formatting checks before being used as geocoding inputs.

### Four collision candidates — source-only follow-up

- **ASAN-CU-008 ↔ ASAN-CU-089:** same address `충청남도 아산시 둔포면 충무로 1396`; candidate sources respectively include a public licensing-based list and map/business listing; both cite the same job-ad URL. The shared job-ad URL is **not independent corroboration** of identity, renaming, or current occupancy.
- **ASAN-CU-078 ↔ ASAN-CU-079:** same address `충청남도 아산시 둔포면 운용길 73`; both cite a public licensing-based list. This alone cannot distinguish duplicate records, aliases, renamed store or two store units.

None of these four candidate names has a verified matching Asan CU code in the saved CU state. All four remain separate candidates with blank codes; **no merge, delete, or speculative code assignment**.

### Reconciliation after update

- 119 unique registry IDs remain.
- 119/119 candidates now have nonempty address fields, **but address accuracy is unverified**.
- 28 historical CU codes remain; all 28 match entries in saved `cu_stock_state.json`.
- 91 codes remain unresolved.
- All 119 retain barcode `8800286275732` and `NOT_QUERIED` status.
- The priority CSV generated before this backfill requires refresh: six `P2_CODE_KNOWN_ADDRESS_MISSING` entries should move to an address-present-but-unverified review category, rather than being treated as missing.
