# CU·이마트24 통합 오프라인 교차 검증 — 2026-10-14

## 실제 저장소 스냅샷 교차 검증
GitHub 커넥터에서 `permission-test-20261013-cu` 브랜치의 다음 6개 원본을 직접 읽어 교차 대조:
- `asan_cu_watch_registry.json`
- `cu_stock_state.json`
- `stores.json`
- `unified_control.json`
- `docs/asan_cu_91_manual_approval_queue_20261014.csv`
- `docs/asan_cu_91_evidence_review_20261014.csv`

검사 결과:
- 아산 CU 후보 119개, 코드 미확보 91개, 코드 확보 28개.
- 수동 승인 대기표 91행, 검토표 91행. 두 CSV의 후보 ID 집합·이름·주소가 모두 원본 registry와 일치: **불일치 0건**.
- 수동 승인 대기표 91개 모두 코드/코드 출처 URL/관측일이 비어 있고, `BLOCKED_NO_CODE`, 바코드 `8800286275732`: **위반 0건**.
- 저장된 아산 CU 코드 28개 중 기존 등록 후보에 없는 미배정 코드: **0개**.
- 동일 주소 충돌 4개: `ASAN-CU-008`, `ASAN-CU-089`, `ASAN-CU-078`, `ASAN-CU-079`; 임의 병합 없음.
- 이마트24 제주 캐시 0개, 제주 기능 플래그 false. 검증된 신규 점포 코드 0개.

## 이번 브랜치 변경
- `tests/test_offline_registry_preflight.py`: 원본 JSON/CSV를 읽어 후보 수·ID/이름/주소·빈 코드·바코드·기존 코드 중복·제주 비활성·주소 충돌을 검증하는 **9개** read-only 테스트 추가.
- `tests/offline_manual_approval_gate.py`: 동일 제출 내 CU 후보 ID에 서로 다른 코드가 여러 개 제안되는 경우에도 `REJECT_DUPLICATE_CANDIDATE`로 차단. 코드의 선후 공백을 제거한 뒤 중복 판정.
- `tests/test_offline_manual_approval_gate.py`: 위 두 회귀 사례 **2개** 추가.
- 기존 운영 감시/상태/설정/워크플로 파일 변경 없음.

## 실제 오프라인 실행
- 격리된 Python 3.13.5 작업 디렉터리에 이전에 GitHub에서 확인한 오프라인 테스트 코드와 이번 변경을 재현.
- `python -m unittest discover -s /mnt/data/cu_emart_full_offline/tests -p 'test_offline_*.py' -v`
- **40 tests, OK**. 이전에 준비된 오프라인 29개 + 원본 검증 9개 + 신규 중복 회귀 2개.
- 원본 검증 9개는 로컬에서 생성한 **동일 구조의 합성 fixture**를 사용해 실행했으며, 별도로 위 실제 GitHub 6개 파일은 커넥터에서 직접 읽어 대조했다. 따라서 40개 실행이 실제 원본 데이터에 대한 Python 테스트였다는 뜻은 아님.
- GitHub 브랜치를 clone/check out하거나 GitHub Actions를 실행하지 않았으며, 저장소의 **모든** 테스트 파일을 실행한 것도 아님. 해당 수치는 사용 가능한 `test_offline_*.py` 집합에 한정.
- 네트워크 API 호출, Telegram 발송, 실 재고 조회 없음.

## 결론과 활성화 조건
CU 91개와 이마트24 제주 점포에 대한 신뢰 가능한 재고 API 점포 코드가 여전히 없으므로 자동 등록/수동 승인/제주 활성화 불가. 기존 첫 재고/증가/감소/품절 알림 및 조회 실패 시 상태 유지 정책은 변경하지 않음.

## 보호 범위
모든 쓰기는 `permission-test-20261013-cu`의 `tests/`와 `docs/`만 해당. `main`, GS25, 운영 워크플로, 실 재고 API, Telegram은 변경하거나 실행하지 않음.
