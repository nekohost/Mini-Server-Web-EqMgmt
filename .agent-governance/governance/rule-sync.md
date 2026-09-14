---
id: governance.rule-sync
version: 3
parent: governance.human-reference
source_rules: []
source_validations: []
source_entrypoints: []
source_human: [HUMAN-11.3, HUMAN-11.4, HUMAN-11.5, HUMAN-11.6, HUMAN-11.7, HUMAN-11.8]
human_rule_sections: ["11-3", "11-4", "11-5", "11-6", "11-7", "11-8"]
source_section_digest: 4B1A3DD485C5CDB6D4E4920596CC0C4D012CB2744CD0B4D339F2C7B427CFB702
always_load: false
may_relax_parent: false
---

# Rule 변경 동기화

legacy 절차다. 독립 경로는 부모·Staging·8단계·문서 분리를 상속하지 않으며 정책 유지보수의 의미·추적성·해시 검증만 직접 유지한다. Rule은 사용자 의미 기준, 노드는 실행 투영본이다. 아래 순서를 지킨다.

1. 적용 경로의 작업 위치(legacy는 Staging)에서 `node .agent-governance/tooling/governance-tool.mjs sync-status`로 추가·변경·삭제 섹션 전체와 currentRuleHash를 확인한다.
2. `node .agent-governance/tooling/governance-tool.mjs sync-plan --expected-rule-sha <currentRuleHash> --section <번호>`에 변경 섹션 전체를 반복 지정한다.
3. 대상 노드에 사용자 Rule의 의미를 투영하고 human_rule_sections·source_human·source_section_digest를 갱신한다. 도구는 대상/digest만 산출하며 의미를 자동 작성하지 않는다.
4. traceability/human-rule-map.yaml의 node↔section↔HUMAN ID를 갱신한다.
5. traceability/rule-section-baseline.yaml의 섹션/원본 hash와 manifest의 Rule SHA·governance_version을 함께 갱신한다.
6. 새 노드는 manifest/human map에 등록한다. 독립 노드는 execution-profiles 등록부에 연결하며 always_load에 넣지 않는다. 새 작업 유형·경로가 있을 때만 router를 변경한다.
7. `node .agent-governance/tooling/governance-tool.mjs validate --expected-rule-sha <currentRuleHash>`로 YAML·front matter·Rule 포인터·ID/부모·양방향 섹션·기준선/digest·원본/Rule hash를 검증한다.
8. 오류 또는 parser 실행 불가 시 fail-closed로 중지하고 해당 버전을 활성화하지 않는다.
9. 검증 보고서와 사용자 승인 후 Rule·노드·map·manifest·진입점을 같은 버전으로 병합한다.

## 복합 작업과 작은 모델

관련 intent·대상 path를 모두 context에 전달하고 matchedRoutes·nodes·packs를 그대로 읽는다. 미등록 intent/path/section과 예산 초과는 성공이 아니며 노드 제거는 금지한다. 초과 시 공통 안전 노드를 각 pack에 보존해 작업을 분할한다. 예산은 UTF-8 바이트 기반 추정이지 실제 토크나이저/시스템 주입량 보장이 아니다. 플랫폼 한도가 더 작으면 더 작은 Task로 나눈다.
