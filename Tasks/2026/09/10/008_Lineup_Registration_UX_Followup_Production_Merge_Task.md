---
artifact_id: TASK-20260910-008
work_id: WORK-20260910-LINEUP-REGISTRATION-UX-FOLLOWUP
created_at: 2026-09-10T20:32:42.000+09:00
related_artifacts:
  - ../../../../Plans/2026/09/10/004_Lineup_Registration_Modal_and_Node_Add_UX_Followup_Plan.md
  - ../../../../Reports/2026/09/10/016_Lineup_Registration_UX_Followup_Review_Report.md
  - ../../../../Reports/2026/09/10/017_Lineup_Registration_UX_Followup_Production_Merge_Report.md
  - ../../../../Reports/2026/09/28/001_Lineup_Registration_UX_Followup_Closure_Report.md
---
# [Task] 장비등록 UX 후속 보완 운영 소스 반영

- `work_id`: `WORK-20260910-LINEUP-REGISTRATION-UX-FOLLOWUP`
- 상태: **완료 — Git push·백업 서버 적용·Chrome 실브라우저 검증 완료 (2026-09-28)**
- 사용자 승인: 2026-09-10 운영 반영 명시 승인

## 작업 목록

- [x] Review 016 필수 보완 2건을 Staging 후보에 반영
- [x] 빈 노드 조합 안내 문구 보강
- [x] 모달 재오픈 시 body scrollTop 초기화
- [x] Staging 회귀 8/8 통과
- [x] 운영 `templates/index.html` 병합
- [x] 운영 Proposal 047 UI 회귀 테스트 갱신
- [x] 운영 UI 회귀 8/8 통과
- [x] governance validate/sync-status 통과
- [x] Git commit/push — 기존 구현 `31f8027`, 실브라우저에서 발견한 스크롤 초기화 결함 보완 `3ced6e8`
- [x] Linux pull·실브라우저/서비스 검증 — 백업 서버 `eqmgmt-backup`, `nekohost.org`, 일반 사용자 테스트 계정으로 확인

## 2026-09-28 잔여 작업 완료 근거

- 과거 구현은 이미 Git 이력과 서버에 포함되어 있었지만 체크리스트가 갱신되지 않았다.
- 실제 Chrome에서 모달 재열기 시 `scrollTop=393`이 남는 결함을 발견하여, 모달 표시 후 스크롤 초기화하도록 보완했다. 신규·수정 모달을 실행하는 회귀 테스트를 추가했다.
- UI 회귀 15/15, 카탈로그 정적 회귀 5/5 통과. 운영 Chrome에서 취소 후 재열기 `393→0`, X 닫기 후 재열기 `328→0`을 확인했다.
- PC 및 320×640·390×844·768×600 viewport에서 모달 높이, 본문 독립 스크롤, 닫기·저장 버튼의 화면 내 배치를 확인했다.
- 백업 서버 fast-forward pull·서비스 재시작 완료. HTTP 200, DB 무결성 정상, 외래키 위반 0건, 배포 전후 업무 테이블 10개 동일.
- 상세 근거와 검증 범위: [완료 보고서](../../../../Reports/2026/09/28/001_Lineup_Registration_UX_Followup_Closure_Report.md).
