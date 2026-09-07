---
id: validation.phase.02-user-intent
version: 1
parent: validation.orchestration
source_rules: []
source_validations: [VAL-PHASE.2.0, VAL-PHASE.2.1, VAL-PHASE.2.2, VAL-PHASE.2.3, VAL-PHASE.2.4, VAL-PHASE.2.5]
source_entrypoints: []
human_rule_sections: ["10-3", "10-3-1", "10-3-2", "10-3-3", "10-3-4", "10-3-5"]
source_section_digest: 742BDBC6A0A4F07E204B7CC9F6AFE653CE6A4CE4AC71A8ED936696C7099C6EFA
always_load: false
may_relax_parent: false
---

# 2단계: 사용자 의도 달성도

최초 요청과 계획·결과 사이의 간극을 대조한다.

- 시스템 고유 요구가 데이터 모델과 설계에 왜곡 없이 반영되었는가.
- 기존 거버넌스와 문서 워크플로우가 통합되었는가.
- 사용자 제약 중 묵인되거나 누락된 항목이 있는가.
- 기대 UI/UX 동선이 설계에 반영되었는가.
- 단기 해결과 향후 확장을 함께 수용하는가.
- 표면적 요청 뒤의 실제 목적을 훼손하는 추가 변경이 없는가.


