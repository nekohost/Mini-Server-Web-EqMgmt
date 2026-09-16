---
id: context.project
version: 2
parent: core.kernel
source_rules: [RULE-1.1, RULE-1.3]
source_validations: []
source_entrypoints: []
human_rule_sections: ["1-1", "1-3"]
source_section_digest: ADC1F7C5C4E1C92625EA78E53E0431FEE821C51C76BFF02B72212C5534A17AEB
always_load: true
may_relax_parent: false
---

# 프로젝트 문맥

이 저장소는 개인 보유 장비와 자산을 등록·관리하는 Flask 기반 웹 애플리케이션이다. Python Flask 백엔드와 REST API를 학습하고 실제 미니서버에서 운영하는 목적을 함께 가진다.

사용자는 한국어로 프로젝트 이력과 설계 의도를 다시 읽는 유지보수자다. 모든 코드 변경은 상세 설명 주석과 의존성 파급 안내를 포함해야 하며, 핵심 함수·API·비자명한 계약은 영문 기준 주석과 코드 감사 후의 한국어 동기화본을 함께 추적한다. 자명한 행까지 이중언어화를 강제하지 않으며 구체적 형식과 revision·hash 규칙은 `engineering.code-comments`를 따른다.


