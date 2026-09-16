---
id: engineering.code-comments
version: 2
parent: context.project
source_rules: [RULE-1.3, RULE-4.3.1, RULE-4.3.2, RULE-4.3.3, RULE-4.3.4, RULE-4.3.5, RULE-4.3.6]
source_validations: []
source_entrypoints: []
human_rule_sections: ["1-3", "4-3-1", "4-3-2", "4-3-3", "4-3-4", "4-3-5", "4-3-6"]
source_section_digest: E088F70D0ED966A6CE3006199C748FEBD4F5296462FBBC79F02FB012DA936998
always_load: false
may_relax_parent: false
---

# 코드 주석

모든 함수와 API 라우트 상단에는 역할·의존성·영향을 설명하는 메타 주석을 유지한다. 핵심 함수·API·비자명한 내부 계약은 안정적인 `[MINI-COMMENT: <ID>]`를 사용하고 다음 두 섹션을 함께 둔다.

- `[EN rev.N]`: `[Role]`, `[Dependencies]`, `[Impact]`를 포함하는 기술 기준 주석이다.
- `[KO rev.N]`: `[역할]`, `[의존성 관계]`, `[변경 시 영향도]`를 포함하며 실제 소스와 EN을 감사한 한국어 동기화본이다.

실제 소스가 가장 우선하고 EN이 그다음, KO가 마지막이다. ChatGPT/Codex가 추적 코드의 계약 또는 EN 본문을 바꾸면 EN revision을 증가시킨다. Gemini는 소스와 EN이 일치하는지 확인한 뒤 KO 본문과 KO revision만 동기화하며, 불일치하면 `CONTRACT-DIVERGENCE`로 보고하고 번역을 보류한다.

comment-sync baseline은 Comment ID별 EN/KO revision과 EN/KO/source hash를 기록한다. EN>KO, KO>EN, 본문·source hash 변경과 revision 불일치, 중복·삭제 ID를 서로 다른 상태로 보고하며 baseline만 고쳐 경고를 숨기지 않는다. 초기 전환은 핵심 파일부터 점진적으로 수행한다.

기존 상세 행 주석 요구는 유지하지만 자명한 행 설명까지 이중언어 추적 대상으로 강제하지 않는다. 기존 주석을 제거하거나 의미를 축소하지 않으며, 이 정책의 비용이나 코드 품질을 바꾸려면 별도 정책 개정이 필요하다.


