# 관리자 기능 통합 배포 검증

work_id: 20261112-007-admin-staging-release

| 단계 | 배포 전 확인 |
|---|---|
| 1. 거버넌스 | 기존 단일 기록기가 쓰는 동안 첫 확인이 경합했다. 건강 상태가 정상인 같은 PID를 유지한 채 재시도해 성공했다. 정책 검증 44개 노드, 오류 0건이다. |
| 2. 요구 범위 | 가입 이름, 접근 로그 유휴 만료, 읽기 전용 AI 기록, 관리자 계정 생성, 보안 감사 행위자 표시를 한 번에 배포한다. |
| 3. 논리 | 감사 로그 목록·상세·행위자 검색에 표시되는 값과 실제 사용자 식별자를 대조한다. |
| 4. 운영 영향 | 운영 커밋과 종전 미커밋 변경을 확인한다. 사용자 세션, 현재 로그 정리, AI 워커의 상태를 전환 전에 확인한다. |
| 5. 권한 | 관리자 전용 기능은 기존 권한과 현재 세션을 검증한다. 운영 대화 내용이나 비밀번호를 점검 산출물로 내보내지 않는다. |
| 6. 복구 | 코드 버전과 서버 전용 온라인 DB 백업으로 돌아갈 수 있게 한다. 조회 표시를 위한 과거 감사 행 갱신은 필요 없다. |
| 7. 화면 | 이름 있는 회원, 이름이 빈 회원, 시스템 활동과 PC·모바일 관리자 화면을 대조한다. |
| 8. 작업자 | 지정된 확장 컨텍스트 CLI가 분담하고 총괄만 Git 배포 및 서비스 전환을 수행한다. |

## 2026-11-12 추가 실행 및 배포 검증 (ChatGPT + Remote Desktop Commander)

- 작업 대상: `NKHST-5650U\C:\Project\Mini-Server-Web-EqMgmt`; 원격 Linux 호스트 `eqmgmt-backup`.
- 작업 범위: 기존 세 Staging 패치의 통합과 감사 행위자 표시 수정. 운영 DB 스키마 변경과 과거 감사 행 수정은 없음.
- Windows 거버넌스: `governance-tool.mjs validate` PASS, errors 0, warnings 0. `context`는 최초 `**` 와일드카드 실제 경로 오류를 수정하여 정상 선택, 관련 규칙을 확인함.
- 기존 Staging 소스 원장: 감사 SQL 수정을 제외한 23개 파일의 SHA256을 대조하여 모두 동일. 세 패치 모두 `git apply --reverse --check` 성공.
- 감사 행위자: `NULLIF(TRIM(u.Name),'')`에 의한 공백/빈 이름 복구와 로그인 ID 대체, 시스템 표시 유지. `ActorName` 검색에도 같은 SQL 사용. Windows SQL 회귀 5/5, Linux 독립 API 추출 회귀 6/6.
- 통합 Linux 격리 시험: Python 323/323 PASS, failure 0, error 0, skipped 0. 합성 임시 SQLite `/dev/shm` 사용, 운영 애플리케이션 import/운영 DB 접근 없음.
- Linux Node/Chromium UI·로직 시험: 34/34 PASS, failure 0, skipped 0. 320px·1280px 관리자 계정 생성 UI 검증 포함. Windows에서는 Playwright 미설치로 1파일 실패했으나 Linux 환경에서 의존성 확보 후 통과.
- Linux 전체 브라우저 하네스의 별도 실행은 테스트용 Flask 엔드포인트 `logout` 누락으로 실패했으므로 성공 근거로 사용하지 않음. 별도 Node/Chromium 34개 통과와 동일하지 않음.
- Git: 대상 26개 파일만 별도 스테이징/커밋; `git diff --cached --check` 통과. 로컬/원격/운영 HEAD는 `b8192a1a8579eb0f2f408dc4ed223863dabe3df5`, 부모 `920edeffbb9642eb3cc77f244f325af6d4a2336f`. 기존 다른 미커밋 파일들은 포함하지 않음.
- Linux 운영 전환: 2026-11-12 17:12 KST, 서버 Git Fast-forward `920edef` → `b8192a1`; 운영 전환 파일 `instance/releases/admin-007-3261f405e468/result.json` 보고 상태 `active`. 웹 PID `1823510` → `1847149`, AI 워커 PID `1653197` 유지.
- 운영 전환 백업: `instance/releases/admin-007-3261f405e468/equipment-before.sqlite3` 413,237,248 bytes / `assistant-before.sqlite3` 1,232,896 bytes. 각 SQLite integrity=ok, FK 위반 0. 운영 기록에 사용자 행 8, 세션 8, AI 작업 행 54 보존 확인. 백업 파일은 서버 내 비공개 경로에 유지.
- 실제 HTTP: `/login` 200, `/register` 200. 비로그인 `/admin_center`, `/audit_logs`, `/users_management` → 302; `/api/audit_logs` → 401; GET `/api/users/create` → 405. 실제 운영 `app.py`의 감사 행위자 SQL 존재 및 서버 tracked Git tree clean 확인. 워커 서비스 active.
- **미완료**: 정상 로그인된 관리자 계정으로 운영 관리자 UI, 실제 데이터 조회, 감사 행위자 표시 및 관리자 계정 생성 폼을 직접 확인하지 못함. 공개/익명 경로 및 격리 브라우저 시험을 운영 인증 테스트로 표현하지 않음.
- 비용·사용량: 독립 작업자 별 토큰 사용량/비용 영수증 확보 불가. QuotaMonitor 설정·서비스 변경하지 않음.
- 잔여 작업: 관리자 세션을 가진 운영 브라우저에서 기존 데이터 조회 중심의 비파괴 동작 검증. 실제 신규 계정 생성은 운영 데이터 변경이므로 별도 시험 계획에 따라 승인된 테스트 계정과 삭제/보존 조건 확정 후 실시.
- 롤백 기준: 서버 Git 직전 버전 `920edef`, 배포 전 두 SQLite 온라인 백업 및 `result.json`. 장애 발생 시 웹 PID/쓰기 작업 상태·Git tracked tree/세션 상태를 재확인하여 기존 승인된 원복 절차를 사용; 현재는 롤백 불필요.

