# 아산 CU 공유 메모리 승인 이력·취소 저장소 오프라인 설계 및 검증

대상 브랜치: `permission-test-20261013-cu`. 대상 ASAN-CU-083/092/100. 합성 데이터만 사용.

## 설계

- 신규 `tests/cu_shared_memory_approval_ledger.py`: 하나의 `SharedMemoryApprovalLedger` 객체를 여러 `MockReviewClient`가 공유한다.
- 같은 `threading.Lock` 아래에서 취소된 승인자 검사, 기존 `cu_hardened_approval_policy.assess()` 평가, 승인 ID 소비를 연속 처리한다.
- `revoke()`도 동일 잠금 사용. 취소 후 새 요청은 `REVIEWER_REVOKED`로 보류.
- 증거 SHA-256 결속, 점포 코드, 만료, 상충 증거는 기존 강화 정책 함수가 검사. 실패 요청은 승인 ID를 소비하지 않음.
- 승인 성공은 `APPROVED_FOR_REVIEW_ONLY`일 뿐이며 `production_activation=False`, `same_location_confirmed=False`를 유지.
- 승인자 목록·시계·증거는 전부 합성 입력. 외부 인증이나 공식 주소 확인을 하지 않는다.

## 검증

신규 `tests/test_cu_shared_memory_approval_ledger.py`는 11개 테스트를 포함한다. 동일한 핵심 로직을 재현한 격리 Python 사본에서 11개 테스트 모두 통과(0 실패, 0 오류). **GitHub에 커밋된 파일 자체의 직접 실행은 아님.** 확인 항목: 공유 이력, 8개 동시 요청(1 통과/7 재사용 거부), 권한 취소 전파, 취소 후 새 승인 ID 차단, 증거 변경, 상충 증거, 만료, 세 점포 개별 승인, 별도 저장소 간 이력 격리, 운영 비활성, 잘못된 저장소 타입.

## 한계와 남은 위험

- **프로세스 재시작과 여러 프로세스 간 이력 보존 문제는 해결하지 않는다.** 모든 클라이언트가 같은 Python 객체를 참조할 때만 동작한다.
- 별도 `SharedMemoryApprovalLedger` 인스턴스를 만들면 사용 이력과 취소 기록은 공유되지 않는다.
- 실제 DB, IPC, 네트워크, 영속 저장, 외부 인증, 서명 검증, 운영 활성화는 전혀 구현하지 않았다.
- 증거의 `source_verified=True` 등은 호출자가 설정한 합성 플래그이며 독립적 진위 검증이 아니다.
- 원자성은 단일 프로세스 공유 객체와 그 잠금 범위에서만 유효하다. 다중 프로세스·재시작 안전성을 주장해서는 안 된다.

## 변경 금지 준수

신규 프로토타입·테스트·이 문서만 작업 브랜치에 추가. 기존 정책·운영 코드·상태 파일·레지스트리·main 브랜치 변경 없음. CU API, Telegram, GitHub Actions 실행 없음.
