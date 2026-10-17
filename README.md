# 포켓몬카드 30주년 재고 알림

CU·이마트24·GS25의 남원·아산·전주 재고 조회, 수량 변동 Telegram 알림, 지역별 조회 제어를 운영합니다. 실제 재고는 조회 후 바뀔 수 있으며 누락·오류는 재고 0과 구분합니다.

## 운영 파일

| 역할 | 진입점 | 주요 데이터·의존성 |
|---|---|---|
| 이마트24 조회 | `monitor.py` | `request_pacing.py`, `stores.json`, `emart24_jeonju_seed.json`, `state.json` |
| CU 재고 조회 | `cu_stock_monitor.py` | `cu_asan_registry.py`, `asan_cu_watch_registry.json`, `cu_stock_state.json` |
| CU 상품등록 감지 | `cu_registration_monitor.py` | `cu_registration_state.json` |
| GS25 조회 | `gs25_independent/gs25_auto_monitor.py` | 같은 폴더의 `config.json`, `gs25_asan_guard.py`, `gs25_asan_approval_review.csv`, `gs25_stock_state.json` |
| Telegram 제어·현황 | `telegram_control.py` | `stock_snapshot_report.py`, `unified_control.json`, `telegram_control_cursor.json` |
| 공통 지역 설정 | `region_config.py`, `unified_settings.py` | `region_settings.json`, `unified_control.json` |
| 저장 재고 웹 화면 | `docs/stock/index.html` | CU·이마트24·GS25의 마지막 저장 기록을 읽으며 0개와 미확인을 구분 |
| 지도 링크 연결 | `docs/index.html` | Telegram 현황의 지도 링크에서 사용 |

위 파일의 경로와 상태 데이터를 유지해야 합니다. **기존 상태 파일을 지우면 이전 수량과 알림 기준을 잃을 수 있습니다.**

## 정기 실행

루트 `.github/workflows/`에서 다음 5개가 정기 실행됩니다.

- `stock-monitor.yml`: 이마트24, 5분 cron
- `cu-stock-monitor.yml`: CU 재고, 5분 cron
- `cu-registration-monitor.yml`: CU 상품등록, 15분 cron
- `gs25-stock-monitor.yml`: GS25, 5분 cron
- `unified-telegram-control.yml`: Telegram 제어, 5분 cron

예약 시각은 실제 시작 간격을 보장하지 않습니다. 상태 저장·웹 화면의 기록은 실시간 재고 보장이 아닙니다. 기타 남아 있는 수동 진단 워크플로는 문제 분석용으로 유지합니다.

## 오프라인 검증

실제 재고 API·Telegram 없이 최적화 및 GS25 guard 회귀를 검증하는 명령:

```sh
python -m unittest -v test_monitor_optimization test_gs25_guard_integration gs25_independent.test_gs25_asan_guard
```

`test_stock_alerts.py` 등 다른 수동 진단 스크립트에는 외부 통신이 포함될 수 있습니다. 위 오프라인 명령과 구분하여 사용하세요.

## 보관 파일

완료된 일회성 설치/통합 도구, 초기 설정, 현재 운영 대상이 아닌 세븐일레븐 진단 도구를 [보관 폴더](archive/retired_20261017/README.md)로 옮겼습니다. 영구 삭제하지 않았으며 원래 경로와 Git blob SHA는 [복원 목록](archive/retired_20261017/MANIFEST.json)에 기록했습니다. 보관된 workflow는 Actions 목록에서 실행되지 않습니다.

점포 등록 근거와 감사 데이터는 운영에 직접 쓰이지 않더라도 검증 이력을 위해 유지합니다. 최근 변경은 [조회 최적화 보고서](docs/STOCK_QUERY_OPTIMIZATION_20261017.md), [이마트24 공식 코드 보고서](docs/EMART24_OFFICIAL_CODES_20261017.md)를 참고하세요.
