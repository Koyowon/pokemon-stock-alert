# CU official-store coordinate provenance audit — 2026-10-17 (KST)

## Scope
CU official directory contains 377 verified codes and postal addresses: Namwon 20, Asan 153, Jeonju 204. The JSON directory has **zero** `lat`/`lng` or `latitude`/`longitude` fields. The baseline monitor has **19** existing probes across these three cities (Namwon 4, Asan 7, Jeonju 8), with no store-specific coordinate provenance.

## Research findings
1. CU official listing `https://cu.bgfretail.com/store/list.do?category=store` and sample official detail `https://cu.bgfretail.com/store/view.do?jumpo=04766`: attempted direct retrieval 2026-10-17; the retrieval tool could not access the pages. Thus **no latitude/longitude or code-coordinate linkage was confirmed** from official detail HTML.
2. A published, independently maintained CU network analysis describes `POST /store/list_Ajax.do` for the official web store directory and `POST /api/store` for the PocketCU store lookup. The document does not establish a stable, authenticated match from the official `jumpo` code to a lat/lng pair for these 377 stores. Its example endpoint signatures are not verified for this deployment. Source: https://github.mosekj.com/hmmhmmhm/daiso-mcp/blob/main/docs/cu-network-analysis-result.md (retrieved 2026-10-17).
3. OpenStreetMap-backed services such as Mapcarta publish coordinates for some named CU stores, but examples found were outside the target municipalities and did not include the official CU `jumpo` code. Do **not** join by name alone. Example: https://mapcarta.com/N4642358021 (retrieved 2026-10-17).

## Verified store-coordinate records
**0 records.** No source simultaneously established official code, name, address, and latitude/longitude for any of the 377 target stores. Do not invent or reuse arbitrary coordinates.

## Baseline comparison and minimum expansion
| City | Official directory | Existing coordinate probes | Additional verified coordinates | Approved additional probes |
|---|---:|---:|---:|---:|
| Namwon | 20 | 4 | 0 | 0 |
| Asan | 153 | 7 | 0 | 0 |
| Jeonju | 204 | 8 | 0 | 0 |
| **Total** | **377** | **19** | **0** | **0** |

The only evidence-backed minimal plan today is to retain all 19 existing probes and add **none**. This is *not* evidence of 377-store coverage. Store codes absent from API responses must remain UNKNOWN, never zero.

## Acceptance gates for future candidate coordinates
For each candidate, record `cu_store_code` (preserve leading zero), exact `name`, official `address`, `latitude`, `longitude`, `coordinate_source_url`, `official_detail_url`, `verified_at_kst`, `matching_evidence`, and `coordinate_system=WGS84`. Require direct source evidence linking coordinate to that exact official store code, plus consistent name and road address. Reject name-only OSM matches, geocoded guesses, uncertain projections, conflicts, stale listings, and unverifiable detail pages.

After collecting qualifying records, calculate distances to existing probes, but do not infer the API's effective radius or coverage from geometry alone. Minimize extra probes using authorized recorded API-response fixtures and an explicit request budget. No live inventory API calls, Telegram sends, or GitHub Actions runs are permitted in this stage.

## Offline validation
Local Python verified the **19 existing coordinate pairs are unique within their cities**. This check does not prove coordinate-to-store linkage or inventory coverage. Full monitor regression tests were not rerun in this step.
