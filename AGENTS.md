# Codex Bootstrap

이 파일은 프로젝트 운영 루트에 적용되는 Codex 진입점이다.

`Rule.md`는 사용자가 전체 정책을 읽는 통합 핸드북이다. 일반 작업에서는 자동으로 읽지 않으며, Rule 자체의 검토·개정·동기화 요청에서만 `Rule.md`와 `traceability/human-rule-map.yaml`을 함께 읽는다.

1. 작업 디렉터리는 프로젝트 루트로 고정한다. 각 작업 시작 시 `.agent-governance/manifest.yaml`을 확인하고 `node .agent-governance/tooling/governance-tool.mjs validate`가 통과하는지 확인한다.
2. 자연어 요청을 하나로 축약하지 않고 관련 intent와 대상 path를 모두 식별한다. 분류할 수 없는 intent·path는 추측하지 않는다.
3. `node .agent-governance/tooling/governance-tool.mjs context`에 모든 `--intent`와 `--path`를 전달하고 출력된 pack의 노드를 순서대로 읽는다. Rule 개정은 변경된 모든 `--section`도 전달한다.
4. 질문에는 답변부터 한다. 제안·계획·검토를 승인 없는 구현으로 확대하지 않는다.
5. 실제 작업은 Task를 만들고 순차적으로 수행한다.
6. 계획 또는 검토에서는 Validation 커널·오케스트레이션·1~8단계를 순서대로 모두 적용한다.
7. 일반 파일 쓰기는 Diff와 Undo가 가능한 구조화된 편집 수단을 사용한다. 그 수단으로 조치할 수 없고 capability에서 터미널 변경의 Diff와 Undo 또는 동등한 복구가 검증된 경우에만 방법·영향·복구 절차를 제안하고 사용자 명시 승인 후 조건부로 사용한다.
8. 필요한 노드가 없거나 규칙이 충돌하면 실행을 중지하고 규칙 ID와 영향을 보고한다.
9. 객관적으로 보고하고 승인을 재촉하지 않는다.
10. 통합 Rule·노드·추적성 원장이 불일치하면 활성화를 중지하고 사용자에게 보고한다.
11. context 도구가 실패하거나 요구한 intent·path·section이 미등록이면 수동으로 노드를 줄여 진행하지 않고 fail-closed 한다.
12. Rule 변경에서는 먼저 `sync-status`의 전체 변경 섹션과 `currentRuleHash`를 확인하고, 그 hash를 `sync-plan`·`validate`의 `--expected-rule-sha`로 사용한다. 대상 노드 digest·섹션 기준선·map·manifest를 함께 갱신하기 전에는 병합하지 않는다.

플랫폼 도구 대응은 `.agent-governance/capabilities/codex.yaml`을 따른다.


