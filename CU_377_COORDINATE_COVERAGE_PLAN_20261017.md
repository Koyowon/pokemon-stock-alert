# CU 377-store geographic coverage plan — 2026-10-17

## Evidence and limits
- Official directory: 377 name/address/code-verified stores (Namwon 20, Asan 153, Jeonju 204).
- **No coordinates or geocoding provenance** in the official directory. Postal addresses alone cannot safely become latitude/longitude.
- Existing monitor has 4 Namwon, 7 Asan, 8 Jeonju, 9 Jeju geographic probes (28 total). These are legacy coordinates, not independently proven to cover all official stores.
- CU inventory adapter accepts existing geographic query parameters `lat`, `lng`, `keyword`, `size`, `offset`, `storeCheck`, `format`. No supported store-code-specific inventory query is established.
- The API response cannot be assumed to contain every nearby store, and missing store codes never mean zero stock.

## Safe staged expansion
1. Obtain store-level coordinates from an authorized, verifiable source (with address, code, lat/lng, source, timestamp); do not infer coordinates from address strings or fabricate geocoding results.
2. Check city, store code, name and road-address identity; reject mismatches and duplicate/ambiguous coordinates.
3. Calculate a reproducible candidate probe set offline; use existing probes first and evaluate incremental gain only against recorded, authorized response fixtures. Do not claim a spatial radius or complete coverage without evidence.
4. Before enabling extra probes, establish a verified per-request upper bound and enforce a per-run query budget. Existing workflow timeout is 12 minutes. Current code caps query initiation at 600 seconds; each in-flight request can take up to 40 additional seconds.
5. Stage a small, explicitly approved set of additional verified coordinates, then compare observed store codes with 377-code directory; preserve unknown/missing and conflicting identities.
6. Require explicit authorization for any real API verification and later main deployment.

## Current branch behavior
- Deduplicates identical (city, latitude, longitude) probes; preserves original order.
- Uses only the existing coordinate list; **does not increase API request count** or add invented points.
- Stops initiating new probes after 600 seconds, leaving 80 seconds of the workflow's 720-second job timeout for a possible 40-second request and state processing.
- Existing inventory state, alert semantics, disabled-region settings and chain isolation remain unchanged.
- No API, Telegram, or GitHub Actions calls were performed for this plan.

## Validation
The test suite `test_cu_coverage.py` and `test_cu_monitor_integration.py` includes mocked no-network checks for identity, unknown stock, alert/state safety, duplicate coordinates and time budget. Local reconstructed-code validation is not a byte-identical execution of the remote branch; run a clean checkout of the branch in an isolated offline environment before approval.

## Source research and candidate gate (2026-10-17)
- CU's official store finder at https://cu.bgfretail.com/store/list.do?category=store supports region/name lookup and is the authoritative store identity source. Publicly accessible indexed documentation does not establish a reliable 377-store latitude/longitude export.
- Independent CU store-finder reverse-engineering describes `POST /store/list_Ajax.do` for store listings, not a verified store-coordinate feed. A third-party 2026 network analysis reports nearby-store APIs, but no 377-code coordinate mapping was verified. Neither is evidence that a coordinate belongs to a particular official store.
- Verified new coordinate records: **0 / 377**. No speculative coordinates were generated or deployed.
- `cu_coordinate_plan.py` accepts candidate coordinates only with exact official code/name/address, matching city, source URL, verification timestamp, finite numeric lat/lng in a broad South Korea sanity range, and non-duplicate probe. It performs no geocoding, API requests or file writes. This gate does not itself verify that an asserted source URL actually contains those coordinates; external provenance verification remains mandatory.
- A truly *minimum* set of added geographic probes cannot be computed from addresses alone: the API's geographic coverage radius, pagination behavior and store response sets have not been verified. Do not assume that one point per store is necessary or sufficient.
- Existing 28 coordinate probes are retained; only 19 target-region probes (Namwon 4, Asan 7, Jeonju 8) are relevant to the 377 target stores. Jeju 9 are out of scope for this registry.
- An isolated local Python run of `test_cu_coordinate_plan.py` passed 8/8 tests. The entire GitHub branch suite was not re-run in a clean checkout, and no claim of full regression pass is made.
