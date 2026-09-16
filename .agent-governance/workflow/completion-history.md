---
id: workflow.completion-history
version: 2
parent: workflow.plans
source_rules: [RULE-7.4.1, RULE-7.4.2, RULE-7.4.3, RULE-7.4.4]
source_validations: []
source_entrypoints: []
human_rule_sections: ["7-4-1", "7-4-2", "7-4-3", "7-4-4"]
source_section_digest: 0450AEAE4566EC4F66978D22489796B177B2321D0A1A44DA0AC268BA2C729E47
always_load: false
may_relax_parent: false
---

# 완료 이력

개발 완료 후에도 `PROPOSALS.md`와 `ROADMAP.md`의 원본 항목은 삭제하지 않는다. 상태를 `[개발 완료 (FEATURES.md 이관)]` 등으로 갱신하여 이력을 보존한다.

완료된 항목은 `UNIMPLEMENTED_PROPOSALS.md`와 `UNIMPLEMENTED_ROADMAP.md`에서 제거하여 현재 대기열을 최신화한다. 최종 상세 기능 명세는 `FEATURES.md`에 추가한다.

AI 작업자가 만드는 일반 Git commit은 Conventional Commit의 영문 type을 유지하고 제목과 본문 설명은 한국어를 기본으로 한다. API명·파일명·심벌·표준 고유명사는 원문을 유지할 수 있고 자동 merge/revert 메시지는 예외다. 프로젝트에 commit 메시지 검사기가 있으면 commit 전에 통과시킨다.


