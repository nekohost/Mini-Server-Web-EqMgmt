---
id: governance.human-reference
version: 2
parent: core.precedence
source_rules: []
source_validations: []
source_entrypoints: []
source_human: [HUMAN-11.1, HUMAN-11.2, HUMAN-11.3, HUMAN-11.4, HUMAN-11.5, HUMAN-11.6, HUMAN-11.7, HUMAN-11.8]
human_rule_sections: ["11-1", "11-2", "11-3", "11-4", "11-5", "11-6", "11-7", "11-8"]
source_section_digest: 7C36C12B9FD533798DA8293E92A16987D022C5C1018CC478FE9C02203DFD9976
always_load: false
may_relax_parent: false
---

# 사용자용 통합 Rule과 노드 동기화

`Rule.md`는 사용자가 전체 정책을 읽고 변경 의도를 판단하는 사용자용 의미 기준이다. `.agent-governance/` 노드는 AI가 작업별로 읽는 실행 투영본이다.

1. AI는 일반 작업에서 통합 `Rule.md`를 자동 로딩하지 않는다.
2. Rule 자체의 검토·개정·동기화 요청에서만 `Rule.md`와 `human-rule-map.yaml`을 읽는다.
3. 정책 변경은 통합 Rule, 대상 노드, node front matter, traceability map, manifest의 Rule 해시·거버넌스 버전을 같은 변경 단위에서 갱신한다.
4. Rule과 노드가 불일치하면 어느 한쪽을 묵시적으로 우선하지 않고 해당 거버넌스 버전 활성화를 차단한다.
5. 통합 Rule의 각 말단 조항은 실제 규칙 ID, 노드 ID, 경로 포인터를 가진다.
6. 루트 Rule 반영 전 Staging 작성, 양방향 동등성 검증, 사용자 승인을 거친다. 사용자가 Staging 통합 Rule에 직접 추가했거나 명시적으로 승인한 정책은 운영 병합에서 누락하거나 이전 초안으로 덮어쓰지 않고 대상 노드·추적성·manifest에도 같은 의미와 변경 상태를 유지한다.
7. 실제 동기화 순서와 정규 파서 검증은 `governance.rule-sync`를 따른다.
8. Rule 변경은 섹션 기준선과 노드별 `source_section_digest`로 탐지·검증하며, 이 검증을 통과하기 전에는 활성화하거나 병합하지 않는다.

