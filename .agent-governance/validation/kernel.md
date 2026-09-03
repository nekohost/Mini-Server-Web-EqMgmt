---
id: validation.kernel
version: 1
parent: core.kernel
source_rules: []
source_validations: [VAL-PREAMBLE, VAL-CORE.2, VAL-CORE.3, VAL-CORE.4]
source_entrypoints: [ENTRY-GEMINI.6, ENTRY-GEMINI.6.1, ENTRY-GEMINI.8]
human_rule_sections: ["9-6", "9-6-1", "9-8", "10", "10-1-2", "10-1-3", "10-1-4"]
source_section_digest: BD713C34CDA75DACE2A1AF46446AFA6D32B77BDE041E817033928F305CA47D7D
always_load: false
may_relax_parent: false
---

# 검증 커널

신규 제안이나 구현 계획 수립 직후, 코드 작성 또는 운영 병합 전에 자체 검증을 수행한다.

1. 판단은 객관적이고 건조하게 작성한다.
2. 실제 긍정적 측면과 부정적·위험 측면을 독립적으로 찾고 비교한다.
3. 어느 한쪽이 실제로 없으면 억지로 만들지 말고 없다는 근거를 남긴다.
4. 각 단계의 관찰점은 최소 기준이다. 작업 맥락에 맞는 숨은 엣지 케이스와 위협을 자율적으로 확장 발굴한다.
5. 검증 실패를 표현만 바꾸어 통과시키거나 거버넌스를 우회하지 않는다.


