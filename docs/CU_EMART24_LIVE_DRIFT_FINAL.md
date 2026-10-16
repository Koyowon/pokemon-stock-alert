# CU·이마트24 최종 읽기 전용 권한·드리프트 점검 (2026-10-16)

## 판정: NO-GO — 기존 백업 기준선이 변경됨
- 기존 Runbook의 main commit `08849cf0214ae7264f25aed5f3c17885e64a9ecd` → 현재 읽기 전용 main `78fafed9ddd84ca1a8aafc3b16158b636c86d40a`. **승인 전 기준선을 다시 고정해야 함.**
- CU `cu_stock_state.json` blob `2dbb1c0abd9adcbf613d05711c0b066a79dcdd20` → `8736cbd47da11a84b5001a07ddd0949d44dc4ed3`; 164 → 165 stores, alerted=true 0, outbox 없음.
- 이마트24 `state.json` blob `53941d3e6dcfbc83270a715652e6bae5a6af0dc0` (103 keys), `stores.json` blob `8e3940981f394cc0d0dc3213840116514fe997e7` (114 cached stores): unchanged.
- CU workflow blob `9fcc1c923ad335bde791cbc512242e1b2f303708`, emart24 workflow blob `05ecbbc78bb03311a69895bca775f5651422569d`: unchanged. Both existing schedules and direct Telegram dispatch remain in place.
- Main protected=true, but branch protection details API 403; Actions workflow permissions API unavailable. **Do not assume write access.**
- Dedicated `stock-state-cu-emart24` branch: 404, absent.
- Draft PR #2 remains draft at `84a4adcdb14a205e1ac0d1244ac363bf76dcd93e`.

## Isolated change
- `cu_emart24_live_drift_gate.py`: pinned main SHA and five file blobs fail-closed when drift detected, or write rights, rules, real backups and first-alert policy not verified.
- `tests/test_live_drift_gate.py`: four synthetic tests for actual observed drift, missing permissions and first-alert approval.
- Offline Actions run 38830902704: 39 tests passed; no operating files or workflows modified.

## Required actions (none performed)
1. **Rebaseline** current main commit and all five blobs at approved freeze time; reject changes after freeze. Existing Runbook's SHA cannot be reused blindly.
2. Owner manually verifies Actions `GITHUB_TOKEN` write capability, detailed main/state branch rules and dispatcher secrets scope via GitHub Settings; available integration could not read those endpoints.
3. Owner authorizes CU/emart24-only pause and drain, raw-byte backups with SHA256 and disposable restore verification. GS25 unaffected.
4. Owner approves first-scan suppression of legacy positive stock, unknown delivery handling and no replay of `claimed`/`send_unknown`.
5. Separately approve state branch creation and migration; review real replacement workflow diff and explicitly authorize any live inventory/Telegram pilot. Candidate jobs remain disabled, not live-ready.

**NO-GO persists** until all preconditions are met. No merge, deployment, API/Telegram call, state migration or production file writes performed.
