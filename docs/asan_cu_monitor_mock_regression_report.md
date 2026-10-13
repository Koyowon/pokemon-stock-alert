# CU 모니터 파싱·식별·재고 회귀 점검 (오프라인)

일자: 2026-10-13. 브랜치: `permission-test-20261013-cu`.
대상 운영 파일: `cu_stock_monitor.py` (읽기 전용).
신규 테스트: `tests/test_cu_monitor_parser_regression.py`.

## 실제 수행 결과와 범위

- GitHub에서 운영 코드 원문을 읽고, 그 중 HTMLTokens, field, stock_number, valid_address, extract_stores, query의 관련 함수 부분을 격리된 ChatGPT Python 환경에 **수동으로 분리한 사본**으로 구성함.
- 외부 요청 함수 `urllib.request.urlopen`을 `unittest.mock.patch`로 대체하고 가상 HTML 응답을 제공함.
- **격리 사본 기준 13개 테스트 실행: 13 PASS / 0 FAIL / 0 ERROR (0.005초)**.
- 원본 파일 전체를 직접 내려받아 import하는 방식은 외부 GitHub 호스트 DNS 접근이 실패해 수행하지 못함. 따라서 실행 결과를 **원본 파일 전체에 대한 검증으로 표현하지 않음**.
- 새 브랜치 테스트는 `cu_stock_monitor`를 직접 import하고 `urlopen`을 패치하도록 작성했지만, **GitHub에 커밋한 해당 테스트 파일의 실행은 아직 수행하지 않음**. CI 또는 GitHub Actions 실행도 하지 않음.

## 합성 응답 검증

정상 파싱, 명시적 재고 0, 누락/음수 재고 제외, 아산 이외 주소 제외, 숫자가 아닌 점포 코드 제외, 잘못된 바코드 및 success=false 거부, query 파라미터 size=100/offset=0, 재고 숫자 변환 검증.

## 발견한 설계상 위험 및 추가 검증 과제

1. `query()`는 동일 `storeCode`가 응답에 중복되면 그대로 반환함. 이후 `main()`이 동일 코드·동일 수량을 합치고, **수량 또는 도시가 다른 경우** 해당 코드를 `conflicts`로 제외함. 이 `main()` 경로는 이번 격리 실행으로 검증되지 않았음.
2. `main()`의 중복 판정은 같은 코드의 **점포명·주소 불일치**를 비교하지 않음. 동일 코드에 서로 다른 이름/주소가 있어도 수량·도시가 같으면 첫 레코드가 유지될 수 있음. 별도 회귀 테스트 권장.
3. `query()`의 주소 검증은 도시 접두사 기반이며 실제 점포 위치·실존 여부·등록 후보와의 일치를 증명하지 않음.
4. `size=100`, `offset=0`은 설정값일 뿐 반환 상한·페이지네이션 동작의 증거가 아님.
5. 성공한 지리 조회에서 누락된 후보를 재고 0으로 처리하지 않아야 함. `NOT_QUERIED`, `NOT_OBSERVED`, `ZERO_STOCK` 구분 유지.
6. 실제 운영 `main()`은 Telegram 및 상태 저장 경로를 포함하므로 이 테스트에서 호출하지 않음.

## 안전한 후속 테스트

GitHub 원본을 직접 체크아웃한 **격리된 오프라인 환경**에서 `python -m unittest discover -s tests -p 'test_cu_monitor_parser_regression.py' -v`를 실행한 뒤, 결과를 확인할 것. 이후에도 운영 `main()` 전체를 실행하지 않고 AST로 분리한 관측 병합 부분 또는 의존성 주입된 순수 함수로 중복/충돌 로직을 검증해야 함. 상태 파일 쓰기·Telegram 호출·CU API 호출은 차단.

## 변경 범위

신규 테스트 및 이 보고서만 feature branch에 추가. 기존 운영 코드, 상태 파일, 워크플로, `main` 변경 없음. CU API 호출·Telegram 발송·GitHub Actions 실행 없음.
