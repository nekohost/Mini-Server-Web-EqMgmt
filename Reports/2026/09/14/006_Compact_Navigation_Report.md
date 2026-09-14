# 상단바 좌우 그룹 2줄 배치 개선 결과

2026-09-14 · nekohost.org / eqmgmt-backup 운영 반영 완료

## 결과

이전 구현은 1,024px 미만에서 왼쪽 이동·중앙 제목·오른쪽 컨트롤을 각각 별도 행으로 강제했다. 좁은 PC 창에서도 상단 전체가 세로 3영역으로 바뀌는 것이 원인이었다. 이번에는 그룹 내부의 세로 공간을 먼저 사용하도록 변경했다.

| 영역 | 현재 배치 |
|---|---|
| 왼쪽 | 메인메뉴는 세로 중앙. 바로 오른쪽에 이전으로 위 / 상위 메뉴 아래. 두 버튼은 왼쪽 정렬. |
| 메인 포털 | 상위 메뉴 요소 자체가 없으므로 이전으로가 메인메뉴 바로 옆의 세로 중앙에 위치. 빈 행 없음. |
| 중앙 | 600px 이상에서는 좌우 그룹과 같은 행, 동일 폭의 좌우 트랙으로 현재 메뉴명의 정확한 중앙 좌표 유지. |
| 오른쪽 | 테마·세션을 첫 줄, 계정·로그아웃을 둘째 줄에 오른쪽 정렬. |
| 600px 미만 | 제목만 첫 행으로 이동. 왼쪽과 오른쪽 메뉴 그룹은 둘째 행에 나란히 유지. 세 영역을 각각 한 행으로 강제하지 않음. |

상단의 Standard 최대1,280px/여백, 기존 제목 경계, Edge의 넓은 본문/표·카드, 검색·CSV 접기는 유지했다. 360px 미만에서는 장식용 이동 아이콘만 숨기고 모든 버튼의 문구와 기능을 남긴다. 긴 닉네임/역할은 오른쪽 영역 안에서 말줄임하며 계정 링크 title에는 전체 값을 둔다. 실제 `<strong>`을 포함하는 세션 만료 임박 안내도 영역 안에서 줄바꿈한다. title의 hover는 터치 전용 환경에서 전체 표시를 보장하는 기능으로 주장하지 않는다.

서비스 변경 파일은 `static/css/layout.css`, `templates/miniserver_frame.html` 2개다. 이력 이동 JS·부모 경로·Python·DB 스키마·인증/권한은 변경하지 않았다. 별도 제안을 만들지 않고 제안019·020의 후속 개선으로 FEATURES.md/PROPOSALS.md에 기록했다. 005 보고서는 당시 배포 이력이고 현행 상단 배치는 이 보고서와 FEATURES.md 12-4절을 따른다.

## 검증

- Node 정적/프런트엔드 회귀31건 및 실제 템플릿 브라우저 회귀13건, 합계 **44건 통과**.
- 실제 후보 템플릿16종 × 320/390/599/600/768/960/1024/1920/2560px × Standard/Edge에서 상단 너비·중앙 좌표·좌우 내부 배치·본문 제목 폭·영역 겹침/넘침을 검사했다. 기존 8폭의 카드/표/설정/검색 회귀도 유지했다. 긴 닉네임·SUPER_ADMIN·구조화된 세션 경고를 별도로 검사했다. 320px 스트레스 검사에서 발견한 오른쪽 내부 침범은 역할 말줄임·배지 줄바꿈으로 배포 전에 보완했다.
- Windows Flask 실행 없이 Linux Jinja DictLoader로 로컬 후보 템플릿을 읽기 전용 렌더링하고, 네트워크가 차단된 headless Edge fixture로 확인했다.
- 배포 후 기존 일반 사용자 `guide_test_user`로 실제 도메인의 **PC 중심49개 상태 통과**. 599/600px 분기와 768/960px 좁은 PC 창의 좌/중앙/우 배치, 메인 포털의 상위 메뉴 부재, 이전/부모 이동을 확인했다. 배포 정적 자산 해시, 설정 저장·새로고침, 테마, 프로필 모달, Chart.js, 검색 조건/URL/초기화, CSV 접기/모달의 기존 계약도 재확인했다. 장비 등록/수정/CSV 가져오기 확정은 제출하지 않았다.
- **모바일 터치 에뮬레이션72개 상태 통과**: 두 스킨 × 포털/나의 장비/공개 장비/내 정보/통계 × 320×568/360×800/390×844/412×915의40상태, 조건검색16상태, CSV 펼침16상태. 좌우 그룹 같은 행·제목 중앙·헤더/본문 분리·가로 넘침·터치 이동을 확인했다. 정상 상태의 상단 높이는120px 미만이다.
- 실제 960px 장비 화면/1920px 포털 및 390px 장비/320px 포털 스크린샷을 육안 확인했다. 서버5xx=0, 브라우저 pageerror=0, 금지된 변경 요청0, 일반 계정 관리자 API403 유지. 두 실검증 종료 후 설정 복원·로그아웃 완료.

