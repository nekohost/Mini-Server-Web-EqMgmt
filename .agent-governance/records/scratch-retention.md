---
id: records.scratch-retention
version: 1
parent: records.conversation-storage
source_rules: [RULE-6.1.10.1, RULE-6.1.10.2, RULE-6.1.10.3]
source_validations: [VAL-PHASE.8.1]
source_entrypoints: []
human_rule_sections: ["6-1-10-1", "6-1-10-2", "6-1-10-3", "10-9-1"]
source_section_digest: A2D84E124DB9ECA83DE49A201D82905C756BE8936A0E5492D8A98D4F197F93CC
always_load: false
may_relax_parent: false
---

# scratch 보존 정책

`scratch/` 임시 파일이 10개를 초과하면 다음 대화 턴 시작 시 생성 시각이 오래된 파일부터 FIFO로 정리한다.

한 턴에서 작업 연속성을 위해 10개를 일시 초과한 경우 즉시 삭제하지 않고 다음 턴으로 유예한다. `scratch/` 임시 파일은 `Chat/`과 `Plans/` 영구 문서가 아니며 문서 생명주기 보존 대상에 포함하지 않는다.

삭제 전 대상이 정확히 `scratch/` 내부 임시 파일인지 확인한다.


