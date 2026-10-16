# CU / 이마트24 운영 전환 — 실행 Runbook (배포 승인 전)

**현재 판정: NO-GO.** 이 문서는 승인 후 운영자가 실행할 절차다. 현재 운영 중지, 운영 파일 백업, 상태 이전, 병합, 실제 API·텔레그램 호출은 **수행하지 않았다**. GS25 및 PR #1, Draft PR #2는 대상이 아니다.

## 0. 읽기 전용 기준선
- Repo: `Koyowon/pokemon-stock-alert`
- 확인된 main: `08849cf0214ae7264f25aed5f3c17885e64a9ecd` (반드시 실행 직전에 다시 확인)
- CU `cu_stock_state.json`: Git blob `2dbb1c0abd9adcbf613d05711c0b066a79dcdd20` (164 stores, `alerted=true` 0, outbox 없음)
- 이마트24 `state.json`: Git blob `53941d3e6dcfbc83270a715652e6bae5a6af0dc0` (103 stock keys, outbox 없음)
- 이마트24 `stores.json`: Git blob `8e3940981f394cc0d0dc3213840116514fe997e7` (114 cached stores)
- CU `.github/workflows/cu-stock-monitor.yml`: Git blob `9fcc1c923ad335bde791cbc512242e1b2f303708`
- 이마트24 `.github/workflows/stock-monitor.yml`: Git blob `05ecbbc78bb03311a69895bca775f5651422569d`
- Git blob SHA는 원본 SHA-256이 아니다. 원본 파일 SHA-256은 **백업 실행 시 별도로 계산**한다. 이 문서 작성 시 실제 백업은 생성하지 않았다.

## 1. 승인 전 읽기 전용 권한 점검
저장소 소유자가 GitHub Settings → Actions → General → Workflow permissions에서 기본 `GITHUB_TOKEN`의 Contents write 가능 여부를 확인한다. Actions workflow job의 `permissions: contents: write`가 실제로 허용되는지도 확인한다. Settings → Rules → Rulesets / Branches → Branch protection에서 main 보호 및 신규 `stock-state-cu-emart24` 대상 규칙과 Actions push 허용 범위를 확인한다. 현재 main `protected=true`만 확인됐으며 보호 상세 API는 403, Actions 권한 API는 접근 불가였다. **쓰기 권한이 있다고 추정하지 않는다.**

읽기 전용 확인 명령 (GitHub CLI, 소유자 권한으로 실행):
```bash
gh api repos/Koyowon/pokemon-stock-alert/branches/main --jq '{sha:.commit.sha,protected:.protected}'
gh api repos/Koyowon/pokemon-stock-alert/actions/permissions/workflow
gh api repos/Koyowon/pokemon-stock-alert/rules/branches/main
gh api repos/Koyowon/pokemon-stock-alert/branches/main/protection
gh api repos/Koyowon/pokemon-stock-alert/branches/stock-state-cu-emart24
```
403/404는 자동 통과가 아니다. 새 상태 브랜치가 아직 없으므로 마지막 명령은 현재 404가 예상된다.

## 2. 승인된 유지보수 창에서만: 동결 → 원본 백업
1. CU와 이마트24의 기존 스케줄만 중지하고 in-flight job 종료를 확인한다. GS25는 유지한다.
2. 아래 명령의 `CURRENT`가 승인받은 기준 커밋과 다르면 즉시 중단하고 다시 검토한다.
3. 별도의 접근 제한된 로컬 디렉터리에 다섯 파일의 원본 바이트와 manifest를 저장한다. 백업 파일은 Git에 커밋하지 않는다.

