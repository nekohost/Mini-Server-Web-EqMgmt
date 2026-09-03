---
id: workflow.multi-agent-handoff
version: 1
parent: core.task-modes
source_rules: [RULE-6.1.3, RULE-7.5.1, RULE-7.5.2, RULE-7.5.3, RULE-7.5.4]
source_validations: [VAL-PHASE.8.2, VAL-PHASE.8.3]
source_entrypoints: []
human_rule_sections: ["6-1-3", "7-5-1", "7-5-2", "7-5-3", "7-5-4", "10-9-2", "10-9-3"]
source_section_digest: 70B8BF07A4077DEC0817BEFC95244AF360629FFDC6D02FFD48628420EB52F63E
always_load: false
may_relax_parent: false
---

# 다중 AI 인계

기획·검토 모델과 코딩·실행 모델이 교차 투입될 수 있다. 새 작업자는 자신의 실제 모델·플랫폼과 현재 역할을 식별한다. 역할이 불명확하고 결과를 바꿀 수 있으면 사용자에게 확인한다.

직전 AI가 작성하고 사용자가 승인한 `Plans/`, `Staging_PLAN.md`, `ROADMAP.md`, `UNIMPLEMENTED_ROADMAP.md` 등 관련 문서를 읽고 방향성을 승계한다. 이전 모델의 이름을 복사하지 말고 대화 기록에는 현재 실제 작업자 이름을 사용한다.


