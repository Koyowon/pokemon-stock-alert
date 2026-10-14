# CU·이마트24 30주년팩 오프라인 통합 검증 — 2026-10-14

## 실행 검증
- GitHub 테스트 브랜치의 `tests/offline_chain_coverage_audit.py` 및 `tests/test_offline_chain_coverage_audit.py` 내용을 로컬 격리 디렉터리에 재현하고 Python 3.13 `unittest discover` 실행: **1 test, PASS**.
- 이 검증은 임시 fixture 기반 감사 로직 1개에 한정된다. 전체 GitHub 체크아웃, 운영 모니터 전체 회귀, GitHub Actions 실행 결과를 의미하지 않는다.
- 이번에 추가한 `tests/offline_store_gap_analysis.py`, `tests/test_offline_store_gap_analysis.py`는 GitHub에 저장했으나 **실행 PASS 미확인**.

## 저장소 원본 교차 검증
- 아산 CU 후보 119개, 코드 보유 28개, 미보유 91개.
- 저장된 `cu_stock_state.json` 아산 코드 28개. 후보 91개와 저장된 아산 점포의 **정규화 점포명 정확 일치 신규 코드 후보 0개**. 새 코드를 임의 부여하지 않음.
- 이마트24 `stores.json` 114개: 남원 11개, 아산 40개, 전주 63개, 제주 0개.
- `emart24_jeonju_seed.json` 63개 중 캐시에 없는 코드 **0개**.
- 이마트24 `unified_control.json` 제주 OFF. `monitor.py` 지역 목록에 제주 없음. 설정만 켜서는 제주 조회 불가능.
- CU는 4개 지역 검색 좌표가 있으나 첫 페이지 `size=100, offset=0`만 조회. 실제 누락 범위는 미확인.
- 이마트24 검색 `limit=100`; 실제 검색의 완전성 미확인.
- 두 모니터 모두 목표 바코드 `8800286275732`를 사용하고, 재고 증가·감소·품절 분기가 존재. 실제 메시지 발송은 검증하지 않음.

## 남은 실질적 차단 요인
1. CU 91개 코드의 외부 신뢰 가능한 CU 전용 증거 부족. 현재 저장 데이터로 신규 코드 확정 불가.
2. 이마트24 제주 점포 목록 0개, 실행 코드 미지원. 운영 코드 변경 없이 제주 감시 활성화 불가.
3. 전수 점포 등록을 주장하려면 점포 명부의 신뢰 가능한 최신 자료 및 실제 조회 범위 검증이 필요.
4. 라이브 API·텔레그램·워크플로는 사용자 요청에 따라 실행하지 않음.

## 이번 브랜치 추가 파일
- `tests/offline_store_gap_analysis.py`: CU 저장 점포명 정확 일치 후보(자동 연결 금지), 이마트24 시드·캐시 차이, 제주 준비 상태 출력.
- `tests/test_offline_store_gap_analysis.py`: 임시 fixture를 사용하는 회귀 테스트.
- 이 보고서.

`main`, GS25, 운영 모니터, 운영 워크플로, 운영 상태 파일, 외부 API 및 Telegram 변경 없음.
