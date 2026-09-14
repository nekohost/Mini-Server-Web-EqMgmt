# 좁은 화면 상단바·제목/작업 버튼·관리자 UI 개선 결과

2026-09-14 · nekohost.org / eqmgmt-backup 운영 반영·검증 완료

후속 변경: 사용자가 요청한 **2번 페이지 제목/작업 버튼 배치**(이 보고서 아래의 반영 내용3항)는 같은 날 선택적으로 롤백했다. 상단바·선택 버튼·관리자 카드 개선은 유지한다. 이 문서는 당시 배포 이력이며 현재 상태는 [선택적 롤백 보고서009](009_Page_Heading_Selective_Rollback_Report.md)를 따른다.

## 반영 내용

1. **좁은 상단바:** 600px 미만에서도 제목을 별도 윗줄로 보내지 않고 좌/중앙/우를 같은 영역에 둔다. 왼쪽은 메인메뉴 → 이전으로 → 상위 메뉴, 오른쪽은 로그아웃 → 내 정보 → 테마/세션 순으로 세로 배치한다. 포털의 상위 메뉴는 여전히 생성하지 않는다. 600px 이상은 기존 메인메뉴 옆 이전/상위 2줄과 오른쪽 2줄 구조를 유지한다. 양쪽 동일 폭 트랙으로 제목 중심이 화면 중심과 일치한다.
2. **동적 메뉴명:** 공백을 정규화한 뒤 글자(grapheme)1·공백0.5로 계산한다. 좁은 화면에서는 한 줄 10단위와 실제 폰트의 픽셀 폭을 함께 적용해 단어 사이에서 줄을 나눈다. 가능한 줄 수를 최소화하고 줄 길이를 균형 있게 배분한다. 문구별 예외 하드코딩 없이 제목 변경·창 크기 변경·폰트 로딩에 대응한다. 2~3줄이 필요하면 늘어나며 임의의 3줄 제한이나 말줄임으로 제목을 숨기지 않는다. 단어 자체가 영역보다 긴 극단적 경우만 CSS의 비상 줄바꿈으로 넘침을 방지한다.
3. **페이지 제목/작업 버튼:** 장비·사용자·마스터·노드·권한·접근 로그·에러 IP·내 정보의 기존 제목/작업 버튼 행을 공통 그리드로 통일했다. 제목은 왼쪽 세로 중앙, 작업은 오른쪽에 놓고 768px 미만에서는 작업 버튼만 세로로 쌓는다. 설명·경로 안내는 전체 폭의 별도 행을 쓴다. 제목/작업 행이 없는 화면에는 인위적인 행을 만들지 않는다. 마스터 관리의 선택 삭제/신규 등록도 제목 오른쪽으로 이동하되 카테고리 탭은 아래에 유지한다.
4. **선택 작업의 가시성:** 사용자 관리의 선택 세션 파기·비활성화·활성화·영구 삭제 버튼4개는 처음부터 보인다. 선택0건이면 native disabled 상태이며 건수/전체 선택/부분 선택/해제/목록 재조회에 맞춰 갱신한다. 기존 확인창, 선택 없음 방어, CSRF, 관리자 권한 및 실행 API는 바꾸지 않았다. 전체 세션 파기 버튼의 기존 조건도 유지한다.
5. **관련 관리자 카드:** 사용자/권한 → 마스터/라인업/결재 → 감사/접근 로그 → 점검/백업 순으로 묶는다. 단순 정렬만 하면 묶음이 이전 행 끝과 다음 행 시작으로 떨어질 수 있어 각 묶음의 첫 카드는 새 행에서 시작한다. 허용된 API 결과의 표시 순서만 바꾸며 DB의 SortOrder·계층·권한과 일반 포털 순서는 변경하지 않는다. 미래의 미등록 메뉴는 원래 상대 순서를 보존해 뒤에 표시한다.

좁은 상단바의 계정 링크는 긴 이름 대신 `내 정보`로 표시하고 기존 전체 계정명 title/링크를 유지한다. 세션은 좁은 화면에 간결한 시간을 표시하고 접근성 이름에 전체 남은 시간/연장 의미를 제공한다. 세션 요소를 native button으로 바꿔 클릭뿐 아니라 Enter로도 연장한다. 기존 세션 API·시간 계산은 유지한다.

