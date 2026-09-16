# 카탈로그 UI 백업서버 Git 정합성 및 재시작 보고서

- work_id: WORK-20260915-UI-CONSISTENCY-CATALOG-REQUESTS
- 사용자 승인: 2026-09-16T00:04:01Z, commit/push → 백업서버 pull → 재시작.
- 시작 상태: Windows/원격 ac88fa082817a1a76c449497b3b9b849afbc48d5 clean; 서버 HEAD5ab042a, dirty 운영 소스, PID91637 별도 Python 웹앱.
- SSH는 Windows 프로세스에 PROGRAMDATA를 보완하여 정상 연결. 개인키·authorized_keys·서비스 구성 변경 없음.

## 사전 검증
- recorder ensure 오류0, governance 1.7.0 errors0/warnings0, 이번 배포/검토 context와 기존 동일 노드 확인.
- 실제 Jinja 템플릿 + Edge/Chromium 브라우저 전체 회귀를 실행했다. 구 포털 폭/열 수 기대값 한 사례만 신규 승인 규격과 불일치했다.
- 애플리케이션 코드는 변경하지 않고 테스트5곳(설명1/기대값4)만 정정했다. Standard 1280px/4열, Edge18rem 기준1920px6열/2560px8열. 실제 결과와 일치한다.
- 최초 검증: 하위 사례1개 실패 및 그 상위 suite 실패. 정정 후 전체26건 통과, 실패/skip0, 실행88초.
- 테스트 원자 교체의 Windows WinError5 이후 구조화 move로 원본을 보존하고 준비된 후보를 적용했다. 권한/보안 설정은 변경하지 않았다. 원본: catalog-ui-release/browser-contract-before.mjs.
- Git diff로 승인된 기대값만 바뀌었음을 확인했다. 일반 Python 배포 도구는 AST 검사 후 사용한다.

## 배포 안전 경계
- 서버 코드 전체 hash를 전일 실배포 기준 b637c79와 비교하고, 예상 밖 수정이 있으면 실행하지 않는다.
- Git 밖 private 디렉터리에 코드·Git index/diff·운영 DB snapshot을 보존한다.
- 확인된 운영 소스 경로만 Git stash -u로 보존한 뒤 ff-only pull한다. .venv.incomplete 및 DB/비밀은 stash 대상이 아니다.
- Linux 전체 격리 회귀 및 신규 카탈로그 HTTP 경계를 확인한 뒤 실제 기존 명령/환경으로 새 PID를 시작한다. 비활성 systemd unit은 건드리지 않는다.
- 실패 시 보존된 코드로 서비스를 복구한다. 업무 DB 전체 자동 복원은 하지 않는다.
- 실운영 카탈로그 신청/승인 등 업무 데이터 쓰기를 성공 확인용으로 수행하지 않는다.

현재 상태: 배포 도구 및 테스트 정정 준비 완료. commit/push 및 서버 적용 결과는 아래 후속 절에 실제 수행 후 기록한다.

## 사전 적용 점검 보완
- edac767443e415d2c0b01ac440bef757a53d3cdd commit/push 완료 후 서버 사전 검사에서만 중단됐다. 서버 Git fetch 이외의 파일/stash/프로세스/DB 변경은 없었다.
- Resources/EqMgmt.ico의 실제 원시 SHA256은 Windows Git 원본과 서버 모두 22f8657d930bac615948356fdf2d9bcd95e5d7b09291970408e91549c34e02eb로 같았다.
- 배포 controller가 바이너리를 UTF8 문자열로 디코딩해 비교한 오류였다. v2는 byte 보존 변환으로 Python의 byte-level 비교와 일치시켰다. 애플리케이션 코드 및 icon은 변경하지 않았다.
- 최초 오류 결과는 catalog-ui-release/preflight-result.json에 보존한다. v2는 별도 결과 파일로 남긴다.

