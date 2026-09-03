# Antigravity Bootstrap

이 파일은 프로젝트 운영 루트에 적용되는 Antigravity/Gemini 진입점이다.

`Rule.md`는 사용자용 통합 핸드북이다. 일반 작업에서는 자동으로 읽지 않으며, Rule 자체의 검토·개정·동기화 요청에서만 `Rule.md`와 `traceability/human-rule-map.yaml`을 함께 읽는다.

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


