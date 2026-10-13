# 아산 CU 강화된 오프라인 승인 정책 — 설계 및 테스트

작업 브랜치: `permission-test-20261013-cu`. 대상: ASAN-CU-083/092/100.
기존 정책 `tests/cu_evidence_transition_policy.py`는 변경하지 않음. 별도 `tests/cu_hardened_approval_policy.py`, `tests/test_cu_hardened_approval_policy.py` 추가.

## 정책

- 신뢰된 **테스트용** 승인자 목록에서 `can_review=True`와 `cases` 범위가 일치해야 한다. 외부 인증/실제 권한 확인이 아니며 호출자가 임의 목록을 주입할 수 있다.
- 승인 `case_id`, `code`, `evidence_sha256`를 증거와 대조. 증거 JSON을 정렬/고정 구분자로 직렬화해 SHA-256 계산. 해시는 내용 변경 탐지 수단일 뿐 출처 진위·서명 보증 아님.
- `issued_at <= now < expires_at`, 명시적인 타임존, 만료 시각 > 발급 시각을 요구. `now`는 호출자 제공 모의 시각.
- `approval_id`가 외부 제공 `consumed_ids`에 있으면 재사용 거부. 이 함수는 순수 함수라 소비 기록을 **저장하지 않는다**. 실제 일회성 보장에는 원자적 영속 저장과 동시성 제어가 별도로 필요하다.
- `conflicting=True`면 최우선 거부. `conflicting=False`가 명시되고 필수 증거 플래그가 모두 True인 경우만 다음 단계 진행.
- 누락/오류/권한 부족/시간 불일치/해시 불일치/재사용은 `HOLD_UNVERIFIED`. 조건 충족 시에도 `APPROVED_FOR_REVIEW_ONLY`, `production_activation=False`, `same_location_confirmed=False`만 반환.
- 기존 JSON 상태·점포 목록·운영 모니터와 완전히 분리. 실제 점포 위치, 이전, 개명, 재고를 판단하지 않음.

## 오프라인 테스트

```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -p 'test_cu_hardened_approval_policy.py' -v
```

**결과: 20 tests, OK** (격리된 Python 로컬 사본에서 실행). 첫 실행에서 잘못된 테스트 도우미 호출로 unknown-case 테스트 1건 오류가 있었으며, 테스트 호출을 직접 `assess()`로 수정한 뒤 재실행해 20/20 통과. 정책 구현은 수정하지 않았음.

커버리지: 정상 검토 전용 상태, 승인 누락, 미등록/비활성 승인자, 점포별 범위, 점포 코드/케이스 결속, 증거 해시 변경·누락, 만료·발급 전·타임존 누락, 승인 재사용, 상충 증거 우선, 불충분 증거, 문자열형 explicit, 승인 ID 누락, 알 수 없는 케이스, 외부 소비 집합 불변, 상충 플래그 누락.

## 중요한 제한

테스트용 목록과 승인 증거의 불리언은 외부 신뢰 경계에서 검증하지 않는다. 서명·실제 신원·독립된 증거 출처 검증·원자적 재사용 방지·권한 취소/감사 로그·운영 호출자 차단은 구현되지 않았다. 이 코드는 **오프라인 정책 프로토타입**이며 운영 승인에 사용해서는 안 된다.

## 금지 작업 준수

운영 코드·상태 파일·레지스트리·기존 정책 파일·main 브랜치 수정 없음. CU API, Telegram, GitHub Actions 호출 없음.
