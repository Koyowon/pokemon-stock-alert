# CU 증거 승인 경계: 실제 커밋 테스트 실행 및 추가 안전성 검증

일자: 2026-10-13. 브랜치: `permission-test-20261013-cu`.

## 범위

GitHub 원본 `tests/cu_evidence_transition_policy.py` (SHA `937b1938093d452b7f13783aa967c569edcabd82`)와 `tests/test_cu_evidence_transition_policy.py` (SHA `7c3d03e008b247976c92848d644e84bb9d2b5f48`)를 실제 내용 그대로 격리된 Python 작업 디렉터리에 저장. 운영 파일, 상태, 레지스트리, main()을 import 또는 실행하지 않음. 네트워크 요청 없음.

## 실행

```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s . -p 'test_cu_evidence_transition_policy.py' -v
# Ran 12 tests, OK

PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s . -p 'test_cu_evidence*.py' -v
# Ran 18 tests, OK
```

두 번째 명령에는 새 파일 `tests/test_cu_evidence_approval_safety.py`의 6개 테스트 포함. 새 테스트는 로컬에서 실행한 동일 내용을 작업 브랜치에 추가함. GitHub Actions는 실행하지 않음.

## 확인된 보안 경계

- `assess()`는 승인자의 실제 권한을 확인하지 않음. `reviewer`와 `approval_reference`의 비어 있지 않은 문자열 및 `explicit=True`를 확인할 뿐.
- 합성 증거가 `SUFFICIENT`로 판정되는 경우, 임의의 승인자 이름과 임의 참조 문자열로 `APPROVED_FOR_REVIEW_ONLY` 상태를 만들 수 있음. 이 동작을 안전성 테스트에서 재현함. **권한 검증 성공이 아니라 설계상 위험의 확인**임.
- 현재 함수는 이 경우에도 `production_activation=False`, `same_location_confirmed=False`를 반환함. 단, 후속 호출자가 `state`만 보고 운영 활성화하면 안전성이 깨질 수 있음.
- 잘못된 점포 코드, 공백 승인자, 문자열 `explicit='true'`, 충돌 증거는 보류 처리됨.
- 증거의 `source_verified`, `independent_review`도 호출자가 전달하는 불리언으로, 독립적인 증빙 검증은 하지 않음.

## 권장 안전성 설계 (미구현)

1. 검토 상태 이름 `APPROVED_FOR_REVIEW_ONLY`와 실제 운영 활성화 권한을 분리하고, 운영 모듈에서 이 상태를 승인 토큰으로 취급하지 못하게 명시적 인터페이스 차단.
2. 승인자 신원·권한을 독립된 신뢰 경계에서 검증하고, 승인 범위(점포 코드, 주소 증거, 버전, 만료, 결정)를 고정.
3. 증거의 출처·기준일·원문 해시·상충 근거를 독립 검증하고, 호출자가 전달한 `True`만으로 `SUFFICIENT`를 확정하지 않음.
4. 권한 없는 승인자·조작된 참조·재사용된 승인·서로 다른 점포 간 승인 재사용·증거 변경 이후 기존 승인 재사용을 모두 거부하는 후속 테스트 필요.
5. 별도 사용자 승인 전까지 운영 파일 수정이나 실제 API 호출, Telegram 발송, Actions 실행 금지.

## 변경

추가 안전성 테스트 파일과 이 문서만 작업 브랜치에 신규 추가. 기존 운영 코드·상태 파일·레지스트리·`main` 브랜치 변경 없음.
