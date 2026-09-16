# 카탈로그 UI 백업서버 Git 정합성 및 배포 계획

- work_id: WORK-20260915-UI-CONSISTENCY-CATALOG-REQUESTS
- 승인: 사용자 2026-09-16T00:04:01Z commit/push → 백업서버 pull → 서비스 재시작 명시 지시.
- 기준: Windows/원격 ac88fa082817a1a76c449497b3b9b849afbc48d5, clean. 서버 HEAD 5ab042a, PID91637 별도 Python 웹앱.
- SSH: 프로세스 로컬 PROGRAMDATA 보완으로 Windows agent 재사용. 키/인증 정책 변경 없음.
- 기존 Task: Tasks/2026/09/15/001_UI_Consistency_Catalog_Requests_Task.md.

## 실행 및 보존
1. 현재 소스·실제 템플릿 브라우저 재검증. 포털 열 수/폭의 구 규격 기대값만 승인된 관리자 기준으로 정정한다.
2. 애플리케이션 변경 없이 검증 및 배포 계획을 commit/push한다. 다른 작업자 변경이 있으면 중단한다.
3. 서버에서 정확한 목표 commit을 fetch하고, dirty/미추적 운영 파일이 b637c79 배포본과 같은지 재검사한다.
4. 코드·Git 상태·DB를 private release 폴더에 보존한다. .env/프로세스 환경은 출력/Git 저장 금지.
5. 명시적으로 확인된 운영 소스 경로만 stash -u로 보관한다. .venv.incomplete 등 무관한 파일은 제외한다. stash를 삭제하거나 자동 재적용하지 않는다.
6. 기존 프로세스 종료 후 ff-only pull, exact HEAD/소스 해시 확인, Linux 격리 회귀를 수행한다. 운영 DB를 테스트에 사용하지 않는다.
7. 기존 프로세스의 명령/환경 그대로 새 PID를 시작한다. 비활성 systemd unit을 시작해 중복 서버를 만들지 않는다.
8. 실패 시 같은 실행 환경에서 보존한 코드로 서비스 복구하고 실패를 보고한다. 업무 DB 전체를 자동 과거 복원하지 않는다.
9. HTTP/static/API·DB integrity/FK/업무 행 보존 확인 후 Task/Report/FEATURES에 실제 결과를 기록한다.

## Validation 1~8 (배포 전)
1. 거버넌스: v1.7.0 검증 통과, 기존 전체 pack 및 배포 노드 승계. 명시 승인된 배포 범위다.
2. 의도: 신규 기능 추가가 아니라 전일 승인한 3개 UI 개선의 서버 적용이다.
3. 논리: Git HEAD와 운영 내용 불일치를 해시로 분류하고 지정 경로 stash로 비파괴 보존한다.
4. 운영: app.py의 신규 라우트 등록 외 기존 실행 설정/포트/사용자를 유지한다. 주 서버는 제외한다.
5. 보안: 비밀 출력/키 재등록/관리자 권한 확장 없음. 격리 API 검증에 합성 사용자만 쓴다.
6. 복구: 원본 코드 사본·Git stash·기존 HEAD·DB snapshot 보존, 잘못된 PID 종료 방지, 전환 실패 시 원본 코드 재시작.
7. UX: 기존 포털 규격 기대값을 현재 승인 규격으로 정정하고 템플릿 전 화면 회귀를 유지한다.
8. 메타: 사전 PASS를 배포 PASS로 혼동하지 않는다. 각 실제 수행 결과·오류·복구를 별도로 기록한다.
