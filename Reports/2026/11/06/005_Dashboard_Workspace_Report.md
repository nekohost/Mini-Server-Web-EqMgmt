---
artifact_id: REPORT-20261106-005
work_id: RELEASE-20261106-DASHBOARD-WORKSPACE
owner: Codex
status: completed
---

# 통계 분포·작업 공간 검증

구현 전 Validation 1–8:

1. Recorder ensure·watcher 11268, legacy/runtime-session-mismatch, 정책 1.8.1의 44노드 오류 0, context 필수 입력 0. 기존 9개 변경과 미추적 파일을 보존한다.
2. 교집합의 상태 분포를 같은 모양으로 표시하고 장비별 상세도 유지한다. 시범 대상은 포털·나의 장비와 그 하위 작업이며 공개 장비와 다른 메뉴의 본문 제목은 그대로 둔다.
3. 기존 status_distribution, equipment_list 및 임시저장 실제 전환을 사용한다. 취소·오류·빈 응답·테마 재표시와 기존 테스트의 옛 제목 기대를 점검한다.
4. 운영 API/DB 변경 없이 화면만 교체한다. 배포 전 현재 서비스 상태와 백업, 배포 후 실제 조회와 데이터 보존을 확인한다.
5. 표시값을 안전한 텍스트로 처리하고 서버의 장비 공개·소유·임시저장 조건을 재사용한다. 운영 장비·시험 계정 설정을 수정하지 않는다.
6. 이전 Git/설정/DB, 검증된 후보와 SHA를 보존하며 다른 작업자의 변경은 포함하지 않는다.
7. 모바일 겹침·가로 넘침과 PC의 남는 공간, 상단 제목·모달 이름·순차 탐색을 점검한다.
8. 화면/상호작용 증거와 검증 한계를 구분한다. 새 차트 의존성이나 외부 모델 호출은 추가하지 않는다.

Staging 정적 검사 19/19, 한국어 데스크톱·모바일 Chromium 9개 화면(211개 판정)을 통과했다. 최초 정적 검사에서 격리 사본에 WebMCP 정적 메타데이터가 누락된 점을 확인하고 사본 구성을 바로잡았다. 화면 캡처 검토에서 넓은 Edge 배치에서 복합 카드가 상단 카드보다 넓고 모바일 제목이 어색하게 줄바꿈되는 점을 발견했다. 세 카드를 같은 레이아웃에 배치하고 선택 항목과 중복된 제목 설명을 줄인 뒤 대시보드 2개 화면의 28개 판정을 다시 통과했다.

- [정적 검사](005_Dashboard_Workspace/stage-static-final.json), [9개 화면 검사](005_Dashboard_Workspace/stage-browser-1/results.json), [수정 후 대시보드 검사](005_Dashboard_Workspace/stage-browser-2/results.json).
- [최종 PC 대시보드](005_Dashboard_Workspace/stage-browser-2/dashboard-1440-dark.png), [최종 모바일 대시보드](005_Dashboard_Workspace/stage-browser-2/dashboard-412-light.png), [모바일 포털](005_Dashboard_Workspace/stage-browser-1/portal-390-dark.png), [나의 장비](005_Dashboard_Workspace/stage-browser-1/my-412-light.png), [임시저장함](005_Dashboard_Workspace/stage-browser-1/draft-412-light.png), [수정 창](005_Dashboard_Workspace/stage-browser-1/edit-1440-dark.png).
- 검사 데이터는 합성 장비다. 검색 교집합 정상 2대·수리 1대, 0건, 서버 오류 후 재검색, 늦은 이전 응답, 특수문자, 개별 상세 목록을 검증했다. 등록/상세/수정/CSV/카탈로그 신청의 열림·닫힘, 임시저장함 왕복, 공개 장비의 기존 제목, 포털 메뉴 순서·키보드 탐색을 확인했다.

검증한 [원문 SHA-256 목록](005_Dashboard_Workspace/source-manifest.json)과 [ZIP](005_Dashboard_Workspace/reviewed-source.zip) 10개 파일을 운영 소스에 병합한 뒤 동일한 정적 검사 19/19와 JS 문법 검사를 통과했다. [후보 정리](005_Dashboard_Workspace/merge-and-cleanup.json).

구현 후 Validation 1–8:

1. 실제 변경 경로로 다시 산출한 정책 노드 32개가 최초 선택과 동일하고 필수 입력은 0개였다. 검증 후보 원문 10개가 Git·서버 원문과 일치한다(LF/CRLF만 정규화).
2. 포털·나의 장비의 본문 중복 제목을 제거하고 임시저장함 이름은 상단 바에 표시했다. 등록·수정·상세 등 고유 작업 제목은 유지한다. 포털 카드 순서와 공개 장비는 시범 변경 대상에서 제외했다.
3. 카테고리·제조사·복합 상태 분포가 같은 렌더링을 사용한다. 모의 데이터로 여러 상태를 확인하고 실제 일반 계정의 '스마트폰 + 삼성'에서는 2대 모두 정상으로 표시되는지 읽기 전용 SQL 집계 및 펼침 목록 2행과 대조했다.
4. 2026-11-06 17:07:49 KST에 운영 코드 `817ca2e0c5d036c940da6967350d72453619edf6`를 활성화했다. 서비스·워커·보존 타이머 정상, 동시 AI 작업 0건. [배포 및 실제 DB 사본 검사](005_Dashboard_Workspace/deployment.json).
5. 운영 폼은 제출하지 않았다. 업무·AI 기존 행의 누락 및 열 변경 0, 감사 기록·계정별 설정 보존. [배포 후 데이터 확인](005_Dashboard_Workspace/production-preservation.json).
6. 교체 전 코드·설정·DB를 포함한 14개 파일을 서버와 PC의 사용자 전용 사본으로 보관하고 SHA를 대조했다. [백업 검증](005_Dashboard_Workspace/private-backup-verification.json). 비밀 값과 실제 DB는 보고서에 포함하지 않았다.
7. 운영 PC 1280×720에서 상단 바 아래부터 첫 장비 현황까지 95px → 16px(79px 절감). 포털·나의 장비·임시저장함에서는 412px 너비에서도 16px이었다. PC 복합 결과는 좌우, 모바일은 상하 배치다. 검사한 화면에서 페이지 전체 가로 넘침 없음. [브라우저 실측](005_Dashboard_Workspace/production-ui-verification.json).
8. 일반 계정의 보유 장비는 0대였다. 등록 창·CSV·임시저장함은 운영에서 열어 확인했고 장비 상세·수정은 합성 데이터가 있는 Staging에서 검증했다. 모바일은 브라우저 뷰포트 검증이며 실기기 측정은 아니다.

| 운영 화면 | PC | 모바일 |
|---|---|---|
| 복합 검색 분포 | [도넛·수량표](005_Dashboard_Workspace/production-dashboard-wide.jpg) | [상하 배치](005_Dashboard_Workspace/production-dashboard-mobile.jpg) |
| 메인 포털 | [개선 전](005_Dashboard_Workspace/before-portal-pc.jpg) / [개선 후](005_Dashboard_Workspace/production-portal-pc.jpg) | [모바일 포털](005_Dashboard_Workspace/production-portal-mobile.jpg) |
| 나의 장비 | [검색·등록·목록](005_Dashboard_Workspace/production-my-pc.jpg) | [목록](005_Dashboard_Workspace/production-my-mobile.jpg) / [임시저장함](005_Dashboard_Workspace/production-draft-mobile.jpg) / [등록 창](005_Dashboard_Workspace/production-register-mobile.jpg) |
