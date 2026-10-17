# 운영 파일 안전 정리 — 2026-10-17

기준 main: eb357be43045af26319dbbeba07231e0a9f6cd7d
승인 브랜치: chore/archive-retired-tools-20261017
상태: 브랜치 정리 및 오프라인 검증 완료, main 반영 대기.

## 변경

12개 원래 경로를 archive/retired_20261017/ 아래로 옮긴다. 영구 삭제하거나 Git 이력을 정리하지 않는다. 이 작업은 루트와 Actions 목록을 정돈하는 작업이며 재고 조회시간이나 저장소 용량의 큰 감소를 의미하지 않는다.

- 완료된 설치/통합 스크립트 3개와 관련 수동 워크플로 4개
- 현재 CU·이마트24·GS25 정기 운영과 연결되지 않은 세븐일레븐 진단 스크립트 2개와 수동 워크플로 2개
- 현재 운영 코드가 읽지 않는 초기 루트 config.json 1개

이전 README는 보관 사본으로 남기고 루트 README를 현재 운영 구성으로 고친다. 기존 문서의 '재고 연동 없음', '10분 주기', '초기 ZIP 업로드' 안내는 현재 코드와 맞지 않았다.

## 이동 목록

| 원래 경로 | 보관 경로 |
|---|---|
| install_stock_change_alerts.py | archive/retired_20261017/install_stock_change_alerts.py |
| install_unified_controls.py | archive/retired_20261017/install_unified_controls.py |
| integrate_gs25_guard.py | archive/retired_20261017/integrate_gs25_guard.py |
| .github/workflows/install-stock-change-alerts.yml | archive/retired_20261017/.github/workflows/install-stock-change-alerts.yml |
| .github/workflows/install-unified-controls.yml | archive/retired_20261017/.github/workflows/install-unified-controls.yml |
| .github/workflows/gs25-guard-deploy.yml | archive/retired_20261017/.github/workflows/gs25-guard-deploy.yml |
| .github/workflows/gs25-guard-integration-test.yml | archive/retired_20261017/.github/workflows/gs25-guard-integration-test.yml |
| seveneleven_diagnostic.py | archive/retired_20261017/seveneleven_diagnostic.py |
| seveneleven_relay_diagnostic.py | archive/retired_20261017/seveneleven_relay_diagnostic.py |
| .github/workflows/seveneleven-diagnostic.yml | archive/retired_20261017/.github/workflows/seveneleven-diagnostic.yml |
| .github/workflows/seveneleven-relay-diagnostic.yml | archive/retired_20261017/.github/workflows/seveneleven-relay-diagnostic.yml |
| config.json | archive/retired_20261017/config.json |

원본 SHA와 사유는 archive/retired_20261017/MANIFEST.json에 기록한다. README 원본은 INITIAL_README.md에 별도 보관한다. 보관된 YAML은 루트 .github/workflows 밖으로 이동하므로 Actions에서 직접 실행할 수 없다. 보관 스크립트는 상대 경로를 재작성하지 않은 역사 자료다. 복원 시 원래 경로로 돌리고 최신 운영 코드와 호환성을 재검토해야 한다.

## 유지한 것

- 이마트24·CU·GS25·CU 상품등록·Telegram 제어의 정기 워크플로 5개와 실제 모니터·공통 모듈
- 현재 지역/체인 설정, 점포·후보 등록 자료, 재고/알림 상태, Telegram 커서
- GitHub Pages의 docs/index.html·docs/stock/index.html과 웹 화면의 데이터 경로 4개
- 회귀 테스트와 그 fixture, 나머지 수동 진단 워크플로 38개
- 공식 점포코드 검증 근거·감사 보고서와 초기 GS25 provider 계약 테스트

남은 수동 진단 파일은 실제 수동 워크플로에서 참조되거나 회귀/검증 이력이 있어 일괄 삭제하지 않았다. 세븐일레븐 API를 비교하는 다른 비교 도구는 그 도구의 사용 범위를 임의로 변경하지 않기 위해 유지했다.

## 근거

완료된 설치 스크립트가 적용하던 공통 지역 제어, 재고 변동 알림, GS25 아산 guard가 현재 운영 코드에 이미 포함되어 있음을 확인했다. 이동하는 Python 파일에 대한 운영 코드/남은 워크플로의 참조가 없음을 확인했다. 초기 루트 config.json을 읽는 운영 진입점이 없고 실제 설정은 region_settings.json·unified_control.json·gs25_independent/config.json임을 대조했다.

## 검증

- 기준 main 134개 파일 모두 로컬 전달 후 Git blob SHA-1 일치 확인.
- 이동 12개는 보관 경로에서도 원래 blob SHA를 유지. README 원본 사본도 동일 SHA 유지.
- README와 이동 대상 외 기존 121개 파일은 바이트 단위 해시 동일.
- 남은 43개 workflow의 YAML과 명시된 Python 파일 경로 검사. unittest discover의 -s 검색 디렉터리도 고려.
- 이동 workflow 6개가 모두 workflow_dispatch 전용이고 정기 schedule이 없음을 확인. 정기 workflow 5개는 원본 바이트 유지.
- 정기 진입점의 정적 Python import와 존재하는 리터럴 데이터 경로를 따라 23개 운영 의존 파일을 확인. 이동 대상과 겹치지 않음. 동적 외부 도구의 임의 참조까지 보장하는 검사는 아님.
- 남은 실행 소스/YAML/HTML의 이동된 스크립트 이름 참조 0개. 웹 화면이 읽는 저장 데이터 경로 4개 유지.
- 기존 최적화/알림 상태 보존/GS25 guard 오프라인 회귀 테스트 38개 통과.

재현 회귀 명령:

```sh
python -m unittest -v test_monitor_optimization test_gs25_guard_integration gs25_independent.test_gs25_asan_guard
```

정적 검사 결과는 docs/OPERATIONS_CLEANUP_CHECK_20261017.json에 기록한다. 검증에서 실제 재고 API·Telegram·Actions를 호출하지 않았고 운영 상태를 저장하지 않았다. GitHub 파일 조회와 브랜치 저장만 수행했다.

## 승인 범위와 복원

이 브랜치의 이동·보관 목록과 README 정리만 main에 반영하는 승인을 요청한다. 승인 후 최신 main의 변경사항과 다시 대조해 상태 데이터·다른 작업을 덮어쓰지 않는다. Git branch/commit이 원본을 유지하므로 불필요한 영구 삭제는 없다. 복원은 MANIFEST.json의 from/to 및 sha를 기준으로 개별 수행하며 기존 파일을 자동 덮어쓰거나 오래된 설치 스크립트를 실행하지 않는다.
