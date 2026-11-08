---
artifact_id: REPORT-20261109-001
work_id: RELEASE-20261109-MENU-WORKSPACE
owner: Codex
status: completed
---

# 메뉴 작업 공간 확대 검증

구현 전 Validation 1–8:

1. Recorder ensure 성공·기존 watcher 11268. profile은 legacy/runtime-session-mismatch로 판단되었으며 검증되지 않은 모델 이름으로 우회하지 않았다. 정책 1.8.1의 44개 노드 오류/경고 0, 해당 context 29개 노드를 전체 읽었고 필수 입력 0. 기존 변경 9개와 미추적 항목은 보존한다.
2. 이전 시범의 기준을 나머지 메뉴에 확대한다. 독립 로그인·공지·모달의 고유 제목은 유지하며 이미 최적화한 AI 세션 제목과 입력창 높이 계산을 보존한다. 일반 작업 화면은 상단 바에서 이름을 알리고 16px 아래부터 업무 영역을 표시한다.
3. 반복 제목의 삭제가 검색·처리 버튼·필터·유효성 검사를 제거하지 않도록 원본 DOM ID/폼/이벤트·스크립트와 비교한다. 라인업 aria-labelledby와 공개 장비의 제목 참조를 점검한다. 본문 설명은 접힌 안내로 보존한다.
4. DB·API·권한·모델 호출을 변경하지 않는다. 공통 프레임 여백 변경이 AI의 전용 높이 계약이나 예외 화면에 영향을 주는지 검증한다. Linux 브라우저는 실제 서비스와 독립된 루프백 합성 데이터만 사용한다.
5. 기존 이스케이프와 CSRF·접근 제어를 유지한다. 운영 검증은 조회·열기·닫기만 수행하고 계정·권한·연결·장비 저장과 삭제를 하지 않는다. 비밀/실제 DB를 보고서나 Git에 넣지 않는다.
6. 원본 Git commit·기존 변경 SHA·검증 ZIP을 보존한다. 서버 적용 전 설정·업무/AI DB·코드의 사용자 전용 복구 사본을 확보한다. 활성 요청이 있으면 종료를 기다리며 생성 요청을 중단하지 않는다.
7. 제목을 숨기는 CSS 대신 중복 마크업을 제거하고 상단 h1을 main 접근성 이름으로 연결한다. 좁은 화면의 줄바꿈·작업 버튼·표의 내부 스크롤·페이지 가로 넘침·접힌 안내 접근성을 검사한다.
8. 모든 범위와 한계를 근거로 기록한다. 새로운 외부 라이브러리·관련 없는 파일 수정·다른 서비스 제어는 필요 없다. Linux 환경에서 Jinja/브라우저를 실행하며 Windows에서 Flask를 기동하지 않는다.

Staging 구현: 중복 본문 제목 15곳을 제거하고 공통 상단 h1을 `main`의 접근성 이름으로 연결했다. 라인업의 제거된 제목 참조를 수정했으며 공개/나의 장비는 같은 압축 배치를 사용하되 조회 조건과 소유 기능 분기를 유지한다. 기존 설명은 본문 마지막의 기본 접힘 '화면 안내'에 보존한다. 폼 주변의 경고와 고유 작업 제목은 그대로다. AI 전용 높이 계산을 사용하는 `.assistant-container`에는 일반 16px 여백 규칙을 적용하지 않는다.

- [최종 정적 검사](001_Menu_Workspace/stage-static-final.json): 25개 통과, opt-in 브라우저 검사 1개는 이 실행에서 제외하고 Linux 실제 브라우저로 별도 검사했다.
- [기존 컨트롤 대조](001_Menu_Workspace/controls-preserved.json): 변경한 템플릿 16개에서 기존 inline script 및 form/button/input/select/textarea 태그가 동일하다. 제거한 ID는 본문 제목의 `pageMainHeader`, `lineup-page-title`뿐이며 공통 `app-page-title`을 추가했다.

추가 발견과 수정: 감사 로그의 전역 `loadUserSettings`/`saveUserSettings`가 공통 프레임의 같은 함수를 덮어써 Edge/테마 초기화를 방해했다. `loadAuditLogSettings`/`saveAuditLogSettings`로 분리하고, 공통 함수의 정체성과 감사 설정의 기존 POST/CSRF 계약을 회귀 검사했다. 따라서 최종 원문에서 감사 로그의 inline script만 이 명시적 예외로 변경됐고 나머지 15개 템플릿의 스크립트 및 16개 템플릿의 폼 컨트롤 태그는 동일하다. 320px 권한 표는 메뉴 이름의 최소 폭을 보장하고 기존 표 내부 스크롤을 사용하도록 수정했다.

