# 페이지 제목/작업 버튼 배치 선택적 롤백

2026-09-14 · nekohost.org / eqmgmt-backup 운영 반영·검증 완료

후속 이력: 이 보고서는 선택적 롤백 당시 상태를 보존한다. 이후 사용자 요청의 공통 본문 제목/설명, 그 아래 작업·검색 영역, 원래 계정명과 관리자 연속 배치는 [보고서010](010_Unified_Menu_Headers_and_Toolbars_Report.md)으로 대체됐다. 제목 왼쪽/작업 오른쪽 고정 구조를 재도입한 것은 아니다. 이 릴리스 전용 해시 검사는 `EQM_AUDIT_HEADING_ROLLBACK=1`에서만 실행하며 현재 승인 기준은 `test_unified_ui.mjs`와 공통 화면 검사다.

## 처리 범위

사용자 지시대로 직전 요청의 **2번만 롤백**했다. 전체 릴리스나 DB를 이전 시점으로 되돌리지 않았다.

| 사용자 항목 | 현재 상태 |
|---|---|
| 1. 좁은 상단바·동적 메뉴명 | 유지. 중앙 제목, 왼쪽 이동 버튼 세로 배열, 오른쪽 로그아웃/내 정보/테마·세션, 단어 단위 제목 줄바꿈 |
| 2. 페이지 제목 왼쪽·작업 버튼 오른쪽 고정 | 철회. 개선 직전의 화면별 반응형 배치로 복원 |
| 3. 사용자 선택 작업 버튼 항상 표시 | 유지. 선택0건이면 비활성, 선택/해제/재조회 시 상태 동기화 |
| 4. 관련 관리자 카드 묶음 | 유지. 계정·권한 / 카탈로그·결재 / 로그 / 점검·백업 |

나의/공개 장비는 좁은 화면에서 제목 아래로 작업 버튼이 내려가는 기존 배치다. 마스터 관리의 선택 삭제/새 항목 추가도 제목 오른쪽이 아니라 이전의 탭 영역으로 복원했다. 다른 화면도 일괄 좌우 고정 이전으로 돌렸으며 기존 Standard/Edge 너비 경계, 표 가독성, 검색/CSV 기능은 유지했다.

- 수정9파일: `static/css/layout.css`, 템플릿 `index`, `master_management`, `access_logs`, `access_logs_error_ips`, `lineup_management`, `permissions`, `mypage`, `users_management`.
- 제목 배치만 변경됐던 템플릿7개는 이전 배포의 `before`와 줄바꿈 형식 정규화 기준으로 동일하다.
- CSS는 공통 제목 그리드 규칙을 제거하고 프로필 제목의 기존 nowrap만 복원했다. 사용자 관리 템플릿은 제목/버튼 그룹의 배치 클래스만 복원했다. 배포 도구가 현재 운영 파일에 이 변경만 적용한 예상 결과와 후보가 정확히 일치하는지 검사했다.
- 유지 대상인 JS3개와 공통 상단바/관리자 허브 템플릿2개는 직전 배포와 바이트 해시가 동일하다. CSS의 좁은 상단바·관리자 그룹·disabled 규칙과 사용자 선택 로직도 보존했다.
- FEATURES.md/PROPOSALS.md에 현행 상태를 기록하고 보고서008에는 후속 롤백 안내를 덧붙였다. 기존 이력·무관한 변경·Rule은 보존했다.

## 검증

