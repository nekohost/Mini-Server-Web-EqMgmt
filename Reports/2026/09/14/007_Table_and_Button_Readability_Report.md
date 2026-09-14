# 표 제목·버튼 문구 가독성 개선 결과

2026-09-14 · nekohost.org / eqmgmt-backup 운영 반영 완료

## 개선 내용

- **표 제목:** 일반 표는 컬럼 제목에 줄바꿈 제한이 없었고, CSV 미리보기는 `th`에도 `overflow-wrap:anywhere`를 적용하고 있었다. 공통 레이아웃에서 메뉴 표/미리보기의 제목을 `white-space:nowrap`, `word-break:normal`, `overflow-wrap:normal`로 설정했다. 데이터가 없거나 한 글자뿐이어도 제목이 한 줄로 읽힐 폭을 확보하고 기존 표 내부 스크롤로 좌우를 확인한다. 별도의 모든 표 공통 고정 너비를 강제하지 않는다. 제목의 말줄임·글자 크기 축소·세로 분할은 하지 않는다.
- **버튼 문구:** 공통 버튼·버튼형 링크에 `word-break:keep-all`, `text-wrap:balance`를 적용했다. 한 줄에 들어가는 문구는 한 줄로 두고, 여러 줄이 필요하면 단어를 보존하며 줄 길이의 균형을 맞춘다. 위아래 글자 수를 기계적으로 동일하게 맞추는 방식은 아니다. 균형 배분을 지원하지 않는 브라우저는 일반 단어 단위 줄바꿈을 사용한다. 단어 자체가 공간보다 긴 극단적인 경우에는 `overflow-wrap:break-word`를 최후의 넘침 방지 수단으로 둔다. 기존 검색/상단 이동 등 명시적 한 줄 규칙은 유지했다.
- **좁은 팝업:** 추가 검사에서 장비 등록의 취소·임시저장·저장 버튼 세 개가 한 행에 고정돼 넘치는 경우를 확인했다. `#modalButtons`와 명시적인 `#master-edit-actions` 그룹은 버튼 요소를 다음 행으로 배치한다. 이메일 수정 입력은 `min-width:0`으로 축소 가능하게 하여 발송/확인 버튼이 밖으로 밀리지 않게 했다.

서비스 변경은 `static/css/layout.css`와 `templates/master_management.html` 2개 파일이다. 후자는 마스터 편집 버튼 그룹에 ID만 추가했다. 데이터 셀의 기존 줄바꿈·숨겨진 컬럼·표 스크롤·검색/CSV·상단바 구조는 유지하고, Python·API·DB·버튼 동작·권한 로직은 변경하지 않았다. 기존 제안019의 공통 UI 개선으로 FEATURES.md/PROPOSALS.md에 기록했다.

## 검증

- 정적/프런트엔드31건 + 실제 템플릿 브라우저16건, 합계 **47건 통과**. 마지막 버튼형 링크 선택자 확장 후에는 관련 표/버튼 검사만 추가 재실행해 통과했다. 건수를 반복 실행 횟수로 부풀리지 않았다.
- 실제 템플릿16개 화면 × 두 스킨 × 320/390/768/1920px에서 빈 표 제목과 버튼의 단어 분리/잘림/페이지 넘침을 검사했다. 각 표의 데이터를 짧은 `1`로 바꾼 별도 fixture에서도 제목이 수평을 유지하며 스크롤 끝에 도달하는지 확인했다. 긴 데이터의 기존 표 내부 스크롤 회귀도 유지했다.
- CSV 동적 헤더 fixture와 제한된 폭의 2줄 버튼에서 단어 보존·줄 길이 균형을 확인했다. 장비 등록/CSV/프로필/이메일/마스터 편집/통폐합의 6종 팝업을 320/390/768px에서 열어 버튼 잘림을 검사했다. 관리자 작업은 합성 데이터와 네트워크 차단 fixture이며 실제 관리 작업을 실행하지 않았다.
- 기존 상단바 16화면 × 9폭 × 두 스킨, 카드/설정/검색/제조사/카탈로그 회귀도 유지했다. Windows Flask는 실행하지 않았으며 Linux Jinja DictLoader의 읽기 전용 렌더링과 격리 headless Edge를 사용했다.
- 기존 일반 사용자 `guide_test_user`로 실제 도메인 **PC 중심49상태** 통과. 배포 정적 자산 해시, 표 제목의 실제 텍스트 높이/클리핑, 버튼 단어 분리, 표 스크롤 끝 도달 여부를 검사했다. 기존 검색/CSV/설정/테마/이동/Chart.js 계약도 재확인했다.
- **모바일 세로72상태 + 팝업12상태 통과.** Standard/Edge × 5개 화면 × 320×568/360×800/390×844/412×915의40상태 및 상세검색/CSV 각16상태다. 추가 팝업은 두 스킨 × 장비 등록/프로필/이메일 × 320/390px의12상태로, 열기/닫기만 실행했다. 장비 등록·임시저장·프로필 제출·인증 메일 발송·CSV 업로드/확정은 실행하지 않았다.
- 실제 모바일 장비 표와 등록 팝업, 합성 관리자 표/버튼의 스크린샷을 육안 확인했다. 서버5xx=0, 브라우저 pageerror=0, 허용 범위 밖 변경 요청0. 일반 계정의 관리자 API는403 유지. 두 실검증 모두 환경 설정 복원과 로그아웃 완료.

