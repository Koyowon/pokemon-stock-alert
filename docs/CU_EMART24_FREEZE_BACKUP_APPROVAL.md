# CU·이마트24 동결·백업 승인 준비 — 최종 절차

**현재 상태: NO-GO / 실행 전 승인 대기.** 이 문서는 실제 동결·백업·상태 이전을 수행하지 않는다. `main`, GS25, PR #1, Draft PR #2, 운영 워크플로 및 운영 상태 파일 변경 금지.

## 1. 최신 읽기 전용 관찰
- main: `ef873241199733afed54975e27c0b454e00d6ad3` (보호 활성). 이는 과거 기준 `08849cf0...`, 이후 관찰 `78fafed9...`에서 다시 변경된 것이다. **고정된 커밋을 영구 기준으로 사용하지 말 것.**
- CU `cu_stock_state.json` Git blob `8736cbd47da11a84b5001a07ddd0949d44dc4ed3`: 165 stores.
- 이마트24 `state.json` Git blob `53941d3e6dcfbc83270a715652e6bae5a6af0dc0`.
- 이마트24 `stores.json` Git blob `8e3940981f394cc0d0dc3213840116514fe997e7`: 114 stores.
- CU `.github/workflows/cu-stock-monitor.yml` blob `9fcc1c923ad335bde791cbc512242e1b2f303708`.
- 이마트24 `.github/workflows/stock-monitor.yml` blob `05ecbbc78bb03311a69895bca775f5651422569d`.
- 전용 `stock-state-cu-emart24` branch 없음(404). Branch protection details API 403, Actions permission endpoint unavailable. No write privilege verified.

## 2. 승인 전 안전조건
운영자에게 다음 작업을 별도 승인받아야 한다: **CU·이마트24 두 워크플로만 비활성화**(schedule뿐 아니라 workflow_dispatch도 차단), 이미 시작된 작업의 완료 또는 취소, raw-byte backup, disposable restore. GS25/Pages/기타 워크플로는 절대 비활성화하지 않는다.

GitHub CLI를 소유자 권한으로 사용해 읽기 전용 점검:
```bash
gh api repos/Koyowon/pokemon-stock-alert/actions/permissions/workflow
gh api repos/Koyowon/pokemon-stock-alert/branches/main/protection
gh api repos/Koyowon/pokemon-stock-alert/rules/branches/main
gh api repos/Koyowon/pokemon-stock-alert/branches/main --jq '{sha:.commit.sha,protected:.protected}'
gh run list -R Koyowon/pokemon-stock-alert --workflow cu-stock-monitor.yml --limit 100
gh run list -R Koyowon/pokemon-stock-alert --workflow stock-monitor.yml --limit 100
```
403/404/unknown = NO-GO. Check GitHub Settings → Actions → General and Settings → Rules/Branches. Existing workflows declare `contents: write` but this does not prove token can push to protected branches.

## 3. 승인 후 실제 동결 순서 (NOT EXECUTED)
1. Owner confirms maintenance window and two workflow file identities. Use GitHub Actions workflow disable controls for **only** `cu-stock-monitor.yml` and `stock-monitor.yml`. Disabling prevents new schedule/manual workflow_dispatch runs; **it does not terminate existing jobs**.
2. Immediately query all in-progress/queued runs for each target workflow; drain or, if separately approved, cancel. Poll until both have zero active runs. Keep GS25 active.
3. Double-check both workflows remain disabled and recheck for new queued/in-progress jobs; if any appear, STOP. Maintain freeze until cutover or authorized rollback.
4. Pin latest main SHA **after** both jobs drained, not before. Verify five file blob SHAs against pinned commit. If main changes due to GS25, re-pin and re-verify the five file blobs. If any target blob changed, stop/rebaseline.
5. Owner-approved raw-byte backups and SHA256 of all five files. Use the tested `cu_emart24_raw_backup.py` from isolated branch; save outside Git, with restricted access. Restore and verify byte-for-byte in disposable clone. Git blob SHA != raw SHA256.
6. Confirm effective token write rights, state branch rules, dispatch-only Telegram secret scope, concurrency, and owner-approved first-scan no-replay policy. Any unverified item => NO-GO.

**Commands for an authorized operator** (NOT RUN):
```bash
# Step 1: ONLY after explicit owner approval:
gh workflow disable cu-stock-monitor.yml -R Koyowon/pokemon-stock-alert
gh workflow disable stock-monitor.yml -R Koyowon/pokemon-stock-alert

# Step 2: read-only drain observation; repeat until no queued/in_progress runs:
gh run list -R Koyowon/pokemon-stock-alert --workflow cu-stock-monitor.yml --limit 100 --json databaseId,status,workflowName
gh run list -R Koyowon/pokemon-stock-alert --workflow stock-monitor.yml --limit 100 --json databaseId,status,workflowName

# Step 3: pin main after drain, capture five blobs:
CURRENT="$(gh api repos/Koyowon/pokemon-stock-alert/branches/main --jq .commit.sha)"
printf 'Pinned main: %s\n' "$CURRENT"
for f in cu_stock_state.json state.json stores.json .github/workflows/cu-stock-monitor.yml .github/workflows/stock-monitor.yml; do
  gh api "repos/Koyowon/pokemon-stock-alert/contents/$f?ref=$CURRENT" --jq '.sha'
done

# Step 4: use documented raw backup and restore verification commands
# from docs/CU_EMART24_CUTOVER_RUNBOOK.md, replacing old EXPECTED with CURRENT.
```
**Operational caveat:** Workflow disable permissions and branch protection must be checked before use; disabling existing workflows is a production change and requires explicit approval. GitHub Actions runs can be queued with delays; check each workflow's active run list and disabled state again immediately before pinning.

## 4. 최초 알림, 중단 및 롤백
- CU existing `stock` and `alerted`, emart24 flat quantities, stores cache unchanged. No initial replay; create empty outbox only.
- First-scan dry-run must prove existing positive stock is not sent as a new arrival. Until approved, dispatch disabled. `claimed` and `send_unknown` never auto-retry.
- STOP: any active CU/emart24 job, disabled workflow unexpectedly re-enabled, target blob drift, missing backup/restore proof, unknown write permissions/rules, first-scan duplicate risk.
- On STOP **before migration**: preserve backup and freeze; owner separately approves whether to re-enable only original CU/emart24 workflows.
- On STOP **after migration**: preserve latest state and claims, reconcile ambiguous Telegram outcomes, never force-push/replay; rollback workflows only after owner approval. Do not touch GS25 or unrelated main files.

## 5. 검증 및 변경 범위
`cu_emart24_freeze_evidence.py`: explicit fail-closed freeze gate; `tests/test_freeze_evidence.py`: queued/running target jobs, GS25 exclusion, backup and manual-dispatch approval checks. All tests offline, no production writes. No actual freeze or backup performed.
