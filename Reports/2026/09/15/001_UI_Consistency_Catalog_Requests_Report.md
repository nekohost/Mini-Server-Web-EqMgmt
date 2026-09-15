---
artifact_id: REPORT-20260915-001
work_id: WORK-20260915-UI-CONSISTENCY-CATALOG-REQUESTS
created_at: 2026-09-15T14:04:01.054+09:00
related_artifacts:
  - ../../../../Plans/2026/09/15/001_UI_Consistency_Catalog_Requests_Plan.md
  - ../../../../Tasks/2026/09/15/001_UI_Consistency_Catalog_Requests_Task.md
---
# UI 공통 규격·카탈로그 신청 검증 보고서

## 관찰 근거
- HEAD/remote main b637c79 동일, 초기 clean. v1.7.0/44 nodes/errors0/warnings0. Recorder ensure 오류 없음, 신규 기록0.
- index.html: 공개 배지는 이름 옆 text-[10px], Roadmap 상태 배지는 별도 줄 .75rem. 두 장비 화면은 같은 템플릿이다.
- portal.html: max-w-5xl/최대3열. admin_center: 기본 max-w-7xl/최대4열. layout.css Edge 폭 기본19rem/관리자18rem.
- 카드 본체는 menu_cards.js의 안전한 DOM renderer를 이미 공유한다.
- my_approvals.js는 본인 이력 조회 전용. 마스터 독립 신청 API는 없고 장비 custom 저장 경로에서 상신한다.
- lineup_node_service.create_node는 승인 마스터/부모·동일 조합·깊이50·중복·권한을 이미 검증한다.

## 코드 작성 전 Validation 1~8
### 1. 거버넌스
Plan/Task를 먼저 작성하고 27개 context 노드를 읽었다. 신규 의존성 없이 Staging만 변경한다. 원본 편집 도구의 빈 schema는 무리하게 우회하지 않고 exact overlay 후보로 대체한다. 운영 병합은 별도 gate다.
### 2. 사용자 의도
나의/공개/임시저장 배치를 함께 고친다. 카테고리·제조사·노드 3폼을 두 진입점에서 공유한다. 관리자 센터 카드 규격을 기준으로 한다. 버튼과 정보 배지의 역할까지 같게 만들지는 않는다.
### 3. 논리
노드 create_node 재사용, 마스터/결재/감사 동일 BEGIN IMMEDIATE. 클라이언트 중복 클릭 잠금, 취소 시 원래 장비값 유지, 비동기 응답 세대 검사. 이름 중복은 잠금 안에서 검사한다.
### 4. 운영 영향
스키마 변경 없이 기존 RequestType/Name/node_id 형식을 유지한다. 개인 조회 스크립트와 관리자 처리 권한은 보존한다. 공통 CSS는 명시적 컴포넌트 클래스만 대상으로 하고 위젯은 변경하지 않는다.
### 5. 보안·엣지
서버 인증·CSRF·메뉴 권한을 주입하고 actor는 session만 사용한다. 타입/길이/중복/미승인 부모/다른 루트 노드를 거부한다. JSON은 HTML로 삽입하지 않는다. UI 실패를 승인 성공처럼 표시하지 않는다.
### 6. 복구
운영 DB·서비스 미접근, 기존 소스 미변경. 신규 후보와 exact overlay가 diff/검토 대상이다. 향후 병합은 기준 SHA 재확인과 명시적 gate를 거친다. 기존 업무 DB 전체를 과거로 복원하는 방식은 사용하지 않는다.
### 7. 사용자 오류
장비 등록 form 밖 native dialog, 모든 진입 버튼 type=button. 필수값 안내, 의존 선택 변경 시 상위 노드 초기화, 요청 중 제출/닫기 잠금, 서버 실패 시 입력 보존, 성공 뒤 별도 닫기와 목록 새로고침을 제공한다.
### 8. AI 메타
이 보고서는 실제 파일/도구 결과만 근거로 한다. ChatGPT 대화 native 자동 수집이나 실제 저장 receipt를 주장하지 않는다. 다른 프로젝트·과거 Task는 수정하지 않는다. 정적 통과와 실제 운영 완료를 구분한다.

