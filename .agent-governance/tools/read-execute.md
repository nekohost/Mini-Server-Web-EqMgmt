---
id: tools.read-execute
version: 1
parent: core.kernel
source_rules: [RULE-8-PREAMBLE, RULE-8.1.1, RULE-8.1.2]
source_validations: []
source_entrypoints: []
source_human: [HUMAN-8-TERMINAL-FALLBACK]
human_rule_sections: ["8", "8-1-1", "8-1-2"]
source_section_digest: DB0533FC41FFEA28523CFAA4CDC58A837E718F657A4C694CA5427C80D56524E9
always_load: false
may_relax_parent: false
---

# 터미널 읽기·실행

터미널은 파일 조회, 디렉터리 탐색, 서버 구동, 상태 모니터링 등 읽기 또는 승인된 실행에 사용한다.

일반 소스·리소스 파일을 `Add-Content`, `echo`, 리디렉션, `cat >` 같은 터미널 쓰기로 생성·수정·덮어쓰는 행위는 기본적으로 금지한다. Chat 기록에는 `tools.conversation-exception`이 우선한다.

구조화된 편집 도구로 조치할 수 없고 플랫폼 capability에서 터미널 변경의 Diff와 신뢰 가능한 Undo 또는 동등한 복구가 실제로 검증된 경우에는 `tools.file-editing`의 사전 보고·명시 승인 절차에 따라 조건부 대안으로만 제시할 수 있다.


