# AI 도우미 다단계 웹 검색 도구 호출 호환·보정 작업

work_id: FIX-20261124-AI-FOLLOWUP-WEB-SEARCH

- 관련 계획: [Plan 001](../../../Plans/2026/11/24/001_AI_Followup_Web_Search_Tool_Compatibility_Plan.md)
- 관련 보고: [Report 001](../../../Reports/2026/11/24/001_AI_Followup_Web_Search_Tool_Compatibility_Report.md)

- [x] `preflight` (`conversation-recorder.mjs ensure`) 및 백업 서버 장애 작업(`f24fee369adc41b2b992fee39164acfd`) 원인 규명
- [x] Claude Opus 5.5 (`xhigh`) 독립 계획 검토 및 6건 보완 반영(`Plan 001` · `Task 001` 작성)
- [x] `Staging/20261124-ai-search-followup/` 초기 격리 구현 (`policy.py`, `recovery.py`, `domain.py`, `__init__.py`, 테스트)
- [x] 1차 정적 보안·Linux `tmpfs` (356/356)·CA/메일 (51/51) 가상 테스트 및 `Report 001` 초안 완료
- [x] 웹 검색 한도 확장(`MAX_SEARCHES = 5`, `SEARCH_RESERVATION = 160000`, `last_step = 8`, `w <= 5`, `public_web_sources <= 5`) Staging 반영 및 재검증
- [x] Staging -> 운영 루트 병합, 루트 기준 백엔드·브라우저(`web-search`, `recovery`)·CA/메일·정적 보안·거버넌스 재검증 및 Staging 정리
- [ ] 본 작업 13개 파일 scoped Git commit/push 및 백업 서버(`eqmgmt-backup`) 무중단 배포(`deploy_ai_ux_release.py`)·라이브 검증
- [ ] `Report 001` 및 `Task 001` 최종 완료 기록
