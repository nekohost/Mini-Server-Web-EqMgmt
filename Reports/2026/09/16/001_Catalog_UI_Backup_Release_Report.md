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
