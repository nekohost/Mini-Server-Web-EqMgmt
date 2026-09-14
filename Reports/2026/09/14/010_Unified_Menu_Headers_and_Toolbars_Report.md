# 메뉴 제목·작업 영역 통일 및 긴 닉네임 상단바 개선

2026-09-14 · nekohost.org / eqmgmt-backup 운영 반영·검증 완료

후속 안내: 제목/장식 아이콘·테마 아이콘과 내 정보 보안 패널의 현재 동작은 [보고서011](011_Menu_Workflows_and_Personal_Approvals_Report.md)에서 갱신했다. 이 보고서의20파일 배포와 당시 검증 수치는 이력으로 보존한다.

## 구현 결과

사용자의5개 UI 요구와 추가 긴 닉네임 조건을 함께 반영했다. 이전에 철회한 제목 왼쪽/기능 오른쪽 고정 배치를 되살리지 않고, 제목·설명 아래 별도 작업 영역을 구성했다. 기존 제안019·020·035의 후속 개선으로 기록하며 새로운 제안 번호는 만들지 않는다. 제안018의 선택 버튼 항상 표시/선택0건 비활성은 그대로 유지한다.

| 대상 | 현재 동작 |
|---|---|
| 관리자 센터 | 사용자→권한→마스터→라인업→결재→감사 로그→접근 로그→점검→백업 순. 그룹별 강제 개행 없이 가용 열 수를 차례로 채움 |
| 본문 메뉴 제목/설명 | 인증 후 메뉴15개 템플릿에 공통 제목/설명. 마스터 관리 기준24px/768px 이상30px 제목,14px 설명. Edge의 제한된 제목 경계와 파란 좌측선 공유 |
| 기능 버튼 | 제목/설명 아래 별도 영역. 기존 ID·이벤트·확인 절차 보존 |
| 나의/공개 장비 | 공유 작업 영역. 1024px 이상 기능 왼쪽/검색 오른쪽, 그 미만 제목→설명→검색→기능→상태/페이지→표 |
| 좁은 상단바 | 중앙 메뉴명 유지. 오른쪽은 로그아웃 / 닉네임+권한 / 테마·세션의3줄 |
| 긴 닉네임 | 한 줄·필요 시 말줄임. 원래 이름/권한을 title·aria-label 및 마이페이지에 보존. 360px 미만 장식 계정 아이콘만 숨김 |
| 오른쪽 버튼 디자인 | 카드형 표면·1px 테두리·12px 모서리·그림자·포커스 공통. 빨간 로그아웃/세션 경고, 파란 권한, 테마 아이콘 의미 유지 |

계정 이름을 내 정보라는 대체 문구로 바꾸지 않는다. 닉네임만 줄어들 수 있게 하고 권한 표시는 줄바꿈하지 않는다. 현재 지원 역할 user/admin은 검사한 최소320px에서도 보이며 극단적으로 긴 합성 역할에도 영역 넘침을 제한한다. 닉네임은 실제 계정을 변경하지 않고 합성 화면에서 길게 치환해 검사했다.

장비 등록/임시저장함/목록 복귀, 공개 목록의 내 장비 포함, 간편·조건 검색 및 숨은 조건 제외/재표시, CSV 접기/팝업은 유지한다. 세션 타이머의 className 덮어쓰기만 상태 속성으로 대체해 공통 버튼 디자인이 사라지지 않게 했다. DB·API·권한·세션 만료 정책·CSRF·관리 기능의 실행 로직은 변경하지 않았다.

## 변경 범위

- 서비스20파일: `static/css/layout.css`, `static/js/menu_cards.js`, `static/js/session_timer.js`.
- 템플릿17개: `miniserver_frame`, `index`, `roadmap_equipment`, `master_management`, `users_management`, `permissions`, `admin_center`, `audit_logs`, `access_logs`, `access_logs_error_ips`, `lineup_management`, `approvals`, `portal`, `dashboard`, `mypage`, `maintenance_admin`, `backup_restore`.
- 테스트: 공통 화면 geometry 계약, 실제 템플릿 브라우저 검사, `test_unified_ui.mjs`와 기존 실접속 도구의 `unified-ui` 실행 경로. 과거 롤백의 고정 해시 검사는 명시적 역사 감사 옵션으로 분리했으며 현재 회귀를 대체하지 않는다.
- FEATURES.md/PROPOSALS.md 현행 명세와 보고서009의 후속 안내를 갱신했다. 무관한 로컬 변경·기록·Rule·거버넌스는 보존했다.

## 검증 결과와 한계

