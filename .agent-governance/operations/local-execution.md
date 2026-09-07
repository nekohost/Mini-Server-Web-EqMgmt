---
id: operations.local-execution
version: 1
parent: context.deployment-topology
source_rules: [RULE-5.1.1]
source_validations: [VAL-PHASE.3.0]
source_entrypoints: []
human_rule_sections: ["5-1-1", "10-4"]
source_section_digest: 2939E9C073A7F776046655B1CD5B4DB256D050DA48969FE6C4773C80DB92E84C
always_load: false
may_relax_parent: false
---

# Windows 개발 PC 제한

Windows PC는 소스 작성과 Git Push 용도다. 이 환경에서 애플리케이션 로컬 실행이나 동작 테스트를 수행하지 않는다.

파일 조회, 정적 분석, 문법 구조 검사처럼 애플리케이션을 구동하지 않는 비파괴 검사는 가능하다. 실행 검증이 필요하면 `operations.server-execution`을 따른다.


