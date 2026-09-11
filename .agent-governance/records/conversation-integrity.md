---
id: records.conversation-integrity
version: 2
parent: core.kernel
source_rules: [RULE-6-PREAMBLE, RULE-6.1.1, RULE-6.1.2, RULE-6.1.3, RULE-6.1.4, RULE-6.3.1, RULE-6.3.2, RULE-6.3.3, RULE-6.3.4]
source_validations: [VAL-PHASE.8.2]
source_entrypoints: []
human_rule_sections: ["6", "6-1-1", "6-1-2", "6-1-3", "6-1-4", "6-3-1", "6-3-2", "6-3-3", "6-3-4", "10-9-2"]
source_section_digest: B7CB899151B491AF73823BF90EEE551938B88C5857EC3B56A95A1274B2E94A77
always_load: false
may_relax_parent: false
---

# 대화 기록 무결성

사용자·AI 최종/중간 발언과 제안 코드·설정·명령은 Markdown·링크까지 원문 그대로 기록한다.

- 신규 직접 사용자 헤더: `## 사용자 → Codex YYYY-MM-DD HH:mm:ss.000`(수신 AI 실명). 미확인은 `사용자`, 추측 금지.
- 과거 원문·헤더·provenance와 부모→하위 표기는 보존한다. 미표기 헤더도 원본·시각·본문으로 중복 판정한다.
- AI는 실제 작업자명만 쓴다.
- 적용과 실행 대기를 구분하고 제안에 환경·대상·선행 조건을 명시한다.
- 코드 블록은 언어를 지정한다.
- 비밀번호·토큰·개인키·개인정보는 `<비밀번호>` 등으로 치환한다.
- 정확한 원문/시각이 없으면 조작하지 말고 제한을 보고한다.
