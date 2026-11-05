---
artifact_id: PLAN-20261105-002
work_id: STAGING-20261105-AI-UX-TRASH
parent_work_id: REVIEW-20261105-AI-UX-RETIREMENT
adopted_from: PLAN-20261105-001
owner: Codex
created_at: 2026-11-05
status: complete
---

# AI 도우미 1~7번 승인 계획의 Staging 실행 색인

상세 설계와 수용 기준은 사용자가 구현 전에 승인한 [001 계획](001_AI_Assistant_UX_and_Strata_Retirement_Plan.md)을 그대로 승계한다. 이 문서는 실행 단계의 독립 work_id와 Task/Report를 연결하는 색인이며, 사전에 작성한 승인 설계를 대체하거나 새로운 구현 승인을 만들지 않는다.

사용자 승인: “1~7번 계획사항을 staging에 반영”하고 독립 작업은 하위 에이전트로 분담한다. Staging 구현을 넘어서는 운영 소스 병합·Git push·Linux 서비스 적용·실제 대화 삭제는 이 실행 범위에 포함하지 않는다.

순서:

1. 기존 001 Plan/Task/Report와 현재 root 소스를 확인하고, Task 002에 작업을 분리한 뒤 Report 002에 구현 전 Validation 1~8을 기록한다.
2. 사용자 UI, 관리자 UX/옛 UI 정리, v4 저장소/worker를 세 하위 작업자에게 나누고 부모가 조회·문맥·API·권한/경합을 통합한다. 후보는 `Staging/20261105-ai-ux-trash/overlay`에 둔다.
3. 구문/정적 대조 후 Linux의 합성 DB·가짜 모델·실제 Chromium으로 원래 회귀와 새 반례를 실행한다. 실패는 해당 구현/검증 계약과 대조해 수정하며 오류를 성공으로 바꾸지 않는다.
4. 실제 검증 결과·source fingerprint·원본 보존·화면 문제/수정·복귀/이전 경계를 Report 002와 후보 설치 문서에 보존한다.

산출물은 [Task 002](../../../../Tasks/2026/11/05/002_AI_Assistant_Seven_Improvements_Staging_Task.md), [Report 002](../../../../Reports/2026/11/05/002_AI_Assistant_Seven_Improvements_Staging_Report.md), 후보 `README.md`와 `INSTALL-AND-VALIDATION.md`를 기준으로 한다. 구현 전 검토 근거와 실제 실행 결과의 시점을 구분하며, 이미 승인받은 001 계획이 코드 작성 전에 존재했다는 기록을 유지한다.