사전 결론: Staging 구현 진행 가능. 신규 UI의 실제 치수·이벤트·API 실행 결과는 구현 후 테스트로 판정하며 이 단계에서 PASS로 미리 기록하지 않는다.

## 2026-09-15 중단 후 재개 결과
- RDC 장치 NKHST-5800H가 online이며 실제 호출이 정상 수행됐다. 저장소 HEAD 및 실제 원격 main은 b637c79af1920e4255e5ccaad75fe63ccc9142c7로 유지된다.
- 중단 전 후보 9파일이 남아 있었다. 구현 전체가 유실된 상태가 아니며 Task/Report 최종 조율 이전에 응답이 중단된 상태였다.
- 재개 preflight: recorder ensure 오류0/신규기록0, governance 1.7.0/44 nodes/errors0/warnings0. continue-work를 포함한 context 재선택과 추가 handoff 노드 확인.
- 사용자 요청 3항목의 후보: 나의/공개/임시저장 장비명 아래 배지 행, 3종 독립 신청 공통 dialog, 관리자 센터 기준 포털 카드 배열.
- 실제 common.js의 getCSRFToken을 확인했다. 신청 스크립트가 존재하지 않는 helper를 가정한 상태는 아니다.

### 재개 중 보완
- 일반 신청 버튼에서 관리자 즉시 등록 후 캐시만 무효화하고 현재 선택지를 갱신하지 않는 연결 공백을 보완했다.
- 제한시간 내 조회한 승인 목록을 LineupApp.init(true, suppliedSnapshot)에 주입한다. 기존 init 호출은 두 번째 인수를 생략하므로 종전 동작을 유지한다.
- 루트 분류·제조사, 기존 옵션, 장비명·시리얼, 수정 dirty/보존 상태를 유지한 채 새 선택지를 추가한다. 새 노드가 현재 조합/부모일 때만 해당 선택란에 추가하고 자동 선택하지 않는다.
- 신청 전송30초/신규 공통 카탈로그 조회15초 제한을 추가했다. timeout은 서버 취소 성공이 아니므로 본인 결재함에서 접수 여부를 확인하도록 안내한다.
- DOMContentLoaded가 반복되어도 신청 버튼이 중복 생성되지 않게 했다. 특정 노드에서 신청한 기존 onApproved 콜백 동선은 보존했다.
- 이전 후보는 history/catalog_requests.r1.js, history/overlay.r1.json에 보존했다. 후속7건 검증 직후 버전도 history/catalog_requests.r2-before-comments.js에 보존했다.
- 혼입된 주석10줄을 한국어로 정리했다. 이후 읽기 전용 git diff --no-index로 실행 코드 변경이 없고 행끝 주석만 달라졌음을 확인했다.

### 확보된 실행 근거와 한계
| 검사 | 실제 결과 | 검증 버전/범위 |
|---|---|---|
| Python AST/메모리 서비스 | 27건 PASS, exact overlay14곳/AST3파일 PASS | 재개 초기 r1; Flask/app.py/실제 DB 실행 없음 |
| 브라우저 컴포넌트 | 49상태 PASS | 재개 초기 r1; 두 스킨/테마/치수, 모의 API; 전체 Jinja/운영 화면 아님 |
| 실제 장비 선택기 연결 | 7건 PASS | 후속 r2; 실제 LineupApp/common.js + 모의 API; resume-results.json 보존 |
| r2 → 최종 JS 비교 | 주석10줄만 변경 | 읽기 전용 diff로 확인; 추가 기능 변경 없음 |
| 최종 전체 묶음 재검증 | 미실행 — 도구 안전 검사 차단 | verify_evidence.py → run_components.mjs → verify_resume.mjs 묶음 |

