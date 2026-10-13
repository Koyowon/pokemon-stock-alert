# 아산 CU 3건 증거 검토 상태 전환 정책 (오프라인 제안)

일자: 2026-10-13. 대상: ASAN-CU-083/41691 (지번↔도로명), ASAN-CU-092/27756 (호수·건물), ASAN-CU-100/40840 (아파트 명칭). 근거 원문은 기존 `docs/asan_cu_three_address_evidence_hold_review.md`와 두 원본 JSON에 한정한다.

## 상태 및 판정

- 초기 상태: `HOLD_UNVERIFIED`.
- 증거 수준 `NONE`: 증거 없음 → HOLD.
- `PARTIAL`: 일부 자료만 있음, 출처/날짜/코드/주소/상세위치/독립 검토 중 하나라도 부족 → HOLD.
- `CONFLICTING`: 상충 표시가 있으면 충분성보다 우선 → HOLD.
- `SUFFICIENT`: 검증 가능한 출처, 날짜, 대상 CU 코드, 사례별 쟁점 유형, 주소 연결, 건물·상가·호수 검증, 독립 검토가 **모두** 충족 → **여전히 HOLD**.
- `SUFFICIENT`에 더해 해당 ID·CU 코드와 일치하는 별도 명시적 승인 기록(승인자, 승인 참조번호, `explicit=true`)이 있어야 `APPROVED_FOR_REVIEW_ONLY`로 전환.
- 이 상태는 **검토 프로세스 승인**일 뿐 동일 장소 확정, 점포 이전/개명 확정, 운영 적용 승인, 재고 확인을 의미하지 않음.
- 승인 근거 철회/상충 또는 새 검토 주기에서는 다시 평가하며 영구 승인 자동 승계 금지. 합성 정책은 비영속 함수이며 상태 파일을 변경하지 않음.

## 3건에 대한 개별 게이트

| ID | 필요한 증거 | 누락 시 |
|---|---|---|
| ASAN-CU-083 | 공수리 282 ↔ 모산로126번길 17-7의 공식 대응 및 건물 식별 | HOLD |
| ASAN-CU-092 | 아산로 103-17의 103~105호 ↔ 아파트 1층 점포 구획 대응 | HOLD |
| ASAN-CU-100 | 아이유쉘2차 ↔ 2단지의 공식 명칭 관계 및 상가·호수 식별 | HOLD |

기존 두 JSON에 이 필수 근거는 없으므로 **실제 세 건은 모두 HOLD_UNVERIFIED**. 테스트의 충분한 근거 및 승인 입력은 실제 확보 자료가 아닌 합성 fixture.

## 산출물 및 검증

- `tests/cu_evidence_transition_policy.py`: 외부 호출·상태 저장이 없는 순수 정책 프로토타입.
- `tests/test_cu_evidence_transition_policy.py`: 12개 합성 unittest. 무증거/부분/충돌/충분+미승인/충분+승인/잘못된 대상·코드·쟁점/독립검토·승인참조 누락/운영 미활성 등.
- ChatGPT 격리 환경에서 **동일 정책 로직을 재현한 별도 12개 테스트 12 PASS, 0 FAIL, 0 ERROR**. GitHub raw 호스트 DNS 실패로 **커밋된 실제 테스트 파일 자체를 로컬에서 실행하지 못함**. 따라서 GitHub 파일 실행 성공으로 주장하지 않음.
- GitHub Actions, CU API, Telegram, 운영 `main()` 호출 없음. 원본 `cu_stock_monitor.py`, `cu_stock_state.json`, `asan_cu_watch_registry.json` 및 `main` 브랜치 수정 없음.

## 운영 도입 전 보완할 안전 게이트

- 현재 프로토타입은 합성 입력의 `source_verified` 등 불리언 플래그를 신뢰하며 공식 증거를 **실제로 검증하지 않음**. 승인자 신원 확인·서명·권한 검증도 하지 않음.
- 따라서 실제 운영 승인이나 점포 주소 확정에 직접 사용 금지. 향후 별도 승인된 검증 절차와 감사 추적 필요.
