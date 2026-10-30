# Strata AI 관리자 메뉴 구현 후보

이 디렉터리는 사용자 요청으로 구현한 Staging 후보다. `overlay/`의 파일은 승인 후 프로젝트의 같은 상대 경로에 추가하고, `candidate.json`의 세 가지 변경을 `app.py`에 적용한다. 기존 `app.py` 해시와 교체 지점이 일치할 때만 병합한다. 신규 파일 경로와 충돌하면 덮어쓰지 않고 다시 검토한다.

## 포함 기능

- 관리자용 `/ai` 메뉴와 기존 공통 내비게이션을 유지한 iframe 화면.
- 활성 로그인·현재 DB 역할·메뉴 권한·기능 스위치 검사.
- 전용 `/strata/` 경로의 메서드·경로 허용 목록과 POST CSRF·Origin 검증.
- API 키를 응답하지 않는 Nginx 인증 확인 경로.
- 원본 Strata UI 고정 사본, 관리자 로그인 연계와 세션별 대화 저장소.
- API 키의 브라우저 저장·전송 차단, 계정 전환·접근 거부 시 저장소 정리.
- 260 연결·모델 대기·재시도 안내와 스트림 중계용 Nginx 예시.
- 보호된 Nginx 키 include 생성 도구, Linux 격리 테스트와 적용·롤백 문서.

## 확인 상태

Windows에서는 `check_candidate.py`가 앱 import·DB 열기·서버 실행 없이 Python AST, JavaScript 문법, Jinja 문법, 통합 지점과 구성 정적 조건을 검사한다. Linux Python 테스트 23개와 브리지 테스트 6개는 실제 동작 검증용으로 준비했으며, 신뢰된 Linux 접속에서 실행해야 한다.

프로젝트의 Staging 결과 승인 규칙에 따라 현재 운영 소스는 변경하지 않았다. 백업 Linux 서버에는 현재 PC와 260 모두 신뢰된 SSH 호스트 키가 없어 접속하지 못했다. 호스트 검증을 끄거나 서버 키를 임의 등록하지 않았다.

실제 적용은 `overlay/docs/strata-integration.md`를 따른다. 기능 기본값은 비활성이다. 원본 Strata API 키를 Git이나 이 후보 디렉터리에 넣지 않는다.