검사 도구도 보완했다. 카탈로그 버튼의 비동기 mount를 기다리고 감사 로그 모의 응답의 실제 `total_count` 계약을 맞췄다. 테마 전환 도중의 회색 중간 프레임은 유한 애니메이션 종료 후 캡처하도록 바꿨다. 명시한 320px 조합이 비어도 통과하던 검사 선택기를 수정하고 실제 320px 검사를 다시 실행했다. 초기 실패/빈 시도 기록은 삭제하지 않고 최종 결과와 구분했다.

[최종 화면 검사 취합](001_Menu_Workspace/stage-verification.json): 15개 메뉴의 36개 화면·348개 판정, AI 대화/연결관리의 공통 프레임 회귀 10개 화면·346개 판정이 통과했다. 320/384/820/1440 CSS px, 라이트/Standard·다크/Edge를 포함하며 메뉴의 첫 업무 영역까지 간격은 모두 16px이었다. 화면 전체 가로 넘침은 없고 넓은 표는 내부에서 스크롤한다. 모바일은 브라우저 뷰포트 검사이며 실기기 검사는 아니다.

운영 소스 병합 전 Validation 1–8:

1. 정확한 23개 후보/운영 경로로 context를 다시 산출했고 이미 읽은 29개 노드와 동일했다. 기존 변경 9개 SHA가 유지된다.
2. 본문 중복 제목 15곳만 제거하고 상단 h1·폼 경고·모달/패널 고유 제목과 기존 메뉴 순서를 유지했다. 설명은 숨김 삭제가 아니라 펼칠 수 있는 안내로 남는다.
3. 25개 정적 검사 및 694개 브라우저 판정을 통과했고 발견한 충돌·좁은 표 문제를 수정했다. 기능 태그와 기존 스크립트 비교에서 감사 로그의 검증된 이름 분리 외 변경이 없다.
4. 공통 main은 살아 있는 상단 제목을 참조한다. 모든 메뉴 및 AI 프레임의 실제 Jinja/JS를 Linux 격리 환경에서 검사했다. DB·API·권한 계약에는 변경이 없다.
5. 합성 데이터의 조회·열기·닫기·필터·접힘 조작을 검증했다. 운영 계정·권한·장비·연결 저장이나 실제 모델 생성은 수행하지 않았다.
6. [검토 원문 ZIP](001_Menu_Workspace/reviewed-source.zip)과 [SHA 목록](001_Menu_Workspace/source-manifest.json)에 23개 후보를 보존했다. 병합 및 정리는 이 원문과 일치하는 후보만 대상으로 한다.
7. 메뉴별 스크린샷을 직접 검토했다. 테마 중간 프레임을 제외한 최종 캡처에서 경고·검색·처리 동선과 텍스트 대비, 좁은 화면의 내부 스크롤을 확인했다.
8. 남은 단계는 승인된 서버 백업·적용과 실제 운영/데이터 검증이다. 완료로 선기록하지 않으며 초기 실패 기록과 최종 판정을 구분한다.

운영 반영 후 Validation 1–8:

