---
id: engineering.data-model
version: 1
parent: context.project
source_rules: [RULE-3.1.1, RULE-3.1.2]
source_validations: []
source_entrypoints: []
source_human: [HUMAN-3.1.1-DB-DEFERRAL]
human_rule_sections: ["3-1-1", "3-1-2"]
source_section_digest: 00E84EA6639179DBF0D85B5390A8501E1A80AF47A9D66B82C4625B4333856C82
always_load: false
may_relax_parent: false
---

# 장비 데이터 모델

`id`, `name`, `category`, `manufacturer`, `model_name`, `purchase_date`, `serial_number`, `memo`는 프로젝트 초창기에 확인된 기준 필드다. 이후 개발로 운영 DB 구조가 달라졌을 수 있으므로 현재 운영 스키마의 확정값으로 단정하지 않는다.

`[제안-013]` DB 백업·복원 기능이 구현되고 원본 운영 DB 백업을 로컬로 안전하게 받은 뒤 실제 스키마를 확인한다. 그전에는 실제 운영 DB를 열람하지 않고, 이 기준 목록만으로 스키마를 변경하거나 현재 필드를 확정하지 않는다. 별도의 사용자 명시 승인이 없는 운영 DB 조회·스키마 변경은 fail-closed로 중지한다.

확인된 실제 스키마가 이 기준선과 다르면 데이터 보존 원칙에 따라 차이를 보고하고 Rule·이 노드·추적성·manifest를 같은 변경 단위에서 갱신한다. 생성, 조회, 수정, 삭제 기능은 확인된 스키마를 기준으로 완전하게 제공해야 한다.

필드 변경 시 `engineering.schema-evolution`과 `engineering.data-integrity`를 함께 읽는다. 기존 필드와 데이터의 호환성을 깨뜨리지 않는다.


