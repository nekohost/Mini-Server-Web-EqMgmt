---
id: tools.conversation-exception
version: 1
parent: tools.read-execute
source_rules: [RULE-8.0, RULE-6.1.6]
source_validations: []
source_entrypoints: []
source_human: [HUMAN-6.1.6-PLATFORM]
human_rule_sections: ["6-1-6", "8-0"]
source_section_digest: 6FACE30F55CEED503D7050ABFD8B6B27F6FB9879CA76D81218B1744751A47A8E
always_load: false
may_relax_parent: false
---

# Chat 기록 예외

도구 규칙 제8조의 일반 터미널 쓰기 금지는 `Chat/` 대화 저장에는 적용하지 않는다. Chat 저장은 제6조를 우선한다.

현재 플랫폼의 capability profile에서 원문 완전성·Diff·Undo를 제공하는 구조화된 편집 도구를 우선한다. Codex에서는 그러한 구조화 도구가 정상 동작하는 동안 터미널 append를 기본값으로 사용하지 않는다.

Antigravity에서 보고된 내장 API의 지속적인 누락·환각성 오기입은 해당 플랫폼 위험으로 기록한다. 어느 플랫폼이든 실제 누락이나 오기입 때문에 터미널 append가 필요하면 사용자에게 필요성과 절차를 먼저 보고하고 승인을 받은 뒤 `records.encoding`의 UTF-8 중간 파일 및 리터럴 Here-String 절차를 따른다. 이 예외를 다른 파일 쓰기로 자동 확장하지 않는다.


