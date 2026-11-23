# AI 도우미 문맥 한도·다단계 재압축 및 중단 사유 화면 표출 작업

work_id: FIX-20261123-AI-CONTEXT-ERROR-VISIBILITY

- 관련 계획: [Plan 001](../../../Plans/2026/11/23/001_AI_Context_Budget_and_Error_Visibility_Plan.md) · [항목 4 보류 계획 Plan 002](../../../Plans/2026/11/23/002_AI_Context_Token_Calibration_Plan.md)
- 관련 보고: [Report 001](../../../Reports/2026/11/23/001_AI_Context_Budget_and_Error_Visibility_Report.md)

- [x] preflight (`conversation-recorder.mjs ensure`) 및 Plan 001/002·Task 작성
- [x] 병렬 하위 작업자 A: 백엔드 Step 0 최악 오버헤드·여유분 예약, Step 1+ 재압축, `CONTEXT_LIMIT`·안전 진단 로그·queued 취소 사유 Staging 구현 및 테스트 작성
- [x] 병렬 하위 작업자 B: 프론트엔드 말풍선 오류/코드 표출(`formatJobFailure`, `jobErrorNotice`, `progress`, CSS) Staging 구현 및 Node/Chromium 테스트 작성
- [x] 운영 루트 무변경 확인 및 Linux(`eqmgmt-backup`) 격리 백엔드·정적보안·Node·실제 Chromium UI 검증 실행
- [x] Validation 1~8 순차 검증 및 Report 001 작성 (운영 루트 병합·배포는 사용자 승인 후 진행)
- [x] 사용자 승인 후 운영 루트 병합, 정적·격리 재검증, Git commit/push 및 백업 서버 적용
