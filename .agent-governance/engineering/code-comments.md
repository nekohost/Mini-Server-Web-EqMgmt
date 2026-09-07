---
id: engineering.code-comments
version: 1
parent: context.project
source_rules: [RULE-1.3, RULE-4.3.1, RULE-4.3.2, RULE-4.3.3, RULE-4.3.4]
source_validations: []
source_entrypoints: []
human_rule_sections: ["1-3", "4-3-1", "4-3-2", "4-3-3", "4-3-4"]
source_section_digest: 2DCCC5709271A820C9F08419F15CDF237ADC22509F76B84A8D96FEC8D67F72B8
always_load: false
may_relax_parent: false
---

# 코드 주석

모든 함수와 API 라우트 상단에는 다음 메타 주석을 유지한다.

- `[역할]`: 함수 또는 라우트가 수행하는 기능
- `[의존성 관계]`: 의존하는 함수·파일과 이 코드에 의존하는 프론트엔드 요소
- `[변경 시 영향도]`: 수정 시 함께 영향을 받는 위치

추가로 모든 코드 줄에는 해당 줄이 수행하는 작업을 설명하는 상세 주석을 포함한다. 기존 주석을 제거하거나 의미를 축소하지 않는다. 이 요구의 비용이나 코드 품질을 변경하려면 노드 이전과 분리된 정책 개정 승인을 받아야 한다.