## 실제 백업서버 배포 완료 (2026-09-16 09:20 KST)
- 코드 적용 commit: 5b60d5b63b7f46a20b0817fa44ecfae7e6231c75. 기능 commit6862c78을 포함하며 이후 변경은 테스트/배포 도구/문서다.
- 사전 점검: 운영 파일65개 중 기존61개가 b637c79 실배포본과 동일, 신규4개만 없었다. 설명되지 않는 변경0.
- private 복구 위치: /home/nekohost/.local/share/mini-server-eqmgmt/releases/catalog-ui-git-20260916T002004077523Z.
- 기존 운영 코드·Git index/diff/status 및 equipment-before.db를 보존했다. 확인된30개 미커밋/미추적 소스는 stash af29c05b3b2e86abae742f8b4a9c7e27e65c9805에 추가 보존했다. stash는 유지하며 재적용하지 않았다.
- git pull --ff-only origin main 성공. HEAD가 목표와 일치하고 전체65개 운영 파일 hash가 동일하다.
- 실제 프로세스는 .venv/bin/python -u app.py였다. PID91637을 SIGTERM으로 정상 종료한 뒤 동일 명령/환경의 PID119262로 시작했다. 비활성 mini-server-backup.service의 상태는 변경하지 않았다.
- Linux unittest discover: 99건/15.525초/OK, exit0. 임시 DB/작업/첨부 경로를 사용하며 실행 중 운영 DB10개 확인 테이블은 변하지 않았다.
- 추가 실제 Flask 격리 HTTP 검사19건 PASS: 401/CSRF403/JSON400/중복409, 카테고리·제조사·노드 접수, 본인 결재함, 미승인 의존성 거부, 권한 위조/사용자 승인 거부, 관리자 즉시 등록, 감사 실패 원자적 rollback, 관련5페이지 Jinja 렌더.
- 재시작 후 integrity_check=ok, foreign_key_check=0. 사용자·장비·옵션·노드·카테고리·제조사·결재·메뉴·권한·마이그레이션10개 테이블의 전체 행 hash가 배포 직전과 동일하다.
- 실제 localhost 및 HTTPS nekohost.org의 /login, 신규 CSS/JS는200, 비로그인 /api/catalog_requests POST 및 /api/my_approvals GET은401이다.
- 변경된 정적자산3개 실제 HTTP 응답 hash가 Git 목표와 일치한다. 새 프로세스 기동 로그의 Traceback/ERROR/FATAL 없음.
- 서버 추적 작업 트리는 clean. 기존 .venv.incomplete-20260907/는 미추적 보존 artifact로 그대로 남았다.
- 운영 계정으로 카탈로그를 신청/승인하거나 장비값을 변경하지 않았다. 로그인 후 사용성은 실제 템플릿의 격리 브라우저 검사이며 실사용자 로그인/실기기 검증으로 표현하지 않는다.

## 실행 증거
- catalog-ui-release/preflight-v2-result.json: 서버 preflight 승인 상태/대상 경로.
- catalog-ui-release/deployment-v2-result.json: pull·백업·stash·새 PID·DB 보존·정적 hash의 실제 결과.
- catalog-ui-release/postflight.json: 외부/내부 HTTP와19개 격리 HTTP 결과. 이 파일의 tests 배열은 최초 정규식 추출 실패로 비어 있다.
- catalog-ui-release/linux-test-summary.json: 로그에서 직접 다시 추출한 최종99건/OK. 로그 원본은 서버 private release/linux-tests.log에 남긴다.
- 완료 문서 commit은 위 코드 적용본에 대한 기록만 갱신한다. 해당 commit의 서버 pull 시 운영 코드 차이가0인지 확인하고 불필요한 추가 재시작은 하지 않는다.

최종 판정: 운영 코드·Git 원격·백업서버 적용 및 실제 웹앱 재시작 완료. 복구는 필요하지 않았으며 복구본과 stash를 보존했다.
