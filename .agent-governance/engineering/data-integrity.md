---
id: engineering.data-integrity
version: 1
parent: core.kernel
source_rules: [RULE-4.4.1, RULE-4.4.2]
source_validations: [VAL-PHASE.1.2, VAL-PHASE.3.3, VAL-PHASE.6.1, VAL-PHASE.6.2]
source_entrypoints: []
human_rule_sections: ["4-4-1", "4-4-2", "10-2-2", "10-4-3", "10-7-1", "10-7-2"]
source_section_digest: 4E46AFBB43581112F773D0BAC56504C296906B96F812F237B1680C0E4FE4D744
always_load: false
may_relax_parent: false
---

# 데이터 보존과 마이그레이션

DB 스키마 조작은 기존 데이터 보존을 최우선으로 한다.

- 스키마 변경을 이유로 기존 테이블을 함부로 `DROP`하거나 전체 초기화하지 않는다.
- 가능한 경우 `ALTER TABLE`과 전진 호환 마이그레이션을 사용한다.
- 데이터 보정이나 이전이 필요하면 실행 전에 정확한 쿼리, 순서, 백업, 검증, 롤백 절차를 사용자에게 안내한다.
- Up 변경뿐 아니라 Down 또는 안전한 복구 가능성을 평가한다.
- 파괴적 데이터 작업은 정확한 대상과 복구 가능성을 확인하고 필요한 승인을 받는다.

완료 보고에는 기존 데이터 보존 방식과 실패 시 복구 경로를 포함한다.