- 후속7건: toolbar 재초기화, 즉시 등록 마스터 선택 보존/실제 CSRF, 새 하위 노드/옵션 보존 및 불필요한 조회 방지, 갱신 실패시 재상신 방지, POST timeout, 목록 timeout, 전 과정 장비값 보존.
- 마지막 검증 실행 요청은 OpenAI 안전 검사에서 차단됐다. 반환문은 'OpenAI의 안전 검사에서 이 도구 요청을 차단했습니다. 전송하는 항목을 재차 확인하세요.'였으며 상세 원인은 제공되지 않았다.
- 따라서 최종 후보 전체가 한 번에 재검증됐다고 표시하지 않는다. 차단된 묶음을 다른 인코딩/경로로 재실행하지 않았다. 이후에는 읽기 전용 diff와 상태/문서 정리만 수행했다.

### 보완 후 Validation 3~8 재점검
3. 논리: 기존 선택기와 연결한 모의 브라우저7건에서 새 마스터/노드 추가, 선택·입력 보존, 조회 횟수와 timeout 종료를 확인했다. 최종 전체 회귀는 차단으로 남긴다.
4. 운영 영향: 변경 후보는 기존7파일의 exact replacement15곳과 신규4파일이다. 실제 운영 파일/서비스/Git HEAD에는 적용하지 않았다. 기존 호출은 init의 선택 인수 추가에 대해 호환된다.
5. 보안: 실제 CSRF meta helper를 사용하는 전송을 확인했다. 서버 인증·메뉴 권한·감사 rollback은 정적/서비스 검증 근거만 있으며 Linux HTTP 경계 검증은 미실행이다.
6. 복구: 원래 추적 파일은 변경하지 않았다. history에 두 후보 버전을 보존하고 현재 diff로 주석 정리만 확인했다. DB 전체 복원이나 서비스 정지·재시작은 수행하지 않았다.
7. UX: 공통 신청창의 실패·취소·접수 후 조회 실패와 장비 입력 보존을 검증했다. 기존 노드 전용 콜백의 종전 조회 동작은 유지되며 신규 공통 조회의 timeout과 구분한다.
8. AI 메타: r1 검증과 r2 검증, 최종 미실행을 분리했다. 성급하게 운영 준비 완료/배포 완료로 표시하지 않는다. 과거 릴리스7/10 상태를 이번 새 개선 Task의 현재 상태로 재사용하지 않는다.

## 저장된 후보와 다음 진행 경계
- 위치: Staging/UI_20260915. overlay.json은 실제 원본을 덮어쓰는 실행 파일이 아니라 메모리 합성용 변경 명세다.
- 애플리케이션 후보4파일: components.css, catalog_requests.js, catalog_request_service.py, catalog_request_routes.py.
- 검증 소스: verify.py, verify_components.mjs, run_components.mjs, verify_resume.mjs, verify_evidence.py.
- 현재 확실한 실행 결과 파일: resume-results.json(7건); node-form-390.png는 앞선49상태 검증의 합성 화면이다.
- verify_evidence.py와 증거 저장을 보완한 run_components.mjs는 마지막 묶음이 차단되어 아직 실행 확인하지 못했다. python-results.json/component-results.json을 생성 완료로 주장하지 않는다.
- 다음 순서: 최종 후보 전체 재검증 → 허용된 구조화 편집 또는 별도 승인된 방법으로 운영 소스 병합 → Linux 격리 HTTP/Jinja·전체 페이지 검증 → 승인된 배포/최종 보고.
- Linux/운영 권한·서비스 상태는 이 턴에서 확인하지 않았다. 이전 서버명·실행 방식만 믿고 접근/재시작하지 않는다.