Standard의 최대 상단 폭1,280px, 화면별 제목 경계, Edge의 넓은 표, 카드 크기, 표 제목 한 줄/내부 스크롤, 단어 단위 버튼 줄바꿈, 검색/CSV 접기는 보존했다. 신규 제안이 아니라 기존018·019·020·035의 후속 개선으로 FEATURES.md/PROPOSALS.md에 기록했다. 이전의 좁은 화면 제목 상단 분리 기록은 현재 동작과 혼동하지 않도록 과거 이력으로 표시했다.

## 변경 범위와 검증

- 서비스14파일: CSS1개(`layout.css`), JS3개(`navigation.js`, `menu_cards.js`, `session_timer.js`), 템플릿10개(`miniserver_frame`, `index`, `master_management`, `users_management`, `admin_center`, `access_logs`, `access_logs_error_ips`, `lineup_management`, `permissions`, `mypage`). Python·DB 스키마·업무 API 변경은 없다.
- 정적/프런트엔드 **35건**, 실제 Jinja 템플릿 기반 브라우저 **19건**, 합계 **54건 통과**. 반복 실행을 별도 건수로 더하지 않았다. Node 검사는 `test_roadmap_static`, `test_release_frontend`, `test_proposal047_registration`, `test_responsive_shell`, `test_edge_layout_browser`를 사용했다.
- 실제 템플릿16개 × 두 스킨 × 320/390/599/600/768/960/1024/1920/2560px에서 제목 중앙·좌우 영역·제목/작업 버튼·페이지 넘침을 검사했다. 599/600 경계, 긴 닉네임/역할, 만료 임박 세션, 동적 제목 변경/HTML처럼 보이는 안전한 텍스트, 10단위 전후·공백·이모지·결합문자 검사를 포함한다.
- 사용자 관리 fixture에서는 실제 인라인 코드를 합성 사용자와 차단된 fetch로 실행했다. 선택0건에서 버튼 클릭이 요청을 만들지 않는지, 일부/전체 선택·해제·목록 교체 후 상태를 확인했다. 관리자 카드의 순서·묶음별 동일 행·미래 항목 보존·원본 배열 불변도 확인했다. 실제 사용자 관리 API로 세션 파기·삭제·역할 변경은 하지 않았다.
- 기존 표/빈 표/짧은 데이터/긴 데이터·스크롤, 6종 모달, 검색/CSV·환경 설정·카탈로그·제조사 회귀를 포함했다. Windows에서는 Flask를 실행하지 않았다. Linux에서 앱/DB를 불러오지 않는 Jinja DictLoader로 후보를 렌더링하고 격리 headless Edge에서 검사했다.
- 기존 일반 사용자 `guide_test_user`로 실제 도메인 **PC 중심49상태 통과**. 정적 자산 해시가 배포본과 일치하고 로그인·설정 저장/재로딩·테마·검색 모드·CSV 접기·뒤로/상위 이동·Chart.js 동작을 재확인했다.
- **터치 세로72상태 + 팝업12상태 통과**. Standard/Edge × 5화면 × 320×568/360×800/390×844/412×915의40상태, 상세검색16, CSV16이다. 추가 팝업은 두 스킨 × 장비 등록/프로필/이메일 × 320/390px의12상태로 열기/닫기만 실행했다. native 세션 버튼 Enter 연장도 HTTP200을 확인했다.
- 실제 PC/320px/390px 화면과 합성 관리자 카드/선택 버튼 스크린샷을 육안 확인했다. 실접속 검사에서 서버5xx=0, pageerror=0, 범위 밖 변경 요청0. 일반 계정의 관리자 API403 유지, 설정 복원·로그아웃 완료.

### 검사 중 보정한 사항