## 실제 수행 결과 (2026-11-12, ChatGPT / Remote Desktop Commander)

**변경 범위:** 사용자 요청으로 Codex 기존 작업을 직접 인수했다. Codex CLI 신규 작업자 호출은 0건이며 QuotaMonitor 코드는 변경하지 않았다. 기존 미커밋 문서와 다른 프로젝트는 보존했다.

### 1. 감사 로그 행위자 표시·검색

- 원인: COALESCE(u.Name, a.ActorLoginId, 'System')는 빈 문자열을 NULL로 인식하지 않는다.
- 수정: NULLIF(TRIM(...), '')를 적용하여 이름이 정상적으로 있으면 그대로 유지하고, 이름 없음/공백/NULL일 경우 실제 로그인 ID를, 진짜 시스템 작업에는 System을 반환한다. 목록·상세·ActorName 컬럼 검색에 같은 SQL 식을 사용한다. 데이터/DB 스키마 수정은 없다.
- 검증: 합성 SQLite 및 소스 대조 5/5, 실제 Flask API 함수 AST를 별도 추출한 목록·검색·권한 시험 6/6(Windows와 Linux). 외부 Codex 교차 검토 대신 독립적인 시험 경로를 사용했다.

### 2. 세 Staging 패치 통합 및 기능 회귀

- 회원가입 이름 (선택), 웹 접근 로그 자동조회 유휴 만료, 관리자 AI 기록 조회, 관리자 사용자·관리자 계정 생성의 기존 패치를 구조화된 편집 수단으로 병합했다. 세 패치 모두 git apply --reverse --check 통과.
- 기존 Staging 원장 24개 대상 중 수정 app.py를 제외한 23개 파일의 바이트 또는 CRLF 정규화 SHA-256이 일치하여 내용 불일치 0건이었다.
- 격리된 Linux tmpfs에서 **Python 323개 전부 통과(실패/오류/건너뜀 0)**. Linux Node/Chromium 34개 전부 통과(건너뜀 0). Node 시험은 계정 생성 실제 브라우저 320px·1280px, 중복 제출 및 오류 표시도 포함한다.
- 전체 관리자용 별도 브라우저 fixture는 축약 Flask 시험 앱에 logout 라우트가 없어서 테스트가 끝나지 못했다. 실제 제품 장애로 판정하지 않으며 해당 실행을 성공으로 집계하지 않는다.

### 3. Git 및 온라인 백업