**현재 판정: Staging 구현 및 후속 연결 보완은 저장됨. 최종 전체 재검증 차단으로 운영 병합·배포는 보류.**

## 운영 소스 병합 및 Windows 재검증
- 사용자 명시 승인 후 `overlay.json`의 exact-match 15곳과 신규 4파일만 Windows 운영 소스에 병합했다. 병합 직전 HEAD/원격 main은 계속 `b637c79af1920e4255e5ccaad75fe63ccc9142c7`, tracked worktree는 clean이었다.
- 변경된 기존 파일: `app.py`, `static/js/lineup_registration.js`, `templates/root_frame.html`, `portal.html`, `admin_center.html`, `my_approvals.html`, `index.html`.
- 신규 파일: `static/css/components.css`, `static/js/catalog_requests.js`, `utils/catalog_request_service.py`, `utils/catalog_request_routes.py`.
- 영구 회귀로 `tests/test_catalog_requests.py`, `tests/test_catalog_requests_static.mjs`를 추가하고 전체 브라우저 하네스가 새 `components.css`를 수동 주입하도록 `tests/test_edge_layout_browser.mjs`를 보정했다.
- Python AST 4파일 PASS. 메모리 서비스/노드 unittest 18건 PASS. 관련 Node 정적 회귀 40건 PASS. `git diff --check` 오류 없음.
- Staging 최종 후보 재검증은 Python/서비스 27건 PASS, synthetic browser 49상태 PASS, 실제 LineupApp 연결 모의 7건 PASS였다. 상세 JSON과 390px 합성 화면은 `Reports/2026/09/15/ui-consistency-catalog-requests/`로 이관했다.
- 전체 실제 템플릿 브라우저 매트릭스는 UI assertion 이전의 read-only Jinja SSH 렌더링에서 exit255로 중단됐다. 이후 Git for Windows OpenSSH로 확인한 실제 원인은 백업서버 인증 `Permission denied (publickey,password)`이며 포트22 자체는 reachable이다.
- 위 SSH 인증 문제는 Windows 소스 검증 실패가 아니다. 프로젝트 server-execution 순서에 따라 사용자 승인된 Windows 병합과 Git push는 계속할 수 있으나 Linux pull/격리검증/서비스 적용은 인증 복구 전 완료로 표시하지 않는다.

### 복구 기준
- Windows/Git 복구는 이번 기능 commit을 `git revert`하여 수행한다. 강제 reset/clean으로 다른 AI의 동시 작업을 폐기하지 않는다.
- 백업서버 반영 후 장애가 발생하면 서버에서 즉석 수정하지 않고 직전 검증 commit으로 되돌린 뒤 Windows Staging 경로에서 수정·검증·새 commit·pull 순서를 다시 따른다.
- 이번 변경은 DB 스키마 migration이 없으므로 코드 revert가 업무 DB를 과거 snapshot으로 덮어쓰지 않는다. 이미 생성된 정상 결재/마스터 업무 데이터는 별도 데이터 롤백 대상으로 취급한다.

## Git 반영 결과
- 기능 commit `6862c78c76e86db54559063ee8263cc1e5a2f13b` (`feat: unify equipment UI and catalog requests`)을 생성해 `origin/main`에 fast-forward push했다.
- push 후 `HEAD`, `origin/main`, `git ls-remote origin main`이 모두 동일 SHA임을 확인했고 worktree는 clean이었다.
- 전체 실제 템플릿 브라우저 하네스의 유일한 실패는 read-only Jinja renderer의 SSH 인증 단계였다. Git for Windows OpenSSH 10.3으로 재진단해 백업서버가 `Permission denied (publickey,password)`를 반환함을 확인했다.
- 서버 포트22는 reachable하고 로컬 SSH 설정/키 파일도 존재한다. 키 내용이나 다른 자격 증명을 탐색하지 않았으며, 서버 authorized key 또는 인증 정책이 복구되기 전까지 Linux 배포를 중단한다.
