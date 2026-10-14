# CU·이마트24 증거 접수 사전 검증 절차 — 2026-10-14

## 1. 문의 및 증거 수집
공식 문의 초안: `docs/cu_emart24_official_store_id_inquiry_drafts_20261014.md` (미발송).

확인 가능한 점포 식별자와 점포명·주소의 연결이 공식 공개 문서로 증명될 때에만 `docs/store_code_evidence_intake_template_20261014.csv`를 복사해 새 증거 CSV를 작성한다.

필수 열: `chain,registry_id,store_code,name,address,source_url,observed_at,barcode`.

- `chain`: `cu` 또는 `emart24`.
- `registry_id`: CU는 `asan_cu_watch_registry.json`의 실제 후보 ID. 이마트24는 비워도 됨.
- `store_code`: 확인된 실제 점포 코드. 미확보 시 **빈 값**; 절대 추정하지 말 것.
- `name,address`: 원문 점포명·주소. CU는 기존 후보와 정확히 대조.
- `source_url`: 점포코드와 해당 점포의 연결을 확인할 수 있는 공개 공식 URL. 단순 점포 검색 링크만으로는 부족.
- `observed_at`: 확인 날짜 `YYYY-MM-DD`.
- `barcode`: `8800286275732`만 허용.

## 2. 오프라인 검사
저장소 루트에서:

```bash
python tests/offline_evidence_preflight_cli.py docs/store_code_evidence_intake_template_20261014.csv --root .
python -m unittest discover -s tests -p 'test_offline_*.py' -v
```

출력 `approved`는 항상 **0**. `MANUAL_REVIEW_REQUIRED`도 실제 공식 증거의 진위를 보증하지 않음. 최종 수동 승인·운영 등록 절차는 별도로 필요.

주의: 이 CLI는 코드가 없는 행은 `BLOCKED_NO_CODE`로 분류하며, 저장소 운영 상태를 변경하거나 재고 API/Telegram에 접속하지 않는다. 개인 연락처, 상담 접수번호, 비공개 회신 원문을 공개 저장소에 업로드하지 않는다.

## 3. 이번 로컬 검증
- GitHub 원문과 로컬 파일의 Git blob SHA를 비교한 기존 4개 오프라인 파일은 일치.
- 새 CLI 및 3개 통합 테스트도 GitHub 원문과 로컬 Git blob SHA가 각각 일치.
- 저장소 원본 JSON/CSV를 담은 격리 로컬 스냅샷에서 `python -m unittest discover -s /mnt/data/cu_emart_full_offline/tests -p 'test_offline_*.py' -q` 실행: **46 tests, OK**.
- 46개는 격리 폴더에 존재하는 `test_offline_*.py` 파일에 한정. GitHub Actions 및 전체 저장소 테스트를 실행한 것은 아님.
- 신규 CLI 실데이터 기반 테스트: 빈 증거 입력 0건 승인, 실제 CU 후보 코드 누락 차단, 제주 가상 fixture 코드 누락 차단.
- 신규 검증 코드 0, 운영 등록 0.

## 4. 보호 범위
`permission-test-20261013-cu`의 `tests/` 및 `docs/`만 수정. `main`, GS25, 운영 워크플로, 운영 감시 코드·설정·상태, 실 재고 API, Telegram 변경·실행 없음. 기존 증가·감소·품절 알림 및 미관측 시 상태 보존 정책 유지.
