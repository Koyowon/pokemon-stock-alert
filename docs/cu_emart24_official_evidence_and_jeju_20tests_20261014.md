# CU 아산·이마트24 제주 내부 점포코드 증거 조사 및 직접 오프라인 테스트 — 2026-10-14

## 공식 공개 자료 확인
1. CU 공식 점포 검색: https://www.pocketcu.co.kr/store/around — 지역·점포명 검색을 지원하지만 정적 공개 결과에 재고 API용 내부 점포코드 매핑은 나타나지 않음.
2. CU 공식 포켓CU 안내: https://cu.bgfretail.com/membership/app_info.do?category=membership_info&depth2=4 — 재고조회 기능 제공 확인. 점포코드 목록 제공 근거는 아님.
3. 이마트24 공식 매장 검색: https://m.emart24.co.kr/store — 점포명·주소·전화번호 조회 가능. 공개 페이지의 전화번호는 내부 점포코드가 아님.
4. 이마트24 공식 FAQ: https://emart24.co.kr/helpdesk/faq/search?search=%EB%A7%A4%EC%9E%A5 — 매장 찾기 경로 및 매장 전화번호 안내. API 점포코드 공개 근거는 아님.
5. 이마트24 공식 고객센터: https://m.emart24.co.kr/helpdesk — 공식 질의 경로. 문의를 실제 발송하지 않았음.

**증거 채택 기준:** 같은 점포의 이름·도로명주소·실제 재고 API 점포코드가 신뢰 가능한 원천 자료에서 명확히 연결되고 확인일이 기록되어야 함. 전화번호·지도 ID·상점 URL 번호·유사 명칭만으로 점포코드를 추정하거나 자동 등록하지 않음.

## 조사 결과
- CU 아산: 기존 119개 후보, 28개 기존 코드, 미확보 91개. **신규 검증 코드 0**.
- 이마트24 제주: 기존 캐시 0개, 제주 비활성. **신규 검증 코드 0**.
- `docs/store_code_evidence_intake_template_20261014.csv`는 증거 입력 헤더만 유지. 출처와 점포코드가 검증되지 않은 신규 행은 작성하지 않음.
- `docs/asan_cu_91_manual_approval_queue_20261014.csv`의 91개 미확보 상태 유지. 운영 등록 없음.

## GitHub 원문 기반 실제 실행
GitHub 커넥터로 브랜치의 다음 네 파일을 읽고 그 내용을 로컬 격리 경로에 복사해 직접 실행:
- `tests/offline_jeju_simulator.py`
- `tests/test_offline_jeju_simulator.py`
- `tests/offline_emart24_jeju_plan.py`
- `tests/test_offline_emart24_jeju_plan.py`

실행: `python -m unittest discover -s /mnt/data/cu_emart_run/tests -p 'test_offline_*.py' -v`

결과: **20 tests, OK**. 확인한 범위는 첫 재고·증가·감소·품절·동일 재고·미관측·알림 전달 실패 시 상태 보존, 잘못된 상품/재고 차단, 제주 seed 빈 목록·잘못된 주소·출처 누락 차단, 오프라인 준비 상태.

테스트에 등장하는 `01234` 및 `제주테스트점`은 **가상의 fixture**이며 실제 점포나 확인된 점포코드가 아님.

## 제한 및 보호 범위
- GitHub 전체 저장소 clone, GitHub Actions 실행, 전체 테스트 실행은 하지 않았음. 20개는 상기 네 파일의 테스트만 뜻함.
- 코드 확보 가능성은 공개 정적 페이지에 한정하여 확인. 내부 식별자 비공개 여부를 사업자에게 직접 확인한 것은 아님.
- `main`, GS25, 운영 워크플로, 운영 감시 코드·설정·상태, 실 재고 API, Telegram 미변경·미실행.
- 기존 증가·감소·품절 및 미관측 시 상태 보존 로직 변경 없음.