- 26개 허용 파일만 명시적으로 스테이징했다. UTF-8 Git 파일명 대조로 허용 26개/실제 26개/예상 밖 0건 확인. diff, Python AST, JavaScript 구문, 거버넌스(44 노드 오류 0), Conventional Commit 검증 통과.
- Windows와 GitHub main 기능 커밋: **b8192a1a8579eb0f2f408dc4ed223863dabe3df5**. 직전 기준 **920edeffbb9642eb3cc77f244f325af6d4a2336f**. 기존 전역 Git 작성자 설정을 변경하지 않았다.
- Linux 직전 웹 PID 1823510, AI 워커 PID 1653197, 진행 중 AI 작업·가드 모두 0건, 점검 NORMAL, 저장 대기 구형 spool 없음 확인.
- private 릴리스 폴더: instance/releases/admin-007-3261f405e468/. SQLite 온라인 백업: 장비 DB 413,237,248바이트 및 AI DB 1,232,896바이트. 양쪽 무결성 ok, 외래 키 위반 0건. SHA와 상세 증명은 같은 폴더의 비공개 증거 및 첨부 JSON에 있다.

### 4. 운영 적용 및 검증

- 웹을 정상 SIGINT로 종료하고 Git fast-forward 후 신규 PID **1847149**를 실행했다. 1.629초에 readiness 확인. AI 워커 **1653197**은 교체하지 않았다.
- 기존 사용자 8행과 로그인 세션 토큰 8개, AI 작업 행 54개의 전체 지문 일치. 두 운영 DB의 무결성/외래 키 검증 통과.
- 실제 HTTPS 경로 10/10 통과. 로그인·회원가입 HTTP 200, 회원가입 페이지 이름 (선택) 표시 확인. 관리자/사용자 관리/감사/AI 기록 접근은 비로그인 상태에서 302 또는 401, 무인증 계정 생성은 401이었다.
- 운영 DB에 AI 도우미 기록 메뉴 1개와 권한 admin/IsAllowed=1 등록을 확인했다. AI 대화 28개, 메시지 108개, 작업 54개 보존 및 워커 active 확인.
- **남은 UI 검증:** 기존 Chrome의 관리자 로그인 세션에 접근할 수 없어, 실제 운영 관리자 자격으로 로그인한 브라우저에서 AI 기록 조회·계정 생성·행위자 검색을 직접 클릭하는 양성 시나리오는 시험하지 않았다. 해당 테스트를 완료로 주장하지 않는다. 운영 계정 생성이나 260Strata 모델 요청은 수행하지 않았다.

### 5. 증거·사용량·복구

- [검증 구조화 원장](007_Admin_Staging_Release/verification.json)
- [운영 배포/복구 게이트 코드](007_Admin_Staging_Release/deploy_admin_007.py)
- [운영 HTTPS 무인증 검사](007_Admin_Staging_Release/verify_live_http.py)
- [운영 SQLite 읽기 전용 검사](007_Admin_Staging_Release/verify_live_db_007.py)
- [Linux Node/Chromium 격리 검사](007_Admin_Staging_Release/run_node_qa.py)
- [비공개 SSH 실행 래퍼](007_Admin_Staging_Release/run_deploy_007.py)
- Codex 주간 잔여율은 이번 세션에 앞서 QuotaMonitor에서 0%로 확인했으며 Codex CLI 신규 호출 0건이다. 이 채팅과 외부 도구의 별도 토큰 소모는 측정하지 못해 수치를 추정하지 않는다.
- 배포 스크립트는 시작 실패 시 기존 Git 버전으로 복귀하고 데이터베이스를 과거 스냅샷으로 덮어쓰지 않도록 보호한다. 사후 문제 발생 시 새 업무 기록이 생성됐는지 확인한 뒤 기존 코드 커밋과 private 백업을 기준으로 별도 복구한다. 비밀번호와 인증 토큰 자체는 보고서에 보관하지 않았다.

### 구현 후 Validation 1~8

1. 거버넌스 44개 노드 오류 0; 기존 dirty 변경 보존.
2. 사용자가 승인한 다섯 관리자 기능만 대상.
3. 감사 목록·상세·검색의 행위자 표시와 역할 경계 일치.
4. 기존 웹만 교체, AI 워커 및 운영 데이터 보존.
5. 미인증 접근 차단과 사용자 생성 권한·CSRF·감사의 합성 검증.
6. 원본 커밋·SQLite 비공개 온라인 백업·복구 코드 보존.
7. Chromium 320/1280 화면 통과, 실제 운영 인증 UI 클릭은 별도 확인 필요.
8. 관측 사실, 실측 불가, 보류 작업을 구분; Codex CLI 신규 작업자 0.
