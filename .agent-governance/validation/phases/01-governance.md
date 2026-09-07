---
id: validation.phase.01-governance
version: 1
parent: validation.orchestration
source_rules: []
source_validations: [VAL-PHASE.1.0, VAL-PHASE.1.1, VAL-PHASE.1.2, VAL-PHASE.1.3, VAL-PHASE.1.4, VAL-PHASE.1.5]
source_entrypoints: []
human_rule_sections: ["10-2", "10-2-1", "10-2-2", "10-2-3", "10-2-4", "10-2-5"]
source_section_digest: 8CF69CB26C43B93D79B1C314BD039DCCFED68D5ED28EADCD7401FCFFEEBC7840
always_load: false
may_relax_parent: false
---

# 1단계: 거버넌스 준수성

계획과 변경이 활성 Rule 노드를 위반하지 않는지 심문한다.

- 프론트엔드와 백엔드의 책임 및 로직 분리가 유지되는가.
- 스키마 변경이 파괴적으로 동작하지 않고 기존 데이터를 보존하는가.
- 운영 코드보다 지정된 Staging 격리 환경을 먼저 사용하는가.
- 요구된 커스텀 규칙을 프레임워크 기본값으로 대체하지 않았는가.
- 외부 라이브러리가 인가되었고 무의존 대안이 제시되었는가.
- 위 목록 밖의 거버넌스 위반 가능성도 추가 탐색했는가.


