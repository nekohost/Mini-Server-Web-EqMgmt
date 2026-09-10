# Antigravity Bootstrap

이 파일은 프로젝트 운영 루트에 적용되는 Antigravity/Gemini 진입점이다.

`Rule.md`는 사용자용 통합 핸드북이다. 일반 작업에서는 자동으로 읽지 않으며, Rule 자체의 검토·개정·동기화 요청에서만 `Rule.md`와 `traceability/human-rule-map.yaml`을 함께 읽는다.

대화 자동 기록 preflight `[ENTRY-GEMINI.RECORDER]`: 다른 검사보다 먼저 프로젝트 루트에서 `node .agent-governance/tooling/conversation-recorder.mjs ensure --platform all --workspace . --json`을 실행한다. 재조정이 실패하면 원래 요청의 일반 작업을 시작하지 않고 `status --json`의 마지막 성공 상태와 오류를 보고한다. 다만 실패 원인이 recorder/Chat 저장·잠금·원자적 교체 또는 관련 Rule·노드 자체에 있고 사용자가 복구를 명시 승인했거나 현재 capability에 검증된 recovery 경로가 있으면 진단·증거 보존·백업·복구·관련 Rule/노드 검토와 그 기록에 필요한 최소 작업만 허용하며, `ensure`와 `governance-tool validate`가 다시 성공하기 전에는 원래 일반 작업으로 복귀하지 않는다.

Scope ownership `[ENTRY-GEMINI.SCOPE]`: Mini-Server workspace에서 시작된 Antigravity 작업은 프로젝트를 기본 owner로 본다. 프로젝트 목적의 외부 reference나 비독립 PC/IDE/Git execution은 owner를 바꾸지 않는다. foreign governed workspace write는 nested handoff하며, 사용자가 새 독립 작업 또는 owner 전환을 명시한 경우에만 full scope switch한다.

1. 작업 디렉터리는 프로젝트 루트로 고정한다. 각 작업 전 manifest를 확인하고 정규 파서 기반 `node .agent-governance/tooling/governance-tool.mjs validate`가 통과하는지 확인한다.
2. 자연어 요청을 하나로 축약하지 않고 관련 intent와 대상 path를 모두 식별하여 context 명령에 전달한다. Rule 개정은 변경된 모든 section도 전달한다.
3. context 명령이 출력한 pack의 노드를 부모에서 자식 순서로 읽고 행위 직전 활성 규칙과의 적합성을 판단한다.
4. 사용자 요청이 규칙과 충돌하면 실행하지 않고 충돌 보고 후 재지시를 기다린다.
5. 질문에 먼저 답하고, 검토·보고·승인 후 실제 작업을 수행한다.
6. 실제 작업은 Task를 만들어 순차적으로 수행한다.
7. 검증·검토에서는 Validation 1~8단계를 순서대로 모두 적용한다.
8. 객관적으로 판단하고 승인을 재촉하지 않는다.
9. 통합 Rule·노드·추적성 원장이 불일치하면 활성화를 중지하고 사용자에게 보고한다.
10. Chat 저장과 일반 파일 편집의 도구 우선순위 및 터미널 예외는 `.agent-governance/capabilities/gemini-antigravity.yaml`과 해당 도구 노드를 따른다.
11. context 도구가 실패하거나 intent·path·section을 분류할 수 없으면 수동 추측으로 진행하지 않고 fail-closed 한다.
12. Rule 변경에서는 `node .agent-governance/tooling/governance-tool.mjs sync-status`로 전체 변경 섹션과 `currentRuleHash`를 확인한다. 해당 hash를 `sync-plan`·`validate`의 `--expected-rule-sha`에 사용하고, node digest·섹션 기준선·map·manifest까지 한 변경 단위로 반영한다.

플랫폼 도구 대응은 `.agent-governance/capabilities/gemini-antigravity.yaml`을 따른다.


