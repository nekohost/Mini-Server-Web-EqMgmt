---
id: records.conversation-integrity
version: 1
parent: core.kernel
source_rules: [RULE-6-PREAMBLE, RULE-6.1.1, RULE-6.1.2, RULE-6.1.3, RULE-6.1.4, RULE-6.3.1, RULE-6.3.2, RULE-6.3.3, RULE-6.3.4]
source_validations: [VAL-PHASE.8.2]
source_entrypoints: []
human_rule_sections: ["6", "6-1-1", "6-1-2", "6-1-3", "6-1-4", "6-3-1", "6-3-2", "6-3-3", "6-3-4", "10-9-2"]
source_section_digest: 6E17F7FF95DBC14AE081381017B304D5D49A8EC518AD76ECDAC82DC9E06E6710
always_load: false
may_relax_parent: false
---

# 대화 기록 무결성

사용자 메시지와 AI의 최종 응답 및 중간 안내를 Markdown, 코드 블록, 링크까지 원문 그대로 기록한다. 제안한 코드·설정·명령도 실제 대화와 토씨 하나 다르지 않게 포함한다.

- 사용자는 `## 사용자 YYYY-MM-DD HH:mm:ss.000` 형식을 사용한다.
- AI는 현재 실제 작업자 이름을 사용한다. 다른 모델명을 복사하지 않는다.
- 적용된 변경과 검토·실행 대기 제안을 명확히 구분한다.
- 제안에는 실행 환경, 대상, 선행 조건을 포함한다.
- 코드 블록은 언어를 지정한다.
- 비밀번호, 토큰, 개인키, 개인정보는 원문 대신 `<비밀번호>` 같은 자리표시자로 치환한다.

플랫폼이 정확한 원문이나 시각을 제공하지 않으면 임의로 만들어 기록하지 말고 기능 제한을 보고한다.


