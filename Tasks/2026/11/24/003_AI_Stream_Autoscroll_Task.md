# AI 도우미 출력 자동 스크롤 사용자 우선 작업

work_id: FIX-20261124-AI-STREAM-AUTOSCROLL

- 관련 계획: [Plan 003](../../../Plans/2026/11/24/003_AI_Stream_Autoscroll_Plan.md)
- 관련 보고: [Report 003](../../../Reports/2026/11/24/003_AI_Stream_Autoscroll_Report.md)

- [x] 거버넌스 `validate`·`context` 통과 및 전체 pack 확인
- [x] 자동 스크롤·추론 상자 스크롤 원인 확인과 Plan 작성
- [x] Validation 1~8단계 기록
- [x] `Staging/20261124-ai-stream-autoscroll/` 패치 작성 및 깨끗한 `HEAD` 사본 적용
- [x] 가상 답변 모델 브라우저 시나리오와 단계별 스크린샷 (12/12, 148개 확인)
- [x] 기존 회귀·정적 보안 검사와 수정 전 코드 대비 회귀 검출 확인
- [x] Report·Task 최종 기록 (운영 병합·배포는 범위 밖)
- [x] 사용자 승인 후 운영 병합, 해시 대조, 본 작업 Staging 정리
- [ ] 본 작업 파일 scoped commit·push
- [ ] `eqmgmt-backup` 배포와 라이브 검증
