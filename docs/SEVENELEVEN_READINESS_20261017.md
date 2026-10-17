# 세븐일레븐 재고 연동 준비 — 2026-10-17

상태: 조사 및 제한 진단 준비 완료, 운영 연결은 미완료.
기준 main: e597829360c478c6f5459ba8d996e12d86b7d50e

## 확인한 것

- 공식 세븐일레븐 앱의 개발사 설명은 전국 매장의 재고찾기 기능을 안내한다.
  - https://play.google.com/store/apps/details?id=kr.co.kork7app&hl=ko
  - https://apps.apple.com/kr/app/%EC%84%B8%EB%B8%90%EC%9D%BC%EB%A0%88%EB%B8%90/id1253773772
- 저장소의 이전 seveneleven_diagnostic.py·seveneleven_relay_diagnostic.py·convenience_relay_compare.py는 제3자 mcp.aka.page의 /api/seveneleven/products·stores·inventory 경로를 사용했었다. 코드에 경로가 있다는 사실만으로 현재 정상 동작·공식 제공·허용 요청률·정확한 수량을 증명하지 않는다.
- 현재 main에는 세븐일레븐 운영 모니터·상태·정기 조회가 없다. 기존 남원·아산·전주와 30주년 카드 조회 범위를 확장 대상으로 삼는다.

## 아직 확인하지 못한 것

현재 제공자의 공개 문서 원문을 웹 조회 도구로 가져오지 못했다(https://mcp.aka.page/ 접근 불가). 공식 웹사이트 원문도 이번 조회에서 timeout이었다. 따라서 API 응답 필드·페이지 처리·상품코드·점포코드·성공/오류/0개 판정·자동조회 허용 조건을 현재 명세로 확정하지 못했다. 공식 앱에 재고찾기가 있다는 사실은 외부 자동화 API 허용을 뜻하지 않는다.

기존 진단 workflow의 과거 실행 결과도 이번 GitHub 커넥터 조회에서 확보하지 못했다. workflow 목록 URL은 커넥터의 허용 endpoint 제한으로 거절됐고, 보관 전 파일명으로 조회한 실행 목록에서도 분석 가능한 본문을 얻지 못했다. 과거 진단이 성공했거나 지금도 실패 중이라고 추정하지 않는다.

다른 편의점의 바코드 8800286275732를 세븐일레븐 내부 상품코드로 가정하지 않는다. 검증 없이 재고 0 또는 양수로 표시하거나 알림을 보내지 않는다. 로그인·토큰·접근 제한을 우회하는 작업도 하지 않는다.

## 준비한 진단

seveneleven_readiness.py는 기본 실행 시 네트워크 없이 계획만 출력한다. --live 플래그가 있어야 아래 공개 제3자 경로에 각각 1회, 최대 3번 GET한다. 이는 과거 저장소에서 사용한 후보 경로이며 현재 검증된 계약은 아니다.

| 순서 | 경로 | 파라미터 |
|---|---|---|
| 1 | /api/seveneleven/products | query=포켓몬확장팩(30주년), size=5, format=html |
| 2 | /api/seveneleven/stores | keyword=남원, limit=5, format=html |
| 3 | /api/seveneleven/inventory | keyword=포켓몬확장팩(30주년), storeKeyword=남원, storeLimit=5, format=html |

제약: 요청당 timeout 10초, 응답 최대 64KiB, 오류 시 즉시 중단, 재시도 0회, 자동 redirect 금지, 상태 파일 저장·Telegram·Actions 0회. 소켓 timeout은 전체 소요시간의 엄격한 상한이 아니다. 단일 남원 표본만으로 아산·전주 전체 커버리지를 검증했다고 주장하지 않는다.

원문 미리보기와 HTTP 상태·최상위 JSON 필드만 출력하며 HTTP 200이어도 inventory_status는 UNVERIFIED다. 실제 값의 의미는 응답 계약과 상품·점포 식별을 대조한 뒤 결정한다.

## 오프라인 검증

7개 테스트 통과: 기본 모드 무호출, 계획 3건 고정, 모의 HTTP 성공도 미검증 유지, 429 무재시도, 502를 0으로 변환하지 않음, timeout 중단, 과대 응답 중단. 성공/실패 응답은 모두 합성 fixture이며 세븐일레븐 실제 재고를 검증한 것이 아니다.

```sh
python seveneleven_readiness.py
python -m unittest -v test_seveneleven_readiness
```

## 다음 승인 대상

이전 작업에서 유지한 실제 재고 API 호출 금지 때문에 live 진단은 실행하지 않았다. 위 최대 3건의 읽기 전용 진단을 허용하는 승인을 요청한다. 승인 후 정상 경로와 응답 계약이 확인되면 상품·점포 이름/주소·페이지 범위 검증, 미확인/0 구분, 알림 및 지역 제어 통합을 별도 브랜치에서 구현하고 회귀 검증한다. 경로가 오류를 반환하거나 외부 사용 조건을 확인할 수 없으면 운영 연결을 보류한다.

이 브랜치는 진단 소스·테스트·이 보고서만 추가한다. main·기존 3개 편의점 코드·상태·설정·워크플로·웹 화면은 수정하지 않는다. 정리 작업은 별도 승인에 따라 이미 main에 반영했다.
