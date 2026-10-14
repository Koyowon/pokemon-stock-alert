# CU 아산 91개·이마트24 제주 공개자료 증거 조사 (2026-10-14)

## 범위
오직 공개 웹 문서 및 기존 GitHub 스냅샷을 읽어 비교. **실 재고 API, Telegram, 운영 코드/워크플로/상태, GS25, main 미접촉**. 숫자 점포코드 추정·자동 등록 없음.

## 공식 매장 조회 경로
- CU 공식 점포 검색: https://www.pocketcu.co.kr/store/around
- CU 공식 포켓CU 기능 안내: https://cu.bgfretail.com/membership/app_info.do?category=membership_info&depth2=4
- 이마트24 공식 매장 찾기: https://m.emart24.co.kr/store
- 이마트24 공식 매장 찾기(별도 경로): https://everse.emart24.co.kr/store/
- 이마트24 공식 FAQ: https://emart24.co.kr/helpdesk/faq/search?search=%EB%A7%A4%EC%9E%A5

공식 페이지는 점포명·주소 조회 경로를 제공하지만 이번 웹 검색의 정적 결과에서 **재고 API용 내부 점포 코드와 점포명·주소의 검증 가능한 일대일 매핑은 확보되지 않음**. 웹 매장 목록의 전화번호나 URL의 숫자를 점포코드로 해석하지 않음.

## 아산 CU: 공개 인허가 기반 목록
- 기존 후보 출처: https://cafe.ayo.pe.kr/convenience/region/%EC%B6%A9%EB%82%A8/%EC%95%84%EC%82%B0%EC%8B%9C
- 위 페이지에 `씨유아산둔포원룸점` (둔포로 78), `씨유아산테크노밸리2호점` 및 `씨유 아산제2테크노밸리점` (둘 다 운용길 73)이 기재되어 있어 후보 명칭/주소 출처를 확인.
- 둔포면 세부 목록: https://cafe.ayo.pe.kr/convenience/region/%EC%B6%A9%EB%82%A8/%EC%95%84%EC%82%B0%EC%8B%9C/%EB%91%94%ED%8F%AC%EB%A9%B4
- 이 자료는 영업 신고 기준이며 실시간 영업 상태 또는 CU 내부 점포코드의 증거가 아님. 동일 주소 점포는 중복/이전/분리 점포일 수 있으므로 병합 금지.
- 기존 CU 후보 119개 중 코드 확보 28, 미확보 91. 저장된 CU 아산 코드 28개는 전부 기존 후보에 배정됨. **새롭게 확정한 코드 0개**.

## 점포별 확인 기록(기존 후보 ID)
| ID | 공개 자료 확인 내용 | 코드 검증 | 판정 |
|---|---|---|---|
| ASAN-CU-001 | 둔포원룸점, 둔포로 78 이름/도로명 확인 | 없음 | NAME_ADDRESS_ONLY |
| ASAN-CU-078 | 아산테크노밸리2호점, 운용길 73 | 없음 | ADDRESS_COLLISION_REVIEW |
| ASAN-CU-079 | 아산제2테크노밸리점, 운용길 73 | 없음 | ADDRESS_COLLISION_REVIEW |
| ASAN-CU-008 / ASAN-CU-089 | 동일 주소 충돌(충무로 1396) 기존 자료에 존재 | 없음 | ADDRESS_COLLISION_REVIEW |

이름/주소 출처가 있어도 `CU 점포 코드 + 이름 + 주소 + 출처 + 확인 시점` 모두 검증될 때까지 자동 배정 금지. 현재 91개 전부 `UNRESOLVED_NO_CODE` 유지.

## 이마트24 제주
- 공식 매장 찾기: https://m.emart24.co.kr/store
- 이마트24 FAQ는 공식 웹/앱의 매장 찾기를 주소·연락처 조회 수단으로 안내: https://emart24.co.kr/helpdesk/faq/search?search=%EB%A7%A4%EC%9E%A5
- 공개 검색에서 **제주시 매장과 내부 숫자 코드의 동일 출처 매핑을 확보하지 못함**. 코드 확인 0개.
- 기존 `stores.json` 제주 점포 0개, 운영 `monitor.py` 제주 지역 미지원, 이마트24 제주 제어 플래그 false. 제주 시드 작성/활성화 금지.

## 후속 자료 수집 요건
1. CU: 공식 매장명·도로명주소와 API의 실제 `storeCode`를 동일 관측 기록에서 확보(현재 금지된 실 API 조회는 실행하지 않음).
2. 이마트24: 공식 점포명·주소와 실제 API `storeCode`가 함께 나타나는 신뢰 가능한 출처 확보.
3. 같은 주소에 서로 다른 상호가 있을 경우 점포별 독립 식별자 증거 확보.
4. 증거가 확보되어도 운영 반영 전 오프라인 중복·상품바코드·알림회귀 검증.

## 결론
공개 자료는 일부 점포명·주소의 후보 근거를 보강하지만 **새 숫자 점포코드 0개**. 따라서 실 감시 범위 변경 없음. 증가·감소·품절 알림 및 조회 실패 시 상태 유지 정책은 운영 코드를 수정하지 않아 그대로 보존.
