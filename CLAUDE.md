# Claude Bootstrap

이 파일은 프로젝트 운영 루트에 적용되는 Claude 진입점이다.

`Rule.md`는 사용자가 전체 정책을 읽는 통합 핸드북이다. 일반 작업에서는 자동으로 읽지 않으며, Rule 자체의 검토·개정·동기화 요청에서만 `Rule.md`와 `traceability/human-rule-map.yaml`을 함께 읽는다.

1. 작업 디렉터리는 프로젝트 루트로 고정한다. `.agent-governance/manifest.yaml`을 확인하고 정규 파서 기반 `node .agent-governance/tooling/governance-tool.mjs validate`가 통과하는지 확인한다.
2. 관련 intent와 대상 path를 모두 context 명령에 전달하고 출력된 pack의 노드를 순서대로 읽는다. Rule 개정은 변경된 모든 section도 전달한다.
3. 질문·제안·계획·구현·삭제 모드를 구분하고 승인 범위를 넘지 않는다. intent·path·section을 분류할 수 없거나 context 명령이 실패하면 추측하지 않고 중지한다.
4. 실제 작업은 Task를 만들어 순차 수행한다.
5. 계획 또는 검토는 Validation 1~8단계를 고정 순서로 수행한다.
6. 규칙 누락이나 충돌 시 추측하지 않고 ID와 영향을 보고한다.
7. 일반 파일은 Diff와 Undo가 가능한 구조화된 편집 수단으로 변경한다. 그 수단으로 조치할 수 없고 capability에서 터미널 변경의 Diff와 Undo 또는 동등한 복구가 검증된 경우에만 방법·영향·복구 절차를 제안하고 사용자 명시 승인 후 조건부로 사용한다.
8. 객관적으로 보고하고 승인을 재촉하지 않는다.
9. 통합 Rule·노드·추적성 원장이 불일치하면 활성화를 중지하고 사용자에게 보고한다.
10. Rule 변경에서는 `sync-status`로 모든 추가·변경·삭제 섹션과 `currentRuleHash`를 확인한다. hash를 `sync-plan`·`validate`의 `--expected-rule-sha`로 고정하고, node digest·섹션 기준선·map·manifest까지 동시에 반영한다.

플랫폼 도구 대응은 `.agent-governance/capabilities/claude.yaml`을 따른다.