1. 23개 검증 원문의 LF SHA가 운영 소스·Git·Linux와 일치한다. 기존 변경 9개는 해당 작업에 포함하지 않았다. [후보 병합/정리](001_Menu_Workspace/merge-and-cleanup.json). 기본 Git 작성자 설정이 없어 직전 승인 commit의 작성자 정체성을 해당 commit 실행에만 재사용했으며 전역 설정을 변경하지 않았다.
2. 2026-11-09 08:51:56 KST에 소스 commit `84ebe7f54abdfeb88a8f62df62673a791080b38f`를 활성화했다. [배포·DB 사본 검사](001_Menu_Workspace/deployment.json). 새 파일의 교체 전 SHA를 읽으려던 최초 백업 준비 시도는 서비스 중지 전에 종료됐으며, 기존/신규 경로를 구분해 재시도했다. 해당 부분 사본도 삭제하지 않았다.
3. 병합 후 정적 검사 25개 통과(별도 Linux 브라우저 대상으로 대체한 opt-in 1개 제외). [최종 화면 취합](001_Menu_Workspace/stage-verification.json): 36개 메뉴 화면·348개 판정, AI 대화/연결관리 공통 프레임 10개 화면·346개 판정. 초기 검사 문제와 제품 수정은 위에서 구분했다.
4. 실제 운영 DB의 별도 사본에서 관리자 19개·일반 사용자 7개 화면의 정상 응답과 공통 단일 제목을 확인했다. 일반 사용자의 관리자 화면/API 접근 제한 15건을 포함한 [41개 역할별 확인](001_Menu_Workspace/role-pages-verification.json)을 통과했다. 일부 기존 메뉴는 HTTP 200의 접근 거부/포털 이동 스크립트를 사용하는 기존 계약이며 이를 403 응답으로 오기하지 않는다. 운영 관리자 자격 증명은 사용하지 않았고 관리자 화면의 동적 동작·스크린샷은 합성 Linux 브라우저에서 검증했다.
5. 실제 운영 `test04`에서 PC 1280×720·모바일 384×915의 8개 화면을 확인했다. 프로필 수정/카탈로그 신청의 열기·취소, 결재함 필터, 공개 장비 조건 검색·읽기 전용 상세, 통계 교집합 정상 2대와 안내 펼침/접힘을 확인했다. 장비·계정 정보·권한·연결 저장이나 모델 생성은 하지 않았다. [브라우저 실측](001_Menu_Workspace/production-ui-verification.json).
6. 교체 전 코드·설정·업무/AI DB 등 14개 파일을 서버와 PC의 사용자 전용 경로에 보관하고 SHA를 대조했다. [개인 백업 검증](001_Menu_Workspace/private-backup-verification.json). 실제 DB·키·환경 값은 Git과 보고서에 포함하지 않는다.
7. 실제 화면의 제목은 상단 한 번, 업무 시작 간격은 8개 화면 모두 16px이고 페이지 전체 가로 넘침이 없다. 내 정보 PC의 간격은 121px → 16px(105px 절감). 모달과 필요한 안내는 유지되며 폼은 제출하지 않았다. 뷰포트 override는 해제하고 운영 내 정보 탭을 결과로 남겼다.
8. [데이터/서비스 보존](001_Menu_Workspace/production-preservation.json): 기존 업무·AI 행의 누락 0, AI 기존 열 변경 0, 감사 이력·모든 계정 PreferencesJSON/UpdatedAt 및 비밀 설정·서비스 유닛 유지. 유일한 업무 DB 열 변화는 점검 후 검증용 `test04` 재로그인의 SessionToken 1건이며 [별도 확인](001_Menu_Workspace/production-auth-check.json)했다. 웹 PID 1385434·워커 1385452·보존 타이머 정상, maintenance NORMAL, 활성 요청/가드·예약 문자 0, HTTPS 로그인 200. 장비관리 외 다른 서비스를 제어하지 않았다.

| 화면 | PC 증거 | 모바일 증거 |
|---|---|---|
| 내 정보 | [개선 전](001_Menu_Workspace/before-mypage-pc.jpg) / [개선 후](001_Menu_Workspace/production-mypage-pc.png) | [프로필/환경 설정](001_Menu_Workspace/production-mypage-mobile.png) / [프로필 창](001_Menu_Workspace/production-profile-dialog-mobile.png) |
| 나의 결재함 | [목록](001_Menu_Workspace/production-my-approvals-pc.png) / [안내 펼침](001_Menu_Workspace/production-help-expanded-pc.png) | [목록](001_Menu_Workspace/production-my-approvals-mobile.png) / [신청 창](001_Menu_Workspace/production-catalog-dialog-mobile.png) |
| 공개 장비 | [목록](001_Menu_Workspace/production-public-pc.png) | [목록](001_Menu_Workspace/production-public-mobile.png) / [상세](001_Menu_Workspace/production-public-detail-mobile.png) |
| 통계 | [현황](001_Menu_Workspace/production-dashboard-pc.png) | [현황](001_Menu_Workspace/production-dashboard-mobile.png) |
| 관리자 메뉴(합성 격리 검사) | [권한 표](001_Menu_Workspace/stage-browser-4/permissions-1440-dark.png) / [감사 로그](001_Menu_Workspace/stage-browser-4/audit_logs-1440-dark.png) | [권한 표](001_Menu_Workspace/permission-320-final/permissions-320-dark.png) / [관리자 센터](001_Menu_Workspace/stage-browser-3/admin_center-384-light.png) / [백업 안전 안내](001_Menu_Workspace/stage-browser-3/backup_restore-384-light.png) |
