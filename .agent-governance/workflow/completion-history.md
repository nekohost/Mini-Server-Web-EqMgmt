---
id: workflow.completion-history
version: 1
parent: workflow.plans
source_rules: [RULE-7.4.1, RULE-7.4.2, RULE-7.4.3]
source_validations: []
source_entrypoints: []
human_rule_sections: ["7-4-1", "7-4-2", "7-4-3"]
source_section_digest: 6813ACA121CFD8D675DA3FF1D9D08A9D09B1836EA6496C97B4B6E23E58B810C3
always_load: false
may_relax_parent: false
---

# 완료 이력

개발 완료 후에도 `PROPOSALS.md`와 `ROADMAP.md`의 원본 항목은 삭제하지 않는다. 상태를 `[개발 완료 (FEATURES.md 이관)]` 등으로 갱신하여 이력을 보존한다.

완료된 항목은 `UNIMPLEMENTED_PROPOSALS.md`와 `UNIMPLEMENTED_ROADMAP.md`에서 제거하여 현재 대기열을 최신화한다. 최종 상세 기능 명세는 `FEATURES.md`에 추가한다.


