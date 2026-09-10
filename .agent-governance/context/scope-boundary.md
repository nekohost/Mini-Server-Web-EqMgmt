---
id: context.scope-boundary
version: 1
parent: context.project
source_rules: [RULE-1.4, RULE-1.4.1, RULE-1.4.2, RULE-1.4.3, RULE-1.4.4, RULE-1.4.5, RULE-1.4.6, RULE-1.4.7, RULE-6.2.13]
source_validations: []
source_entrypoints: [ENTRY-CODEX.SCOPE, ENTRY-GEMINI.SCOPE, ENTRY-CLAUDE.SCOPE, ENTRY-CHATGPT.SCOPE]
source_human: []
human_rule_sections: ["1-4", "1-4-1", "1-4-2", "1-4-3", "1-4-4", "1-4-5", "1-4-6", "1-4-7", "6-2-13"]
source_section_digest: D58A3F0B902D45E1FAB7072EBF76B0F79C07697C388BDCBB763BD854814E4AB6
always_load: true
may_relax_parent: false
---

# 프로젝트 Scope 경계

1. Mini-Server 작업의 owner는 사용자 의도와 부모 작업 연속성으로 판정하며 경로나 도구만으로 바꾸지 않는다.
2. 외부 read-only 관찰은 reference scope이며 프로젝트 owner를 유지한다.
3. 프로젝트 복구에 직접 필요한 OS·IDE·Git·네트워크·도구 환경 변경은 execution scope일 뿐 owner 전환이 아니다.
4. foreign governed workspace의 read는 reference로 유지하고 write만 nested handoff로 분리한다.
5. nested handoff의 대상 변경은 대상 bootstrap/governance가 통제하며 부모 governance가 대상 제한을 완화하지 않는다.
6. 규칙 충돌 시 실행하지 않고 사용자 결정을 받는다.
7. nested handoff 종료 후 별도 full switch가 없으면 Mini-Server owner로 복귀한다.
8. full switch는 사용자의 새 독립 작업 또는 명시적 owner 전환 의도가 있을 때만 수행한다.
9. Codex·Antigravity의 workspace binding과 ChatGPT + Remote Desktop의 cross-scope capability 차이를 인정하되 도구 자체를 owner 신호로 사용하지 않는다.
10. 대화 기록은 owner를 따르며 per-turn owner 신호가 없는 adapter는 의미 추정으로 원문을 삭제·이동하지 않는다.