```bash
set -euo pipefail
REPO="Koyowon/pokemon-stock-alert"
EXPECTED="08849cf0214ae7264f25aed5f3c17885e64a9ecd"
CURRENT="$(gh api "repos/$REPO/branches/main" --jq .commit.sha)"
test "$CURRENT" = "$EXPECTED" || { echo "STOP: main drift"; exit 1; }
git clone --filter=blob:none "https://github.com/$REPO.git" /tmp/pokemon-stock-cutover-readonly
cd /tmp/pokemon-stock-cutover-readonly
git fetch origin "$EXPECTED"
python cu_emart24_raw_backup.py backup --repo . --commit "$EXPECTED" --out "$HOME/cu-emart24-backup-$EXPECTED"
python cu_emart24_raw_backup.py verify --repo . --out "$HOME/cu-emart24-backup-$EXPECTED"
```
**주의:** `cu_emart24_raw_backup.py`는 격리 브랜치의 파일이다. 위 clone은 기본 main만 checkout하므로 실행 전에 별도로 검증된 격리 브랜치의 스크립트를 로컬 경로로 확보하거나 `git show validation/...:cu_emart24_raw_backup.py`로 안전하게 추출해야 한다. GitHub에 직접 푸시하거나 원본 파일을 덮어쓰지 않는다. 원본 복구 검증은 disposable clone에서 백업 파일과 pinned commit의 원본을 바이트 단위로 비교한다.

## 3. 최초 알림 억제·중복 방지
- CU `alerted` 및 `stock`, 이마트24 모든 flat stock key/value, stores cache를 그대로 유지한다. 기존 outbox가 없을 때만 빈 `pending_alerts`와 `alert_sequence=0`을 생성한다.
- 기존 양수 재고를 최초 스캔에서 새 입고로 판단하여 알림을 보내지 않는지 **실제 코드 경로에 대한 모의 API 테스트**로 확인한다. 확인 전 dispatch 비활성화.
- 과거 텔레그램 발송 기록은 재고 값과 `alerted`로 복원 불가. 소유자가 최초 스캔 알림 억제 정책을 명시적으로 승인해야 한다.
- 알림은 remote claim commit/verify 이후에만 보낸다. `claimed`/ `send_unknown`는 자동 재시도하지 않고 감사·수동 확인한다.
- 실제 Telegram 전송과 outcome push 사이에 장애가 나면 정확히 한 번 전달은 보장할 수 없다.

## 4. 별도 승인 후에만: 상태 이전과 워크플로 교체
1. 권한·보호·비밀값 범위·동시성 확인, 원본 SHA 및 백업 복구 확인.
2. `stock-state-cu-emart24` 생성 및 백업 기준의 세 상태 파일만 이전; Git blob과 SHA256 대조.
3. CU·이마트24 워크플로 교체안 및 관련 모듈 변경 diff를 소유자가 검토한다. 현재 후보는 `if: false`이므로 그대로 배포하면 동작하지 않는다. 운영 스케줄은 이전·승인 후에만 활성화.
4. 별도 승인받은 실제 재고 API 및 Telegram pilot을 실행하고 claim/outcome 감사.

## 5. 중단 및 롤백
즉시 중단: source SHA drift, blob/checksum mismatch, 백업 복원 실패, 권한/규칙 확인 실패, 기존 작업 미종료, outbox 재초기화 시도, 첫 스캔 중복 알림, CAS 실패, Telegram 결과 불명확.
롤백은 신규 CU·이마트24 작업 중지 → drain → 최신 상태/claim 백업 → 미확정 발송 수동 확인 → **소유자 승인 후에만** 기존 두 workflow 복구. GS25와 main의 다른 파일을 되돌리지 않으며 state branch 강제 푸시 및 claimed 알림 자동 재발송 금지.

## 6. 오프라인 검증
`cu_emart24_raw_backup.py`는 pinned Git commit의 다섯 파일을 원본 바이트로 로컬 백업하고 Git blob SHA와 SHA256을 기록하며 원본과 재비교한다. `tests/test_raw_backup.py`는 가상 Git 결과로 원본 보존·손상 탐지·중복 경로 거부를 검증한다. 실제 운영 데이터 export는 아직 하지 않았다.

**NO-GO 유지:** 소유자의 유지보수 창 승인, 실백업, 쓰기 권한 확인, 운영 상태 이전, 실제 pilot 승인 전에는 배포하지 않는다.
