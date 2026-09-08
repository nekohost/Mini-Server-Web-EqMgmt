---
id: records.conversation-automation
version: 1
parent: records.conversation-integrity
source_rules: [RULE-6.2.4, RULE-6.2.5, RULE-6.2.6, RULE-6.2.7, RULE-6.2.8, RULE-6.2.9, RULE-6.2.10, RULE-6.2.11, RULE-6.2.12]
source_validations: []
source_entrypoints: [ENTRY-CODEX.RECORDER, ENTRY-GEMINI.RECORDER, ENTRY-CLAUDE.RECORDER]
source_human: []
human_rule_sections: ["6-2-4", "6-2-5", "6-2-6", "6-2-7", "6-2-8", "6-2-9", "6-2-10", "6-2-11", "6-2-12"]
source_section_digest: 6D440D824233B6598E41E3ECD9F3038C7E28DDC664800860E1FCC3DF5D4F98D9
always_load: true
may_relax_parent: false
---

# 대화 자동 기록

1. 일반 작업은 manifest 검사 전에 `conversation-recorder ensure --platform all --workspace . --json`을 실행해 활성화된 모든 어댑터를 한 watcher에서 다룬다.
2. 실패하면 일반 작업을 시작하지 않고 `status --json`의 마지막 성공 상태와 오류를 보고한다.
3. Codex·Antigravity만 활성이다. Claude는 검증 전까지 `unsupported`이다.
4. 직접 대화는 `Chat/YYYY/MM/DD.md`, 허용된 하위 task·상태·final은 `Chat/Subagents/`에 기록한다.
5. system·developer·추론·도구·approval-review는 제외한다.
6. 상세 writer·watcher·cursor·receipt·검증 규칙은 `records.conversation-storage`와 Rule 6-2를 따른다.