- 정적/프런트엔드38건 + 실제 템플릿 브라우저19건 = **57건 통과**. 새 검사는 복원7파일/유지5파일의 해시, 공유 파일의 선택적 변경 및 좁은 장비 화면에서 제목 아래 작업 행 복원을 확인한다.
- 16개 실제 템플릿 × 두 스킨 × 9개 폭의 상단바/페이지 경계, 선택0건·일부·전체 선택·목록 갱신, 관리자 그룹, 검색/CSV/표/팝업/설정 회귀를 유지했다. 관리자 기능은 합성 데이터와 네트워크 차단 fixture에서 검사했다.
- 첫 fixture 실행에서 검사 가정 두 가지를 보정했다. Edge 제목의 내부 좌측 여백을 무시한 정렬 비교는 제목 내용의 시작 위치와 비교하도록 수정했고, 관리자 카드 검사는 viewport 변경 후 두 프레임을 기다리도록 했다. 최종 전체19건은 약76초에 통과했다. 서비스 소스를 추가로 바꿔 검사 기준에 맞춘 것은 아니다.
- 실제 기존 일반 사용자 `guide_test_user`로 **PC 중심49상태**, **터치 세로72상태 + 팝업12상태**를 통과했다. 320×568/360×800/390×844/412×915에서 두 스킨의 5화면·검색/CSV 상태를 확인했다. 팝업은 장비 등록/프로필/이메일을 열고 닫기만 했다.
- 실제 정적 자산 해시, 중앙 메뉴명 유지, 페이지 제목 아래 작업 버튼 복원, 이전/상위 이동, 세션 Enter 연장, 설정 저장/복원, 검색/CSV를 확인했다. 서버5xx=0, pageerror=0, 허용 밖 변경 요청0, 관리자 API403 유지. 두 실접속 검사 모두 설정 복원·로그아웃 완료.
- 320px/390px 실제 화면과 비선택 사용자 관리 fixture를 육안 확인했다. 모바일은 Chromium 터치 에뮬레이션이며 실기기/iOS Safari 검증은 아니다. 관리자 계정으로 실제 변경 작업을 수행하지 않았다.

## 운영 반영·데이터 보존

- **2026-09-14 15:57:49 KST**, 현재 HEAD/파일 SHA/PID/cwd/명령을 확인한 후9파일만 원자적으로 적용했다. PID84781에 pidfd/SIGTERM을 사용하고 기존 인수/환경으로 PID86641을 기동했다. 로그인 HTTP200, 후보 해시 일치, 유지5파일 불변, 기동 오류 표식0.
- 복구 자료: `/home/nekohost/.local/share/mini-server-eqmgmt/releases/ui-heading-rollback-20260914T065749Z/`. 디렉터리0700/보존 파일0600으로 변경 전후 소스·온라인 DB 사본·manifest/result·기동 로그를 남겼다. 배포 실패 시 이번9파일만 재복구하도록 구성했으며 실패 복구는 발생하지 않았다. 이 도구는 이전 PID/SHA를 고정한 일회성 배포 근거로 그대로 재실행하지 않는다.
- integrity=ok, FK위반0. 사용자3/장비1/옵션1/노드12 유지. 배포 전 사본과 장비·옵션·노드·메뉴·역할별 메뉴 권한의 전체 행이 동일하다. 사용자 식별 정보·역할·비밀번호 및 모든 사용자의 유효 환경 설정도 보존/복원됐다. 테스트 로그인·세션·접근 로그만 정상 부수 효과다.
- HEAD `5ab042a7cb1a4acd25af64732c6a1f64b644db94` 유지. Git reset/전체 checkout/commit/push, DB 복원, 주 미니서버 배포는 하지 않았다. governance validate 오류/경고0 및 Git diff 공백 검사 통과.

## 증거

- [배포9파일·유지5파일·선택적 변경 확인](heading-rollback/deployment.json)
- [데이터·권한·설정 보존](heading-rollback/postflight.json)
- [실제 PC49상태](heading-rollback/live/live-verification.json) / [세로72·팝업12상태](heading-rollback/portrait/portrait-verification.json)
- [320px 실제 나의 장비](heading-rollback/portrait/screenshots/standard-my_equipment-320.png) / [390px 실제 Edge 나의 장비](heading-rollback/portrait/screenshots/edge-my_equipment-390.png)
- [선택하지 않아도 보이는 사용자 관리 버튼](heading-rollback/fixtures/users-unselected-320.png)

재검증: `tests/test_heading_rollback.mjs`는 이 릴리스 전용 범위 검사다. 화면 회귀는 `tests/test_edge_layout_browser.mjs`, 실접속은 `edge-release/verify-live.mjs`·`verify-portrait.mjs`의 `EQM_LIVE_VARIANT=heading-rollback`을 사용한다. 일반 CI에서 자동으로 실계정에 접속하지 않는다.