모바일은 Chromium 기반 세로 터치 에뮬레이션이다. 실기기·iOS Safari·소프트키보드·시스템 글자 확대 검증은 아니다. 관리자 전용 화면은 템플릿/레이아웃 검사 범위이며 이 일반 계정으로 실제 관리자 작업을 수행하지 않았다.

## 배포·복구 및 데이터 보존

- 2026-09-14 **14:49:02 KST** 백업 및 UI 2개 파일 원자적 배포. 배포 직전 파일 정규화 SHA·HEAD·정확한 PID/cwd/명령을 확인했다. PID81107을 pidfd/SIGTERM으로 종료하고 같은 명령/환경을 승계해 PID82278로 기동했다. 로그인 HTTP200, 파일 해시 일치, 기동 오류 표식0.
- 비공개 복구 위치: `/home/nekohost/.local/share/mini-server-eqmgmt/releases/ui-compact-navigation-20260914T054902Z/`. 디렉터리0700, 보존 파일0600. before/candidate·DB 온라인 사본·manifest/result·기동 로그 보존. 실패 시 이번 두 파일만 원복/재기동하는 보상 경로를 준비했으며 실제 롤백은 없었다. 동봉 deploy 도구는 이전 PID/해시가 고정된 일회성 배포 근거이므로 그대로 재실행하지 않는다.
- 최종 DB integrity=ok/FK위반0, 사용자3/장비1/옵션1/노드12 유지. 배포 전 사본과 비교해 장비·옵션·노드의 모든 행, 사용자 식별 정보·역할·비밀번호가 동일하고 전체 사용자의 유효 환경 설정은 원상 복원됐다. 테스트 로그인/세션/접근 로그는 정상 부수 효과다.
- 기존 서버 보관 테스트 자격증명은 프로세스 메모리로만 사용했다. 비밀번호·쿠키 파일·trace·비밀 값 출력은 만들지 않았다.
- Git HEAD `5ab042a7cb1a4acd25af64732c6a1f64b644db94`. 이전 미커밋 변경을 보존했으며 이번에 commit/push나 주 미니서버 배포, 무관한 거버넌스/사용자 가이드 배포는 수행하지 않았다.

## 증거

- [배포 해시·PID](compact-navigation/deployment.json)
- [최종 데이터·설정 보존 검사](compact-navigation/postflight.json)
- [실제 도메인49상태](compact-navigation/live/live-verification.json)
- [터치 세로72상태](compact-navigation/portrait/portrait-verification.json)
- [960px 장비 화면](compact-navigation/live/screenshots/my_equipment-compact-960.png)
- [1920px 메인 포털](compact-navigation/live/screenshots/03-portal-edge-1920.png)
- [390px 장비 화면](compact-navigation/portrait/screenshots/edge-my_equipment-390.png)
- [320px 메인 포털](compact-navigation/portrait/screenshots/edge-portal-320.png)

재검증 코드는 `tests/test_edge_layout_browser.mjs`, `Reports/2026/09/14/edge-release/verify-live.mjs`, `verify-portrait.mjs`에 유지한다. 후자의 실계정 검사는 `EQM_LIVE_VARIANT=compact-nav`로 이번 배치 계약을 선택하며 일반 CI에서는 자동 접속하지 않는다.
