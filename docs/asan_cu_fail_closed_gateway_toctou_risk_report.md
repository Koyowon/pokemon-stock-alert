# 아산 CU fail-closed 승인 게이트웨이 TOCTOU 위험 재현

- 브랜치: `permission-test-20261013-cu`
- 새 테스트: `tests/test_cu_fail_closed_gateway_toctou_races.py`
- 실행: 격리된 Python 로컬 사본에서 `python -B -m unittest -v test_cu_fail_closed_gateway_toctou_races`
- 결과: **8개 테스트 / 정상 통과 4개 / 예상 실패(expectedFailure) 4개 / 예기치 않은 실패·오류 0개**
- 실제 DB, 네트워크, 영속 저장, CU API, 텔레그램, GitHub Actions 호출 없음.

## 재현 방식

기존 `FailClosedReviewGateway.review`는 `b = self.binding`으로 바인딩 참조를 저장하고, 준비 상태·초기화·식별자·세대·저장소 객체 동일성을 순차 검사한 다음 `b.ledger.review_and_consume(...)`을 다시 호출한다.

테스트는 `FakeLedgerBinding`의 합성 하위 클래스로 `ledger` 프로퍼티 세 번째 읽기(객체 동일성 검사)를 `threading.Event`로 정지시킨다. 별도 스레드가 그 사이 상태를 바꾸고 게이트웨이가 계속 진행하도록 해 경쟁 순서를 결정적으로 고정한다. 실제 외부 장애나 프로세스 경계는 사용하지 않는다.

## 예상 실패 4건

1. 검증 후 `b.ledger` 객체 교체: 마지막 동일성 검사에서는 이전 객체가 반환되지만, 실제 호출에서는 새 객체를 사용하여 `APPROVED_FOR_REVIEW_ONLY`가 나올 수 있다.
2. 검증 후 `b.ready=False`: 준비 상태를 다시 확인하지 않고 검토 전용 상태가 나온다.
3. 검증 후 `b.generation` 변경: 세대를 다시 확인하지 않고 검토 전용 상태가 나온다.
4. 검증 후 `gateway.binding` 교체: 로컬 변수 `b`에 남은 이전 바인딩으로 검토 전용 상태가 나온다.

이는 **운영 승인이나 실제 위치 확인을 의미하지 않는다**. 모든 반환 결과의 `production_activation`과 `same_location_confirmed`는 False다.

## 통과 4건

- 변경이 없으면 정상 검토 전용 상태
- 교체된 저장소에 승인 ID가 소비되는 현상 확인
- 준비 상태 변경 후에도 운영 활성화는 False
- 검증 시작 전 준비 상태가 False면 보류

## 안전성 제안 (미구현)

- 바인딩을 외부에서 직접 변경할 수 없도록 불변 스냅샷/잠금으로 관리
- 준비 상태·세대·객체 동일성 검증과 승인 소비를 같은 동기화 경계에서 수행
- 상태 변경 및 세대 교체 시 기존 검토 세션 무효화
- 프로세스/네트워크/영속 저장을 다루는 실제 운영 보장은 별도의 인증된 공유 저장소와 원자적 트랜잭션 필요

이번 작업은 **별도 테스트와 보고서만 추가**한다. 기존 승인 정책, 게이트웨이, 공유 저장소, 운영 코드, 상태 파일, 레지스트리, `main`은 변경하지 않는다.
