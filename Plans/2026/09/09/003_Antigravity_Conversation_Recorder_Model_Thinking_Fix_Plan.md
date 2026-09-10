---
artifact_id: PLAN-20260909-003
work_id: WORK-20260909-ANTIGRAVITY-THINKING-FIX
created_at: 2026-09-09T14:29:51.075+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/09/005_Antigravity_Conversation_Recorder_Model_Thinking_Fix_Task.md
  - ../../../../Reports/2026/09/09/010_Antigravity_Conversation_Recorder_Model_Thinking_Fix_Report.md
---
# Antigravity 대화 기록기 모델 추론 필터 및 원문 잘림 보완 계획

- 작성일: 2026-09-09
- 작업 모드: 거버넌스 도구 개선 및 대화 기록 복구
- 관련 계획 ID: `003`
- 관련 Task: `Tasks/2026/09/09/005_Antigravity_Conversation_Recorder_Model_Thinking_Fix_Task.md`
- 목표: Antigravity 대화 기록기에서 Gemini 모델의 `thinking` 동반 최종 응답이 누락되는 버그를 해결하고, `transcript_full.jsonl` 연동을 통해 원문 보존성을 확보한 뒤 누락된 대화를 복구한다.

## 1. 배경 및 문제 정의

1. **최종 응답 누락 (`!item.thinking` 버그)**:
   - `conversation-recorder/antigravity.mjs`의 `visibleFinal` 판정 로직에 `!item.thinking` 조건이 포함되어 있음.
   - 실제 Antigravity 환경에서 Gemini Thinking 모델(Gemini 3.8 Flash High 등)은 최종 응답(`PLANNER_RESPONSE`)에 내부 사고(`thinking`)와 사용자 응답(`content`)을 함께 반환함.
   - 이로 인해 `!item.thinking`이 `false`가 되어 사용자에게 보여진 최종 응답 전체가 누락됨.
2. **장문 응답 텍스트 축약(Truncation) 대응 부재**:
   - 일정 길이를 초과하는 응답은 `transcript.jsonl`에서 `truncated_fields: ["content"]`로 축약되며, 전체 원문은 `transcript_full.jsonl`에만 보존됨.
   - 현재 어댑터는 `transcript_full.jsonl`을 참조하지 않아 축약된 불완전한 텍스트가 수집될 위험이 존재함.

## 2. 작업 범위

1. **어댑터 수정 (`.agent-governance/tooling/conversation-recorder/antigravity.mjs`)**:
   - `discoverConversationFiles`: `transcript_full.jsonl` 경로 후보(`transcriptFullPath`) 수집 추가.
   - `collectAntigravityEvents`: `transcriptFullPath` 존재 시 UTF-8 텍스트 병렬 로드.
   - `inspectConversation`: `fullText` 전달 시 `fullRows` 파싱 및 반환.
   - `conversationEvents`:
     - `visibleFinal` 조건에서 `!item.thinking` 제거 (`content` 존재 및 `tool_calls` 부재 조건 유지).
     - `item.truncated_fields`에 `content`가 포함되고 `info.fullRows`가 존재할 경우, 대응하는 `fullRow`의 완전한 `content`를 채택.
     - `item.thinking` 자체는 이벤트 `content`에 포함하지 않아 Rule 6-2-5(추론 비기록)를 엄격히 준수.
2. **단위 테스트 보강 (`.agent-governance/tooling/conversation-recorder.test.mjs`)**:
   - `thinking` 필드가 포함된 `PLANNER_RESPONSE`가 정상적으로 `final_answer` 이벤트로 추출되는지 검증.
   - `truncated_fields: ["content"]` 및 `transcript_full.jsonl` 존재 시 완전한 원문이 보존되는지 검증.
3. **대화 기록 재조정 및 누락 발언 복구**:
   - `node .agent-governance/tooling/conversation-recorder.mjs reconcile --force` 실행을 통해 금일(2026-09-09) 누락되었던 Antigravity의 응답 복구.
   - `Chat/2026/09/09.md` 무결성 검증.
4. **결과 보고서 발간**:
   - `Reports/2026/09/09/010_Antigravity_Conversation_Recorder_Model_Thinking_Fix_Report.md` 발간.

## 3. 복구 및 롤백 절차

- 수정 대상 파일(`.agent-governance/tooling/conversation-recorder/antigravity.mjs`, `conversation-recorder.test.mjs`)은 Git diff를 통해 즉시 원복 가능.
- `Chat/2026/09/09.md`는 재조정 전 백업 또는 Git 체크아웃으로 복귀 가능.

## 4. 완료 기준

- `conversation-recorder.test.mjs` 전체 테스트 100% 통과 (신규 테스트 포함).
- `governance-tool.mjs validate` 통과 (0 errors, 0 warnings).
- `Chat/2026/09/09.md`에 Antigravity의 누락 발언(로드맵 안내, 사실관계 보고 등)이 완전한 원문으로 시간순 삽입 복구됨.