모바일은 Chromium 기반 터치 에뮬레이션이며 실기기·iOS Safari·소프트키보드·시스템 글자 확대는 미검증이다. 가로 이동의 자동 검사는 스크롤 위치 변경과 끝 지점 도달을 측정하며 실기기 손가락 제스처의 검증으로 주장하지 않는다. 관리자 전용 화면은 일반 계정의 실제 접속 범위가 아니다.

## 배포·보존

- 2026-09-14 **15:05:20 KST**, 현재 서버의 파일 SHA·HEAD·PID/cwd/명령 확인 후 이번 UI 2개 파일만 원자적 반영했다. 기존 PID82278을 pidfd/SIGTERM으로 종료하고 같은 인수/환경으로 PID83671을 기동했다. 로그인 HTTP200, 파일 해시 일치, 기동 오류 표식0 확인.
- 복구 위치: `/home/nekohost/.local/share/mini-server-eqmgmt/releases/ui-readability-20260914T060520Z/`. 디렉터리0700, 보존 파일0600. before/candidate, DB 온라인 사본, manifest/result 및 기동 로그를 보존했다. 실패 시 이번 파일만 원복/재기동하도록 구성했으며 실제 롤백은 없었다. 동봉 배포 도구는 해당 이전 PID/해시를 고정한 일회성 근거이며 그대로 재실행하지 않는다.
- 최종 DB integrity=ok/FK위반0, 사용자3/장비1/옵션1/노드12 유지. 배포 전 사본과 비교해 장비·옵션·노드 전체 행, 사용자 식별 정보·역할·비밀번호가 동일하다. 모든 사용자의 유효 환경 설정도 복원됐다. 테스트 로그인·세션·접근 로그는 정상 부수 효과다.
- 자격증명은 기존 서버 보관본에서 메모리로만 사용했으며 비밀번호·쿠키·trace 파일/비밀 값 출력은 만들지 않았다. 스크린샷의 비밀번호 입력은 마스킹했다.
- HEAD `5ab042a7cb1a4acd25af64732c6a1f64b644db94`. 기존 미커밋 변경을 보존했다. 이번 commit/push·주 미니서버 배포·무관한 Rule/거버넌스/가이드 변경 배포는 없다. 최종 governance validate 및 Git diff 공백 검사를 통과했다.

## 증거

- [배포 해시·PID](table-button-readability/deployment.json)
- [데이터·설정 보존 검사](table-button-readability/postflight.json)
- [PC 중심49상태](table-button-readability/live/live-verification.json)
- [세로72상태·팝업12상태](table-button-readability/portrait/portrait-verification.json)
- [390px 장비 표의 수평 제목](table-button-readability/portrait/screenshots/edge-my_equipment-390.png)
- [320px 등록 팝업 버튼 행 분리](table-button-readability/portrait/screenshots/edge-equipmentModal-320.png)
- [320px 관리자 표/버튼 합성 검증](table-button-readability/fixtures/readable-master_management-320.png)

재검증: `tests/test_edge_layout_browser.mjs`와 `tests/helpers/readability.mjs`. 특정 fixture만 검사하려면 `EDGE_LAYOUT_CASE`에 검사명 일부를 지정한다. 실제 계정 검사는 기존 `edge-release/verify-live.mjs`, `verify-portrait.mjs`의 `EQM_LIVE_VARIANT=readability`를 사용하며 일반 CI에서 자동 접속하지 않는다.
