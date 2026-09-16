---
id: workflow.multi-agent-handoff
version: 2
parent: core.task-modes
source_rules: [RULE-6.1.3, RULE-7.5.1, RULE-7.5.2, RULE-7.5.3, RULE-7.5.4, RULE-7.5.5]
source_validations: [VAL-PHASE.8.2, VAL-PHASE.8.3]
source_entrypoints: []
human_rule_sections: ["6-1-3", "7-5-1", "7-5-2", "7-5-3", "7-5-4", "7-5-5", "10-9-2", "10-9-3"]
source_section_digest: EAC6F54E645E4836289E5D18D934E49B90B53827EA659C90AC5F9E27CE1CBF61
always_load: false
may_relax_parent: false
---

# 다중 AI 인계

기획·검토 모델과 코딩·실행 모델이 교차 투입될 수 있다. 새 작업자는 자신의 실제 모델·플랫폼과 현재 역할을 식별한다. 역할이 불명확하고 결과를 바꿀 수 있으면 사용자에게 확인한다.

직전 AI가 작성하고 사용자가 승인한 `Plans/`, `Tasks/`, `Reports/`, `Staging_PLAN.md`, `ROADMAP.md`, `UNIMPLEMENTED_ROADMAP.md` 등 관련 문서를 읽고 방향성을 승계한다. 이전 모델의 이름을 복사하지 말고 대화 기록에는 현재 실제 작업자 이름을 사용한다.

이중언어 추적 주석에서 ChatGPT/Codex는 구현과 EN 기준 주석을 담당하고, 추적 코드 계약 또는 EN을 바꾸면 EN revision을 증가시킨다. Gemini는 실제 소스와 EN을 감사한 뒤 KO 본문과 KO revision만 동기화하며, 불일치하면 `CONTRACT-DIVERGENCE`로 보고하고 번역을 보류한다. 별도 구현 지시 없이 Gemini가 실행 코드·EN·API·스키마·설정을 바꾸지 않는다.

Gemini 감사 전에는 Git 상태 snapshot을 남기고 감사 후 diff guard로 snapshot 이후 변화만 검사한다. 기존 다른 작업자의 dirty 변경은 그대로 보존해야 하며, 감사 중 HEAD가 바뀌면 snapshot을 폐기하고 새 기준으로 다시 시작한다.


