---
artifact_id: REPORT-20261109-004
work_id: RELEASE-20261109-MENU-TOOLBARS
owner: Codex
status: completed
---

# 장비 및 메뉴 도구줄 운영 배포

1. Recorder ensure와 정책 1.8.1 검사를 통과했다. legacy/runtime-session-mismatch에 대한 context 30개 노드를 확인했다.
2. 배포 대상은 002의 장비 개선을 포함한 003의 검토 원문이다. 사용자용 AI 대화와 관리자 연결 관리의 범위를 구분한다.
3. Git 기준선과 후보 ZIP·파일 SHA를 대조하고 운영 루트 병합 후 정적 회귀를 다시 실행한다.
4. 화면·정적 리소스와 관련 검사에 한정한 변경이다. Linux에 적용하기 전에 실제 데이터의 격리 사본에서 기존 역할별 화면을 확인한다.
5. 운영 브라우저는 조회, 화면 열기·닫기와 검색만 사용한다. 운영 데이터·인증 자료는 상세 검증 로그나 저장소에 포함하지 않는다.
6. 교체 전 서비스 식별, 활성 AI 작업과 운영 파일을 확인한다. 코드와 DB·설정 사본을 서버의 비공개 복구 위치에 보존한다.
7. PC와 모바일에서 기본 배치, 줄바꿈, 가로 넘침, 조회와 작업 도구 접근성을 확인한다.
8. staging 검사와 실제 HTTPS 검증, 역할별 접근 및 운영 서비스 상태를 각각 기록한다.

## 배포 및 운영 검증

2026-11-09 10:45:09 KST에 실행 소스 `3a348ffc24af68393d309f30baa0fee57b9a4a61`를 활성화했다. 접수 제한 전 확인부터 운영 재개 후 검증까지 34.05초가 걸렸다. 웹·AI 워커·보존 타이머가 정상이고 점검 상태는 `NORMAL`이다. [배포 기록](004_Menu_Toolbars_Release/deployment.json)

1. **원문과 배포 범위.** 장비 시범 002의 6개 파일과 통합 003의 26개 파일을 각각 보관 ZIP의 SHA-256과 대조했다. 병합 전에 운영 참조 50개가 staging 작성 당시와 같았다. 실제 배포한 템플릿 15개, CSS 3개, 테스트 8개는 Windows 줄바꿈만 정규화하면 보관 원문·Git blob·Linux 파일이 모두 일치했다. [파일별 대조](004_Menu_Toolbars_Release/merged-sources.json)
2. **사용자 동선.** 실제 HTTPS에 일반 권한 시험 계정 `test05`로 로그인했다. 장비 목록에서 조건검색·CSV·임시저장함을 열고 돌아오는 동작, 결재함 상태 조회와 카탈로그 신청 창 열기·닫기, 통계 복합 검색 결과를 PC와 모바일에서 각각 확인했다. 화면 수정·등록·삭제 없이 PC·태블릿·모바일 9개 화면과 12개 기능 동작을 확인했다. [운영 브라우저 실측](004_Menu_Toolbars_Release/production-ui.json)
3. **검사.** 운영 루트 병합 후 Node 정적 검사 36개, JS 문법과 Python 구문 검사를 통과했다. 정적 실행의 선택형 브라우저 항목 1개는 Linux 실제 브라우저로 별도 검사했다. staging의 83개 조건·1,811개 판정에 이어, 배포 후 관리자 화면 4종을 합성 데이터로 재구동한 8개 조건·151개 판정도 통과했다. `git diff --check`가 감사 로그 템플릿의 줄 끝 공백 4곳을 표시했으며, 검토본과 바이트 일치를 유지했다. [병합 후 정적 결과](004_Menu_Toolbars_Release/merged-static.json) · [관리자 화면 재검증](004_Menu_Toolbars_Release/admin-regression/results.json)
4. **권한과 실데이터 사본.** 배포 커밋과 운영 DB 사본으로 관리자 화면 19개와 일반 사용자 화면 7개가 열리고 관리 화면·API 15건이 일반 사용자에게 차단됨을 확인했다. 별도로 실제 운영 일반 계정에서 관리자 API 3곳과 AI 연결 관리 화면이 모두 HTTP 403이었다. 관리자 정상 화면은 격리 사본과 합성 브라우저에서 확인했다. [사본 역할별 검사](004_Menu_Toolbars_Release/isolated-roles.json)
5. **HTTP·캐시.** 배포 전 CSS ETag를 사용해 실제 HTTPS로 재요청했다. 세 CSS 파일 모두 HTTP 200으로 새 본문을 반환했고 SHA가 일치했다. 로그인 200, 인증 전 화면 리다이렉트와 API 401도 확인했다. [운영 HTTPS](004_Menu_Toolbars_Release/public-http.json)
6. **복구와 기존 데이터.** 배포 전 DB와 환경·서비스 설정·이전 코드 등 복구 파일 14개를 서버와 현재 PC의 사용자 전용 디렉터리에 보관하고 SHA를 대조했다. 웹 재기동 직후 업무 18개·AI 17개 테이블과 감사 이력이 유지됐다. 실제 브라우저 검사 뒤에도 기존 업무·AI 행 누락 0건, 기존 AI 열 변경 0건이었다. 일반 로그인으로 `test05`의 세션 토큰 1건이 갱신됐다. 전체 계정 환경 설정과 기존 서버 환경·유닛은 동일했다. 사후 확인의 첫 조회에서 환경설정 컬럼이 있는 테이블을 잘못 지정해, 실제 `user_settings` 스키마로 고쳐 읽기 전용 대조를 다시 통과했다. [백업 대조](004_Menu_Toolbars_Release/backup-verification.json) · [데이터·서비스 보존](004_Menu_Toolbars_Release/preservation.json)
7. **화면 확인.** 아래 실제 운영 화면에서 지정한 조작의 최소 높이는 모두 44px, 글자는 13px였다. 페이지 전체 가로 넘침은 0px였다. 표가 넓으면 표 영역 안에서 스크롤된다. 모바일 수치는 Chromium의 CSS 화면 폭 기준이다. 표에 기재한 줄 수는 시험 계정의 목록과 화면 설정에서 측정했다.
8. **이력.** 원본 002·003의 계획·검사·ZIP과 배포 증거를 보존했다. 병합한 두 staging 임시 묶음만 정리했다. 다른 작업의 변경을 제외해 소스 커밋을 만들었고 범위에 해당하는 완료 항목만 이력에 반영했다. 사용자 AI 채팅의 원문 템플릿·CSS·JS는 이전 운영 버전과 같다.

| 실제 운영 화면 | 1440px | 820px | 384px |
|---|---|---|---|
| 나의 장비 | [1줄](004_Menu_Toolbars_Release/production/equipment-desktop.png) | [2줄](004_Menu_Toolbars_Release/production/equipment-tablet.png) | [3줄](004_Menu_Toolbars_Release/production/equipment-mobile.png) |
| 나의 결재함 | [1줄](004_Menu_Toolbars_Release/production/inbox-desktop.png) | [2줄](004_Menu_Toolbars_Release/production/inbox-tablet.png) | [3줄](004_Menu_Toolbars_Release/production/inbox-mobile.png) |
| 통계 복합 검색 | [1줄](004_Menu_Toolbars_Release/production/dashboard-desktop.png) | [1줄](004_Menu_Toolbars_Release/production/dashboard-tablet.png) | [2줄](004_Menu_Toolbars_Release/production/dashboard-mobile.png) |
