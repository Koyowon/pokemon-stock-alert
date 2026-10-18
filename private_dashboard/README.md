# 공용 비밀번호 대시보드: 배포 준비안

**아직 비밀번호 서비스는 배포되지 않았고, 기존 GitHub Pages와 원본 저장소는 공개 상태다.**
이 코드는 관리형 호스팅(Render 등)에서 실행하는 서버다. 사용자가 PC를 켜둘 필요는 없다. 재고 모니터는 기존 GitHub Actions에서 계속 실행하고, 서버는 저장된 JSON만 읽는다. 실제 재고 API나 텔레그램 API를 호출하는 코드는 없다.

## 동작

- 페이지, 스크립트, 재고 JSON 모두 서버 인증 뒤에만 제공한다. 브라우저에서 공개 GitHub raw 파일로 우회하지 않는다.
- 공용 비밀번호는 호스팅 비밀 환경변수에만 설정한다. 소스·HTML·로그에 저장하지 않는다. 시작 시 scrypt로 비교 키를 만들고, 로그인 때 상수 시간 비교한다.
- 로그인 쿠키는 HttpOnly/Secure/SameSite=Strict이고 최대 12시간 유지한다. 비밀번호 또는 세션 비밀을 바꾸면 기존 세션도 거부한다. 로그아웃하면 브라우저 쿠키를 지운다. 공용 비밀번호이므로 사람별 차단은 지원하지 않는다.
- 로그인은 같은 출처의 POST만 허용하며 한 서버 프로세스에서 분당 10회로 제한한다. 이 제한은 프로세스 재시작 시 초기화되며 여러 인스턴스 간 공유되지 않는다. 제안 배포는 인스턴스 1개다.
- 저장소가 비공개인지 GitHub API로 확인해야 데이터가 열린다. 확인 실패 또는 공개 저장소이면 503으로 차단한다. 비공개 확인은 최대 60초만 재사용한다.
- 정해진 JSON 파일과 UI 파일만 제공한다. 임의 파일·디렉터리·업스트림 URL은 전달할 수 없다. 보호 응답에 no-store를 적용하고 외부 출처에 CORS를 허용하지 않는다.
- 호스팅 상태 검사 `/healthz`와 로그인 화면만 인증 없이 열리며 재고는 포함하지 않는다.

## 실제 전환 전에 필요한 설정

1. Render 연결 및 GitHub 저장소 연결. 제안 설정은 `private_dashboard/render.yaml`, Dockerfile은 `private_dashboard/Dockerfile`. 배포할 작업 브랜치를 선택한다. 자동 배포는 끈다. 비용·계정 조건 확인 없이 유료 자원을 만들지 않는다.
2. 서버에서 읽을 저장소를 비공개로 전환하거나 비공개 데이터 저장소를 마련한다. 새 저장소를 쓴다면 기존 모니터도 그곳에 상태를 저장하도록 별도 변경해야 한다. 현재 공개 파일을 그대로 두고 새 페이지만 잠그는 것으로 비공개 완료를 선언하지 않는다.
3. 저장소 읽기만 가능한 GitHub fine-grained 토큰을 호스팅 비밀 설정에 입력한다. Contents 읽기 및 저장소 메타데이터 읽기만 필요하다. 쓰기·Actions 실행·관리 권한은 필요하지 않다.
4. 공용 비밀번호(16자 이상, 무작위 긴 비밀번호 권장)와 SESSION_SECRET(32자 이상)을 호스팅의 비밀 환경변수에 설정한다. 채팅·GitHub 파일에 쓰지 않는다. `render.yaml`의 SESSION_SECRET은 호스팅이 생성한다.
5. `DATA_REPOSITORY=owner/repository`, 선택적으로 `DATA_REF=main`을 설정한다. Render의 `RENDER_EXTERNAL_URL`을 로그인 출처로 사용한다. 다른 호스팅이나 별도 도메인은 HTTPS `PUBLIC_ORIGIN`을 설정한다.
6. 새 주소에서 비인증 페이지·JSON 차단, 잘못된 비밀번호, 정상 로그인, 만료·로그아웃 및 실제 저장 데이터 읽기를 검증한다.
7. 새 주소 확인 후 기존 공개 Pages를 중지한다. 원본 저장소·다른 공개 데이터 경로도 더 이상 우회 경로가 아닌지 확인한다. 이미 공개된 과거 사본을 회수하는 기능은 아니다.

GitHub 저장소의 공개/비공개 설정 변경과 기존 Pages 종료는 자동으로 수행하지 않았다. 코드 준비만으로 현재 사이트가 보호되는 것은 아니다.

## 비용과 운영

Render 무료 웹 서비스는 유휴 15분 뒤 멈췄다가 다음 접속 시 다시 시작해 초기 로딩이 지연될 수 있다. 재고 감시는 GitHub Actions가 담당하므로 웹 서버의 유휴 정지와 분리된다. 요금제·사용량 한도는 계정에서 확인해야 한다. 제안 파일이 `plan: free`여도 모든 부가 사용량의 무과금을 보장하지는 않는다.

공식 문서:
- https://render.com/docs/web-services
- https://render.com/docs/free
- https://render.com/docs/configure-environment-variables
- https://render.com/docs/environment-variables

## 오프라인 검증

`node --test tests/test_private_dashboard.mjs tests/test_stock_health_model.cjs tests/test_stock_map.cjs`

인증 테스트는 localhost HTTP 및 모의 GitHub 응답만 사용한다. 실제 GitHub 토큰·재고 API·텔레그램·호스팅 배포는 사용하지 않는다.
