---
id: engineering.frontend-responsive
version: 1
parent: context.stack
source_rules: [RULE-3.2.1, RULE-3.2.2, RULE-3.2.3, RULE-3.2.4]
source_validations: [VAL-PHASE.2.4, VAL-PHASE.7.1, VAL-PHASE.7.2, VAL-PHASE.7.4]
source_entrypoints: []
human_rule_sections: ["3-2-1", "3-2-2", "3-2-3", "3-2-4", "10-3-4", "10-8-1", "10-8-2", "10-8-4"]
source_section_digest: 4749F02EE3E52E466A3FF3CD8F45565A6DBC0E4723A7DB5838499C8878731207
always_load: false
may_relax_parent: false
---

# 반응형 프론트엔드

- 접은 스마트폰·세로 폴더블: `grid-cols-1`
- 펼친 폴더블·태블릿: `sm:grid-cols-2`
- PC·대형 화면: `lg:grid-cols-3 xl:grid-cols-4`

무거운 JavaScript 라이브러리를 피하고 Vanilla JavaScript와 경량 Tailwind CSS를 우선한다. UI 변경은 잘못된 동선의 피드백, 데드엔드 방지, 입력 1차 검증과 대상 화면 크기의 사용성을 함께 확인한다.