- 배포 전 전체 fixture 첫 실행은 연속 `setContent` 과정의 이전 제목 감시자/리스너 누적으로 240초 제한에 걸렸다. 재초기화 시 기존 감시자·리스너를 해제하는 `destroy`, 분리된 요소 조기 종료, fixture 교체 전 정리를 추가했다. 최종 전체19건은 약75초에 통과했다. 시간 제한을 늘려 통과로 취급하지 않았다.
- 배포 후 첫 PC 검사는 창 크기 변경 직후 resize/ResizeObserver 프레임 전에 측정해 `/mypage-light-edge@390: responsive title lines`에서 실패했다. 당시 설정 복원/로그아웃은 성공했다. 브라우저 두 프레임 뒤 측정하도록 검사 시점을 보정한 뒤 PC49/세로72/팝업12 모두 통과했다. 이 보정은 검사 도구에만 적용했으며 서비스 코드 추가 배포나 롤백은 없었다.

모바일은 Chromium 기반 터치 에뮬레이션이다. 실기기·iOS Safari·소프트키보드·시스템 글자 확대는 미검증이다. 관리자 화면은 실제 템플릿/합성 데이터 시험이며 관리자 계정으로 실접속한 검증은 아니다. 비밀번호 입력은 마스킹하고 자격증명·쿠키·trace 파일은 기록하지 않았다.

## 운영 반영과 보존

- **2026-09-14 15:42:37 KST**, 백업 서버 HEAD·현재14파일 SHA·PID/cwd/실행 명령을 확인하고 승인된 UI14파일만 원자적으로 반영했다. PID83671에 pidfd/SIGTERM을 사용하고 같은 명령/환경으로 PID84781을 기동했다. 로그인 HTTP200,14파일 해시 일치, 기동 오류 표식0.
- 복구 위치: `/home/nekohost/.local/share/mini-server-eqmgmt/releases/ui-responsive-shell-20260914T064237Z/`. 디렉터리0700, 보존 파일0600. before/candidate, 온라인 DB 사본, manifest/result, 기동 로그가 있다. 배포 중 실패 시 이번 파일만 원복/재기동하도록 구성했고 실제 롤백은 없었다. 동봉 배포 도구는 이전 PID/SHA를 고정한 일회성 근거로 그대로 재실행하지 않는다.
- integrity=ok, FK위반0. 사용자3/장비1/옵션1/노드12 유지. 배포 전 DB 사본과 비교한 장비·옵션·노드·menus·role_menu_permissions 전체 행이 동일하다. 사용자 식별 정보·권한·비밀번호, 모든 사용자의 유효 환경 설정도 보존/복원됐다. 테스트 로그인·세션 연장·접근 로그는 정상 부수 효과다.
- 로컬/서버 HEAD `5ab042a7cb1a4acd25af64732c6a1f64b644db94`. 기존 미커밋 작업을 보존했으며 이번 Git commit/push, 주 미니서버 배포, 무관한 Rule/거버넌스/가이드 배포는 없다. 최종 governance validate는 오류/경고0, Git diff 공백 검사 통과. Git의 LF→CRLF 안내는 공백 검사 실패와 구분한다.

## 증거

- [배포 파일 해시·PID](responsive-shell/deployment.json) / [데이터·권한·설정 보존](responsive-shell/postflight.json)
- [실제 도메인49상태](responsive-shell/live/live-verification.json) / [세로72상태·팝업12상태](responsive-shell/portrait/portrait-verification.json)
- [320px 실제 나의 장비](responsive-shell/portrait/screenshots/standard-my_equipment-320.png) / [390px 실제 Edge 나의 장비](responsive-shell/portrait/screenshots/edge-my_equipment-390.png)
- [PC 실제 나의 장비](responsive-shell/live/screenshots/04-my-equipment-edge-1920.png)
- [사용자 관리 비선택 버튼 fixture](responsive-shell/fixtures/users-unselected-320.png) / [관련 관리자 카드 fixture](responsive-shell/fixtures/admin-related-order-1440.png)

재검증: `tests/test_responsive_shell.mjs`, `tests/helpers/responsive_shell.mjs`, `tests/test_edge_layout_browser.mjs`. 기존 실접속 도구 `edge-release/verify-live.mjs`·`verify-portrait.mjs`는 `EQM_LIVE_VARIANT=responsive-shell`일 때 이 작업의 증거 폴더를 사용한다. 일반 CI에서는 자동 로그인하지 않는다.
