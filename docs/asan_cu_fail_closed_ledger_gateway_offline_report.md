# CU 공유 메모리 승인 저장소 장애 시 fail-closed 오프라인 설계 및 검증

대상 브랜치: `permission-test-20261013-cu`. 신규 파일:
- `tests/cu_fail_closed_ledger_gateway.py`
- `tests/test_cu_fail_closed_ledger_gateway.py`

## 정책

새로운 오프라인 게이트웨이는 `FakeLedgerBinding`의 `ready`, `initialized`, `identity`, `generation`과 생성 당시 저장소 객체의 동일성(`is`)을 검사한다.

1. 연결 불가/바인딩 제거/잘못된 저장소: `LEDGER_UNAVAILABLE`
2. 초기화 미완료: `LEDGER_UNINITIALIZED`
3. 저장소 ID 불일치 또는 빈 기대 ID: `LEDGER_IDENTITY_MISMATCH`
4. 세대 ID 불일치, 빈 기대 세대, 동일 문자열의 새 저장소 객체 교체: `LEDGER_GENERATION_MISMATCH`
5. 통과한 경우에만 기존 `SharedMemoryApprovalLedger.review_and_consume`에 위임.

모든 장애 시 `state=HOLD_UNVERIFIED`, `production_activation=False`, `same_location_confirmed=False`, `consume_approval_id=None` 반환. 검토 전용 승인 상태가 실제 운영 승인이 아님을 유지.

## 오프라인 검증

합성 시계: 2026-10-13 01:00 UTC. 점포 ASAN-CU-083 등은 실제 위치/재고 조회 없이 코드 상의 가상 증거만 사용.

검증 시나리오 15개: 정상 게이트, 연결 불가, 바인딩 제거, 저장소 제거, 초기화 미완료, ID 불일치/빈 ID, 세대 불일치, 동일 레이블 새 객체 교체, 승인 이후 ID 변경, 동일 바인딩 재연결, 장애 시 미소비, 승인 재사용, 증거 변경, 상충 증거.

**검증 결과:** 15 tests, OK, 0 failures, 0 errors. GitHub에 커밋된 프로토타입과 동일한 핵심 로직을 재현한 격리 Python 테스트를 실행했으며, 커밋된 파일 자체를 직접 내려받아 실행한 것은 아님.

## 한계

- `ready`, `identity`, `generation`은 모두 신뢰되지 않은 **합성 필드**다. 실제 저장소의 인증·신선도·네트워크 헬스 체크를 보장하지 않는다.
- 동일 프로세스의 동일 객체를 고정하는 방식이므로 재시작 후 재결속/복수 프로세스 공유 저장소를 구현하지 않는다.
- 기존 바인딩의 `ready`를 다시 `True`로 바꾸면 동일 객체에서 재검토 가능하지만, 실제 장애 복구와 데이터 정합성 검증을 대체하지 않는다.
- `review_and_consume` 호출 직후의 동시 바인딩 교체까지 원자적으로 차단하는 설계는 아니다. 운영 환경에는 검증된 세대/세션 토큰과 저장소 측 원자적 검증이 필요하다.
- 실제 DB, 네트워크, 영속 저장, 외부 인증, CU API, Telegram, GitHub Actions 사용 없음.
- 기존 정책·운영 코드·상태 파일·레지스트리·main 브랜치 수정 없음.
