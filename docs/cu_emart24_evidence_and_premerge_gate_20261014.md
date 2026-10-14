# CU 91개 증거 검토 및 이마트24 제주 오프라인 통합 게이트 (2026-10-14)

## 이번 작업
- CU 91개 미확보 점포는 기존 `docs/asan_cu_91_evidence_review_20261014.csv`에서 개별 식별자/주소/증거 필요 조건을 유지.
- 과거 저장된 아산 CU 코드 28개는 이미 모두 119개 후보에 연결되어 있어 신규 배정 가능한 미사용 저장 코드는 0개. 신규 코드 자동 배정 없음.
- 주소 충돌 검토 대상 4개 (`ASAN-CU-008`, `089`, `078`, `079`)는 병합 금지.
- `tests/offline_emart24_integration_gate.py`: Python AST로 단일 상품 바코드 및 제주 지역 선언을 정적으로 확인하고, 실제 제주 점포 시드/코드 연결이 없는 상태에서는 `can_activate_jeju=false`를 강제.
- `tests/test_offline_emart24_integration_gate.py`: 제주 지역 미지원, 제주 지역 선언만으로 활성화 금지, 추가 상품 금지 3개 검증.
- 오프라인 실행: GitHub에 기록한 코드를 격리 로컬 디렉터리에 재현하여 `python -m unittest discover -s tests -p 'test_offline*.py' -v` 실행. 이번 신규 게이트 **3 tests, OK**. 최초 테스트의 잘못된 SyntaxError 기대를 수정한 후 재실행.
- 위 실행은 신규 3개 테스트만 대상으로 하며, 전체 브랜치 12개 테스트를 실행한 결과가 아님. GitHub Actions 미실행.

## 정적 검사 한계
- AST 검사는 선언된 상품·지역만 검사하며 런타임 재고 조회 성공, 재고 알림 발송 성공, 점포 전수 등록을 증명하지 못함.
- `jeju_offline_integration_ready=false`는 의도적 차단값. 실제 검증된 제주 점포 코드, 지역 선택 로직, 시드 연결, 오프라인 mock 조회 테스트를 갖추기 전에는 해제해서는 안 됨.
- `monitor.py` 및 운영 파일은 수정하지 않았으므로 실제 이마트24 제주 감시는 미지원.
- 30주년팩 증가·감소·품절 분기는 운영 코드에서 유지됨.

## 보호 범위
`main`, GS25, CU/이마트24 운영 모니터, 상태/설정/워크플로, 외부 재고 API, Telegram 변경·실행 없음.
