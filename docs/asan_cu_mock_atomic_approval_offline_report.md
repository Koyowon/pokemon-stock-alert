# 아산 CU 승인 ID 동시 재사용·증거 변경·권한 취소 오프라인 검증

브랜치: `permission-test-20261013-cu`. 대상: ASAN-CU-083, ASAN-CU-092, ASAN-CU-100.

## 추가 파일
- `tests/cu_mock_atomic_approval_store.py`: 기존 `cu_hardened_approval_policy.assess`를 호출하는 메모리 전용 `Lock` 기반 래퍼. 동일 프로세스 내 승인 ID 조회 및 소비를 임계구역으로 묶음. 승인자 취소 목록도 동일 잠금 아래 확인.
- `tests/test_cu_mock_atomic_approval_store.py`: 10개 합성 단위 테스트. 외부 네트워크·인증·영속 저장·운영 코드 호출 없음.

## 검증 결과

동일 정책 로직을 재현한 격리 Python 사본에서 **10 tests, OK** (실패 0, 오류 0). GitHub에 커밋된 두 파일의 직접 실행이 아닌 동등 로직 재현 테스트이므로 구분함.

- 동일 승인 ID 8개 동시 요청: 한 건 `APPROVED_FOR_REVIEW_ONLY`, 일곱 건 `APPROVAL_REPLAY`.
- 증거 해시 변경: `EVIDENCE_CHANGED_OR_UNBOUND`, 승인 ID 소비 없음. 이후 원본 증거에 대한 첫 승인 가능.
- 승인자 취소 후 새 승인 ID 제출: `REVIEWER_REVOKED`로 보류. 이미 반환된 과거 결과는 소급 삭제하지 않음.
- 세 점포 개별 승인 ID 정상 처리, 상충 증거 우선 거부, 만료 승인 거부, `production_activation=False`, `same_location_confirmed=False` 확인.

## 제한 및 잔여 위험

1. 단일 Python 프로세스의 `Lock`만 사용함. 프로세스 간 동시성·재시작 후 승인 재사용·분산 환경 원자성은 보장하지 않음.
2. 취소 목록과 사용 이력은 메모리에서만 유지되며 프로세스 재시작 시 소멸.
3. 승인자 목록과 취소 이벤트의 진위는 외부에서 검증하지 않음. 신뢰된 테스트용 승인자 목록과 가짜 시계만 사용.
4. `APPROVED_FOR_REVIEW_ONLY`는 운영 승인이나 실제 점포 위치 동일성 확정이 아님.
5. 취소 시 이미 반환된 결과는 자동 철회되지 않음. 실제 시스템은 매 사용 시 재검증과 감사 기록이 필요함.
6. 향후 운영 연동 시 실제 인증·원자적 영속 저장·권한 취소 배포·재검증 경계를 별도로 설계해야 함. 이 작업에서는 구현하지 않음.

## 안전 범위

기존 운영 코드·상태 파일·레지스트리·기존 정책 파일 및 `main` 브랜치 수정 없음. CU API, Telegram, GitHub Actions 호출 없음.