- 정적/프런트엔드 **38건**, 실제 템플릿 브라우저 **22건**, 합계 **60건 통과**. 최종 전체 브라우저 실행 약82초, 실패/건너뜀0. 이후1440px 검색 스크린샷의 viewport·스크롤을 명시한 대상 재검사도 통과했다.
- 16개 실제 렌더 화면 × Standard/Edge × 9폭의 상단바/본문 경계·정렬·넘침 검사. 본문 제목·설명 크기, 기능 아래 배치, 장비 작업/검색의1024px 전환, 표 가로 스크롤/컬럼 제목과 버튼 단어 보존을 확인했다.
- 긴 닉네임: 두 스킨 ×320/360/390/412/599px ×user/admin에서 긴 이름 전후의 오른쪽 그룹 높이가 동일하고 로그아웃·계정·테마/세션 각각 한 줄 높이임을 검사했다. 320px 육안 검토 후 장식 아이콘을 분리해 이름 공간을 확보하고 전체 회귀를 다시 통과했다.
- 관리자 카드: 두 스킨 ×7폭에서 원래 허용 메뉴의 순서/개수 보존, 강제 grid 시작 없음, 마지막을 제외한 행이 채워짐을 확인했다. 최초 배치 검사의 hover 이동(-4px)이 별도 행처럼 측정되는 문제는 포인터를 카드 밖으로 옮겨 보정했다. 빈칸 검사 기준을 완화하거나 서비스 CSS의 hover 효과를 제거하지 않았다.
- 첫 좁은 상단바 검사에서 상속된 줄 높이가 계정/도구 행을 늘리는 것을 발견해 공통 버튼 line-height와 아이콘 line-height를 명시했다. 최종3줄 검사는 그대로 유지했다.
- 실제 기존 일반 사용자 `guide_test_user`: **PC 중심49상태**, **터치 세로76상태**, **팝업12상태** 통과. 세로는320×568/360×800/390×844/412×915의 두 스킨5화면, 조건검색16상태, CSV16상태, 임시저장함4상태를 포함한다. 임시저장함은 조회 후 나의 장비 목록으로 복귀했으며 팝업은 열기/닫기만 했다.
- 실제 도메인 자산 SHA 일치, 설정 저장/새로고침, 세션 Enter 연장, 이력/상위 메뉴 이동, 검색·CSV 상태 전환, Chart.js 출력 확인. 두 검사 모두 서버5xx0/pageerror0/허용 밖 변경 요청0, 관리자 API403 유지, 설정 복원·로그아웃 성공.
- 관리자 메뉴는 권한을 올리지 않고 합성 데이터/차단된 네트워크 fixture로 검증했다. 관리자 계정의 실제 삭제/저장/점검/복원 작업은 수행하지 않았다. 모바일은 Microsoft Edge/Chromium 터치 에뮬레이션이며 실기기/iOS Safari 검증은 아니다. 합성 화면 아이콘은 안정된 대체 문자, 실접속은 실제 아이콘으로 확인했다.
- 긴 닉네임320px, 관리자 연속 배열1440px, 사용자/마스터 관리320px, PC 장비 검색/작업 배치, 실제 나의/공개 장비320/390px 및 임시저장함 스크린샷을 육안 확인했다.

## 운영 반영·보존

- **2026-09-14 16:38:46 KST**, 현재 HEAD/PID/cwd/명령과20개 파일의 변경 전 SHA를 대조했다. 온라인 DB 백업과 변경 전후 소스를 보존한 뒤20파일을 원자적으로 교체했다. PID86641을 pidfd/SIGTERM으로 정상 종료하고 동일 명령/환경의 PID88513을 기동했다. 로그인 HTTP200, 모든 배포 파일 SHA 일치, 기동 오류 표식0.
- 복구 자료: `/home/nekohost/.local/share/mini-server-eqmgmt/releases/ui-unified-ui-20260914T073846Z/`. 디렉터리0700/보존 파일0600으로 before/candidate·온라인 DB 사본·manifest/result·기동 로그를 남겼다. 배포 실패 시 변경20파일만 복구하는 경로를 준비했으며 실패/롤백은 발생하지 않았다. 이 배포 도구는 이전 PID/SHA에 고정된 일회성 근거이며 그대로 재실행하지 않는다.
- integrity=ok/FK위반0. 사용자3/장비1/옵션1/노드12 유지. 배포 전 사본과 장비·옵션·노드·메뉴·역할별 메뉴 권한 전체 행 동일. 사용자 식별/역할/비밀번호 불변, 모든 사용자의 유효 환경 설정 보존/복원. 테스트의 로그인·세션·접근 로그는 정상 부수 효과다.
- HEAD `5ab042a7cb1a4acd25af64732c6a1f64b644db94` 유지. 이번에는 검증한 운영 UI 파일만 반영했으며 Git commit/push/reset, DB 복원, 주 미니서버 배포는 하지 않았다. 전체 dirty worktree를 함께 배포하지 않았다.

## 증거와 재검증

- [배포20파일 SHA·프로세스·무결성](unified-ui/deployment.json) / [데이터·권한·설정 보존](unified-ui/postflight.json)
- [실제 PC49상태](unified-ui/live/live-verification.json) / [세로76·팝업12상태](unified-ui/portrait/portrait-verification.json)
- [긴 닉네임320px 합성 화면](unified-ui/fixtures/nickname-three-rows-edge-320.png) / [관리자 연속 배열1440px](unified-ui/fixtures/admin-related-order-1440.png)
- [PC 장비 검색/작업 배치](unified-ui/fixtures/equipment-simple-1440.png)
- [실제 Standard 나의 장비320px](unified-ui/portrait/screenshots/standard-my_equipment-320.png) / [실제 Edge 공개 장비390px](unified-ui/portrait/screenshots/edge-public_equipment-390.png) / [실제 임시저장함320px](unified-ui/portrait/screenshots/edge-my_equipment-320-drafts.png)

정적 검사는 `test_roadmap_static.mjs`, `test_release_frontend.mjs`, `test_proposal047_registration.mjs`, `test_responsive_shell.mjs`, `test_unified_ui.mjs`를 `node --test`로 실행한다. 템플릿 검사는 `EDGE_LAYOUT_BROWSER=1`로 `test_edge_layout_browser.mjs`를 실행한다. 실계정 검사는 `EQM_LIVE_EDGE=approved` 및 `EQM_LIVE_VARIANT=unified-ui`에서 `edge-release/verify-live.mjs`·`verify-portrait.mjs`를 순차 실행한다. 일반 CI에서는 실계정에 자동 접속하지 않는다.
