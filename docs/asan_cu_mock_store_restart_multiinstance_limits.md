# CU 모의 승인 저장소: 재시작·복수 인스턴스 위험 재현

작업 브랜치: `permission-test-20261013-cu`. 범위: `ASAN-CU-083`, `ASAN-CU-092`, `ASAN-CU-100` 합성 승인 기록.

## 사용한 기존 소스

- `tests/cu_mock_atomic_approval_store.py`, SHA `8be1cd311b9b3901d60ebf9f95b79ba38102c58b`
- `tests/cu_hardened_approval_policy.py`, SHA `5e44ec7bfcce6fdb8b3d7c48d04f326db3bfb9ae`

기존 모의 저장소의 `_consumed` 및 `_revoked_reviewers`는 `__init__`에서 생성되는 **인스턴스별 집합**이고 `Lock`도 인스턴스별이다. 외부 영속 저장소·공유 메모리·분산 잠금은 없다.

## 신규 테스트

`tests/test_cu_mock_store_restart_multiinstance_limits.py` — 총 8개:
- 4개 정상 통과: 같은 인스턴스 승인 ID 재사용 차단, 같은 인스턴스 권한 취소 적용, 새 인스턴스 사용 이력 초기화 확인, 운영 활성화/실제 장소 확정 플래그 False 확인.
- 4개 `@unittest.expectedFailure`: 재시작 모의 시 승인 재사용 차단 유지, 재시작 모의 시 권한 취소 유지, 별도 인스턴스 승인 재사용 차단, 별도 인스턴스 권한 취소 전파.

## 결과

격리된 Python 환경에서 동일 핵심 로직을 재현해 실행: `Ran 8 tests`, `OK (expected failures=4)`. 예상 실패는 현재 구현의 **실제 보장 부재**를 드러내며 성공으로 해석해서는 안 된다.

**검증 한계:** 이번 실행은 GitHub에 추가된 테스트 파일 자체를 다시 다운로드해 실행한 결과가 아니라, 동일한 테스트 시나리오를 격리 사본으로 실행한 결과다. 별도 OS 프로세스나 분산 환경을 띄우지 않았으며 새 `MockApprovalStore()` 객체로 재시작/다중 인스턴스의 메모리 격리를 모의했다.

## 안전성 판단

- **확인된 한계:** 승인 사용 이력·취소 이력은 새로운 객체에 전달되지 않는다.
- **미검증:** 실제 여러 프로세스의 경쟁, 프로세스 충돌, 권한 취소의 동시성, 영속 저장소 복구.
- **필요한 향후 별도 설계:** 원자적·공유·영속 승인 ID 소비 기록, 취소 목록 공유, 승인 버전/증거 해시 결속, 동시성 실패 테스트, 복구 정책. 이번 작업에서는 구현하지 않았다.
- 모든 검토 결과의 `production_activation=False`, `same_location_confirmed=False` 유지. `APPROVED_FOR_REVIEW_ONLY`는 실제 운영 승인 아님.

## 변경 제한

별도 테스트와 이 보고서만 신규 추가. 기존 정책·운영 코드·상태 파일·레지스트리·main 브랜치 변경 없음. CU API, Telegram, GitHub Actions 호출 없음.
