---
id: records.conversation-automation
version: 3
parent: records.conversation-integrity
source_rules: [RULE-6.2.4, RULE-6.2.5, RULE-6.2.6, RULE-6.2.7, RULE-6.2.8, RULE-6.2.9, RULE-6.2.10, RULE-6.2.11, RULE-6.2.12, RULE-6.2.13, RULE-6.2.14]
source_validations: []
source_entrypoints: [ENTRY-CODEX.RECORDER, ENTRY-GEMINI.RECORDER, ENTRY-CLAUDE.RECORDER]
source_human: []
human_rule_sections: ["6-2-4", "6-2-5", "6-2-6", "6-2-7", "6-2-8", "6-2-9", "6-2-10", "6-2-11", "6-2-12", "6-2-13", "6-2-14"]
source_section_digest: 55B0920E1A6759276A727DFD043904F87B7E75C43CAF9C702ECF1F8EFCC8CBA5
always_load: true
may_relax_parent: false
---

# 대화 자동 기록

1. 일반 작업은 manifest 검사 전에 `conversation-recorder ensure --platform all --workspace . --json`을 실행해 활성화된 모든 어댑터를 한 watcher에서 다룬다.
2. 실패하면 원래 요청의 일반 작업을 시작하지 않고 마지막 성공 상태와 오류를 보고한다. recorder 자체 복구는 승인된 recovery exception 범위에서만 수행한다.
3. Codex·Antigravity raw collector만 자동 수집한다. ChatGPT native/raw 수집은 비활성이며 General의 revision-bound routed ingest만 지원한다.
4. 직접 대화는 `Chat/YYYY/MM/DD.md`, 허용된 하위 task·상태·final은 `Chat/Subagents/`에 기록한다.
5. system·developer·추론·도구·approval-review는 제외한다.
6. 상세 writer·watcher·cursor·receipt·검증 규칙은 `records.conversation-storage`와 Rule 6-2를 따른다.
7. 기록 owner는 `context.scope-boundary`를 따른다. 현재 adapter에 per-turn owner 신호가 없으면 의미 추정으로 원문을 삭제·이동하지 않고 한계를 보고하며 full scope switch는 명시적 별도 owner context handoff를 우선한다.
