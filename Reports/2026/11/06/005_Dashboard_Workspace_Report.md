---
artifact_id: REPORT-20261106-005
work_id: RELEASE-20261106-DASHBOARD-WORKSPACE
owner: Codex
status: in-progress
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

검증한 [원문 ZIP과 SHA-256 목록](005_Dashboard_Workspace/source-manifest.json) 10개를 운영 소스에 병합한 뒤 동일한 정적 검사 19/19와 JS 문법 검사를 통과했다.
