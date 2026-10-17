# 포켓몬카드 30주년 전북 재고 알리미 — 클라우드 초기 버전

## 현재 구현 범위
- CU, GS25, 이마트24 / 전북특별자치도 전체 / 30주년 관련 상품 검색 조건
- 텔레그램 테스트 알림
- 검증된 재고 데이터가 나중에 연결되면 신규 재고·수량 증가 알림 및 상태 저장
- GitHub Actions 예약 실행(10분 간격 요청; 실제 실행 시간은 지연될 수 있음)

**중요: 세 편의점의 실제 재고 데이터 조회 연동은 아직 없습니다. 이 버전은 재고를 검색하거나 실제 입고를 통보하지 않습니다.** 점포별 공식 서비스의 이용조건과 허용된 데이터 접근 방법을 확인한 뒤 `monitor.py`의 `load_stock()`에 실제 조회 기능을 추가해야 합니다. 로그인 보호·접근 제한을 우회하지 마세요.

## 아이폰에서 설치
1. GitHub의 비공개 저장소를 엽니다.
2. 압축 해제 후 `monitor.py`, `config.json`, `state.json`, `README.md`를 저장소 루트에 올립니다.
3. **중요:** `.github/workflows/stock-monitor.yml`은 해당 경로에 정확히 생성해야 합니다. iOS Safari에서 `Add file` → `Create new file`을 선택하고 파일명 칸에 `.github/workflows/stock-monitor.yml`을 입력한 다음 ZIP 안의 내용을 붙여넣는 방법이 가장 확실합니다.
4. `Settings` → `Secrets and variables` → `Actions` → `New repository secret`에서 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 각각 등록합니다. **토큰을 코드·채팅·스크린샷에 공개하지 마세요.**
5. `Actions` → `Pokemon Stock Monitor` → `Run workflow` → `Run workflow`를 누릅니다. 처음 수동 실행은 텔레그램 테스트 메시지만 보냅니다.
6. 정기 실행은 저장소 기본 브랜치의 워크플로에서 작동합니다. GitHub 정책에 따라 지연·중단될 수 있으며 정확한 10분 주기를 보장하지 않습니다.

## 운영 관련 주의
- 이 버전은 재고 데이터가 연결되기 전에는 예약 실행 시 '연동 없음'만 기록하고 알림을 보내지 않습니다.
- `state.json`을 저장소에 커밋하는 방식으로 이전 수량을 보존하도록 준비했습니다. `contents: write` 권한이 필요합니다.
- 무료 사용량, 비공개 저장소 Actions 실행 제한, Actions 정책을 확인하세요.
- 실제 재고는 변경될 수 있으니 방문 전 매장에 전화로 확인하세요.
