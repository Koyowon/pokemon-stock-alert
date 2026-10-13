# CU 원자적 바인딩 게이트웨이: 오프라인 설계 및 검증

대상 브랜치: `permission-test-20261013-cu`.

## 신규 파일
- `tests/cu_atomic_binding_gateway.py`: 기존 게이트웨이를 수정하지 않는 별도 합성 프로토타입
- `tests/test_cu_atomic_binding_gateway.py`: 8개 단위 테스트(4개 경쟁 조건은 각각 2개 subTest에서 검사)

## 설계
- 단일 `threading.RLock`으로 바인딩의 연결 상태, 초기화, 식별자, 세대, 정확한 저장소 객체 참조 확인부터 `SharedMemoryApprovalLedger.review_and_consume` 호출까지 직렬화한다.
- 바인딩 변경은 반드시 `mutate()`를 통과하여 **같은 잠금**을 획득한다. 객체 필드를 직접 바꾸거나 잠금을 우회하는 비협조적 변경은 방어하지 못한다.
- 검토 전 변경된 저장소/ready/세대/식별자는 `HOLD_UNVERIFIED`. 검토가 잠금을 먼저 얻은 경우 검토 전용 승인 완료 후 변경이 적용되며, 그 이후의 검토는 보류한다. 이것은 선형화 순서의 차이로서 검증-소비 간 TOCTOU 취약점이 아니다.
- `_before_consume`는 테스트 전용 동기화 후크로 잠금 내부에서 호출한다. 외부 사용자 입력이나 운영 콜백으로 사용하면 안 된다.
- 기존 증거 해시·상충 근거·재사용 차단은 기존 오프라인 공유 저장소의 정책을 그대로 호출한다.

## 검증
격리된 Python 로컬 환경에서 실제 신규 테스트 소스 및 동일한 신규 프로토타입 소스와 기존 의존성 사본으로 `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest -v test_cu_atomic_binding_gateway` 실행.

**결과: 8 tests / 8 passed / 0 failures / 0 errors**. 각 4개 변경 유형을 검토 시작 전과 검토 도중의 결정적 스레드 interleaving으로 검증. 검토 도중에는 변경 요청이 잠금에 의해 대기하며, 완료 후 후속 요청은 보류된다.

## 안전성 범위
합성 데이터와 가짜 시계만 사용. 실제 DB, 네트워크, 영속 저장, CU API, 텔레그램, GitHub Actions 호출 없음. 테스트용 승인자는 실제 인증이 아니며, 검토 전용 상태만 허용되고 `production_activation=False`, `same_location_confirmed=False`. 동일 프로세스·협조적 API 사용자만 보장. 실제 프로세스 재시작/다중 프로세스·저장소 자체 장애/외부 변경·서명·권한 취소의 영속성은 해결하지 않는다.

기존 정책·게이트웨이·공유 저장소·운영 코드·상태 파일·레지스트리 및 main 브랜치 변경 없음.
