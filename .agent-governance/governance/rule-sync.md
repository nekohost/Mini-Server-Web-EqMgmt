---
id: governance.rule-sync
version: 2
parent: governance.human-reference
source_rules: []
source_validations: []
source_entrypoints: []
source_human: [HUMAN-11.3, HUMAN-11.4, HUMAN-11.5, HUMAN-11.6, HUMAN-11.7, HUMAN-11.8]
human_rule_sections: ["11-3", "11-4", "11-5", "11-6", "11-7", "11-8"]
source_section_digest: 7E308E04024BB47517ED1D5857E6A7861D00E00CBF136EE3D980F69B6F4C8772
always_load: false
may_relax_parent: false
---

# Rule 변경 동기화

`Rule.md`는 사용자가 읽고 직접 수정하는 의미 기준이고, 실행 노드는 AI가 작업 중 읽는 투영본이다. AI는 Rule 변경 요청에서 아래 순서를 생략하거나 재배열하지 않는다.

1. 프로젝트 루트를 작업 디렉터리로 삼아 `node .agent-governance/tooling/governance-tool.mjs sync-status`를 실행한다. 추가·변경·삭제 섹션을 모두 확인하고 반환된 `currentRuleHash`를 기록한다.
2. `node .agent-governance/tooling/governance-tool.mjs sync-plan --expected-rule-sha <currentRuleHash> --section <번호>`를 실행한다. 기준선 불일치가 있으면 status의 전체 변경 섹션을 `--section`으로 빠짐없이 반복한다.
3. 사용자 수정 Rule의 의미를 대상 노드 본문에 투영하고, 노드의 `human_rule_sections`, `source_human`, `source_section_digest`를 갱신한다. 도구는 대상과 기대 digest를 제시할 뿐 의미 문장을 자동 작성하지 않는다.
4. `traceability/human-rule-map.yaml`의 node→section 역포인터와 HUMAN ID를 갱신한다.
5. `traceability/rule-section-baseline.yaml`의 섹션 hash·원본 hash와 manifest의 Rule SHA-256·`governance_version`을 같은 변경 단위에서 갱신한다.
6. 새 노드가 생긴 경우 manifest `nodes` 등록과 human map mapping을 추가한다. 새 작업 유형이나 경로가 생긴 경우에만 router route를 추가·수정한다.
7. `node .agent-governance/tooling/governance-tool.mjs validate --expected-rule-sha <currentRuleHash>`로 모든 YAML, Markdown front matter, Rule 포인터, 노드 ID·부모, 양방향 섹션, 섹션 기준선, node digest, source 문서 해시, Rule 해시를 검사한다.
8. 검증 오류가 하나라도 있거나 parser를 실행할 수 없으면 fail-closed로 중지하고 해당 거버넌스 버전을 활성화하지 않는다.
9. 운영 병합은 검증 보고서와 사용자 승인을 받은 뒤 Rule·노드·map·manifest·진입점을 같은 버전 묶음으로 수행한다.

## 복합 작업과 작은 모델

- 자연어 요청을 하나의 intent로 축약하지 않고 모든 관련 intent와 대상 path를 context 명령에 전달한다.
- `context` 결과의 `matchedRoutes`, `nodes`, `packs`를 그대로 사용하며 모델이 임의로 노드를 제거하지 않는다.
- 미등록 intent·path, 미등록 Rule section, context budget 초과는 성공으로 간주하지 않는다.
- budget 초과 시 공통 안전 노드를 각 pack에 보존한 채 작업을 분할한다.
- context 예산은 UTF-8 바이트 기반의 모델 비종속 계획치다. 실제 모델 토크나이저나 시스템 주입량을 보장하지 않으므로 플랫폼 한도가 더 작으면 더 작은 Task로 재분할한다.
