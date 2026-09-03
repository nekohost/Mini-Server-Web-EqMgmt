---
id: tools.file-editing
version: 1
parent: core.kernel
source_rules: [RULE-8.2.1, RULE-8.2.2]
source_validations: []
source_entrypoints: []
source_human: [HUMAN-8-TERMINAL-FALLBACK]
human_rule_sections: ["8-2-1", "8-2-2"]
source_section_digest: 7C9D5EF9FF175ADEDA4B9BE70DF5E4AD4E05B6B061B2C24018D873A3F7E086CC
always_load: false
may_relax_parent: false
---

# 일반 파일 편집

Chat 기록 외의 소스 코드, 문서, 리소스 쓰기는 IDE 또는 에이전트가 제공하는 구조화된 파일 편집 API를 사용한다.

변경은 사용자가 Diff를 확인하고 Undo할 수 있어야 한다. 플랫폼별 실제 도구명은 capability profile을 따른다.

구조화된 편집 도구로 조치할 수 없는 경우에도 터미널 쓰기로 즉시 우회하지 않는다. 다음 조건을 모두 만족할 때에만 터미널 쓰기를 대안으로 제시할 수 있다.

1. 해당 플랫폼에서 변경 Diff와 신뢰 가능한 Undo 또는 동등한 복구 수단이 실제로 검증되었다.
2. 정확한 대상 파일, 사용할 방법, 예상 영향, 복구 절차를 사용자에게 먼저 보고한다.
3. 사용자가 그 터미널 쓰기를 명시적으로 승인한다.

복구 가능성을 검증할 수 없거나 승인을 받지 못하면 일반 파일의 터미널 쓰기는 금지하고 기능 제한을 보고한다.


