---
id: workflow.staging-merge
version: 2
parent: operations.staging
source_rules: [RULE-7.3.1, RULE-7.3.2, RULE-7.3.3, RULE-7.3.4]
source_validations: [VAL-PHASE.4.0]
source_entrypoints: []
source_human: [HUMAN-11.6, HUMAN-11.7, HUMAN-11.8]
human_rule_sections: ["7-3-1", "7-3-2", "7-3-3", "7-3-4", "10-5", "11-6", "11-7", "11-8"]
source_section_digest: A3E45F0F2038DF7781336A2D169C632C3813D302172B213EF95F337CB535F934
always_load: false
may_relax_parent: false
---

# Staging 검증과 병합

운영 코드를 수정하기 전에 Staging 모의 결과물을 작성하고 검증한다. 사용자가 검증 결과를 승인한 뒤에만 운영에 병합한다.

사용자가 Staging 통합 Rule에 직접 추가했거나 명시적으로 승인한 정책은 운영 병합에서 누락하거나 이전 초안으로 덮어쓰지 않는다. 통합 Rule, 가리키는 실행 노드, 추적성 원장, manifest 해시·버전에 같은 의미와 변경 상태가 유지되는지 병합 전에 정규 파서 기반 `validate`로 대조한다.

Rule 변경 병합에는 `sync-status`가 보고한 변경 섹션 전체, 그 상태의 `currentRuleHash`를 사용한 `sync-plan`과 `validate`, 섹션 기준선 및 대상 노드의 `source_section_digest` 갱신이 모두 포함되어야 한다. 어느 하나라도 불일치하면 운영 병합을 중지한다.

병합 완료 후 Staging 임시 파일은 정리하여 빈 상태로 유지한다. 단, `Staging_PLAN.md`는 먼저 `Plans/YYYY-MM-DD_작업내용_Plan.md`로 이관·영구 보존한 후 삭제한다.

정리는 파괴적 작업이므로 정확한 대상과 보존 예외를 확인하고 승인 범위 안에서 수행한다.

