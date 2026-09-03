---
id: workflow.plans
version: 1
parent: core.task-modes
source_rules: [RULE-7-PREAMBLE, RULE-7.2.1, RULE-7.2.2]
source_validations: [VAL-PREAMBLE, VAL-CORE.1]
source_entrypoints: []
human_rule_sections: ["7", "7-2-1", "7-2-2", "10", "10-1-1"]
source_section_digest: 048CC51BF147E7BEA51D44646A99B9EEE20F30C2D003D30946B7E6AC4E053AD7
always_load: false
may_relax_parent: false
---

# 기획 문서

기능 추가, 버그 수정, 아키텍처 개편 전에 Plan을 작성한다. 영구 계획은 `Plans/YYYY-MM-DD_XXX_Plan.md` 형식으로 보존하고 조율한다.

계획 수립 직후 실제 코드 작성이나 운영 병합 전에 Validation 1~8단계를 순서대로 수행한다. 계획 승인만으로 파괴적 작업이나 이후 단계 전체의 권한이 발생하지 않는다.


