# CU·이마트24 증거 수집·수동 승인 전 검증 결과 — 2026-10-14

## 실제 실행
- Python 3.13.5 격리 환경에서 GitHub `tests/offline_store_evidence_intake_v2.py`와 `tests/test_offline_store_evidence_intake_v2.py` 내용을 그대로 재현해 실행: **9/9 통과**.
- 이어서 신규 `tests/offline_manual_approval_gate.py` 및 `tests/test_offline_manual_approval_gate.py`를 같은 격리 환경에서 실행: **11/11 통과**.
- 전체 `python -m unittest discover -s /mnt/data/cu_emart_validation/tests -p 'test_offline_*.py' -v` 결과: **20/20 통과**.
- GitHub 체크아웃이나 Actions 실행은 아님. 이 테스트는 신규 4개 파일에 한정하며 프로젝트 전체 회귀 결과가 아님.

## CU 아산 점포 검토
- `asan_cu_watch_registry.json`의 119개 후보 중 28개 코드 보유, 91개 미보유.
- `docs/asan_cu_91_manual_approval_queue_20261014.csv`에 91개 각각의 기존 후보 ID, 점포명, 주소, 단일 바코드 `8800286275732`를 입력함.
- **store_code/source_url/observed_at는 모두 비워둠**. 기존 공개 인허가 URL은 점포코드 증거가 아니므로 출처로 채우지 않음.
- 91개 모두 `BLOCKED_NO_CODE`로 기록. 신규 확정 코드 0, 자동 등록 0.
- 기존 후보 중 동일 주소 충돌은 검토 상태로 유지. 코드 추정/병합 금지.

## 이마트24 제주
- 공식 매장 찾기 https://m.emart24.co.kr/store 는 점포명·주소 검색 수단. 공개 페이지에서 실제 재고 조회용 내부 코드의 제주시 점포 매핑은 확보하지 못함.
- 제주 증거가 확인되지 않았으므로 빈 `docs/store_code_evidence_intake_template_20261014.csv`를 유지. 제주 코드 0, 제주 감시 미지원 및 미활성화.

## 수동 승인 전 차단 게이트
- 새 `tests/offline_manual_approval_gate.py`는 코드 누락, 중복 코드(기존 코드·동일 제출), 다른 상품, CU 후보 ID 불일치, 점포명·주소 불일치, 제주시 외 주소, 비HTTPS/날짜 오류·미래 날짜를 검사함.
- 통과해도 `approved=false`, `MANUAL_REVIEW_REQUIRED`만 출력. **자동 승인·실제 점포 등록 없음**.
- 출처 URL 형식 및 점포 문자열 일치만으로 원천 증거 진위가 보장되지 않음. 사람이 실제 점포코드의 공식 출처를 확인해야 함.
- `offline_store_evidence_intake_v2.py`의 기존 검증은 별도로 유지. 신규 게이트는 수동 승인 전 추가 방어막이며 운영 감시 코드와 연결하지 않음.

## 보호 범위
`permission-test-20261013-cu`에 오프라인 테스트·CSV·문서만 추가. `main`, GS25, 운영 모니터/워크플로/상태/설정, 실 재고 API, Telegram 미변경·미실행. 기존 첫 양수/증가/감소/품절 및 실패 시 미관측 유지 정책 보존.
