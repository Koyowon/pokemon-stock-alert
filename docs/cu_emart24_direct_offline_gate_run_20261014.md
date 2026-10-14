# 실제 오프라인 승인 게이트 코드 실행 및 공개 식별자 증거 확인 (2026-10-14)

## 직접 실행한 저장소 코드
GitHub 커넥터로 `permission-test-20261013-cu`의 다음 파일 전체를 가져와 로컬 격리 디렉터리에 **동일한 내용으로 복사**하고 Python unittest 실행:
- `tests/offline_manual_approval_gate.py`
- `tests/test_offline_manual_approval_gate.py`

명령: `python -m unittest discover -s /mnt/data/cu_actual_repo/tests -p 'test_offline_manual_approval_gate.py' -v`

결과: **16 tests, OK**. 코드 축약·모의 구현이 아닌 GitHub에서 가져온 승인 게이트 원문과 테스트 코드 실행. GitHub Actions/운영 워크플로는 실행하지 않음. 저장소 전체 오프라인 테스트를 실행한 것으로 해석하지 말 것.

검증된 정책: 승인 false, 코드 누락, 코드 중복, 동일 CU 후보 복수 코드, 공백 정규화 중복, 바코드 불일치, CU 후보·주소 불일치, 제주시 외 주소·위장 문자열, 이름 누락, 비HTTPS·자격증명 포함 URL, 미래 확인일 차단.

## 점포코드 공개 증거 재조사
- 이마트24 공식 매장 찾기: https://m.emart24.co.kr/store
- 이마트24 공식 FAQ: https://emart24.co.kr/helpdesk/faq/search?search=%EB%A7%A4%EC%9E%A5
- CU 공식 점포 검색: https://www.pocketcu.co.kr/store/around
- 공식 점포 찾기는 매장명·주소·연락처 조회에 유용하지만, 공개 검색 결과에서 **실제 재고 API 내부 점포코드와 점포명·주소의 검증 가능한 일대일 매핑은 확인하지 못함**.
- 이마트24 FAQ의 '매장 번호'는 전화번호 문맥이며 내부 재고 API 코드가 아님.
- 기존 CU 아산 119 후보 중 미확보 91, 기존 코드 28. 이마트24 제주 캐시 0 및 제주 OFF. 신규 코드 0, 승인 0, 등록 0.

## 제한
- 로컬 실행은 두 파일에 한정. 실제 JSON·CSV 원본 교차 검증은 앞선 단계에서 GitHub 커넥터로 수행했지만, 이번 실행의 unittest는 합성 fixture 기반.
- URL이 HTTPS이고 형식이 유효해도 실제 점포코드의 공식 출처 진위가 증명되는 것은 아님.
- `main`, GS25, 운영 코드·설정·상태·워크플로, 실 재고 API, Telegram 미접촉. 증가·감소·품절 및 조회실패 상태 유지 정책 변경 없음.
