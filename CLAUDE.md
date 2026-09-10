# Claude Bootstrap

이 파일은 프로젝트 운영 루트에 적용되는 Claude 진입점이다.

`Rule.md`는 사용자가 전체 정책을 읽는 통합 핸드북이다. 일반 작업에서는 자동으로 읽지 않으며, Rule 자체의 검토·개정·동기화 요청에서만 `Rule.md`와 `traceability/human-rule-map.yaml`을 함께 읽는다.

대화 자동 기록 capability `[ENTRY-CLAUDE.RECORDER]`: Claude 원본 어댑터는 이번 버전에서 `unsupported`이다. 지원 검증 전에는 자동 기록 성공으로 보고하지 않으며 기존 승인된 수동 기록 절차를 사용한다. 후속 capability가 활성화되면 다른 검사보다 먼저 `conversation-recorder ensure --platform claude`를 실행한다. 활성화 후 preflight가 실패하면 원래 요청의 일반 작업은 차단하고, 실패 원인이 recorder/Chat 저장·잠금·원자적 교체 또는 관련 Rule·노드 자체에 있으며 사용자가 복구를 명시 승인했거나 현재 capability에 검증된 recovery 경로가 있는 경우에만 진단·증거 보존·백업·복구·관련 Rule/노드 검토와 그 기록에 필요한 최소 작업을 허용한다. `ensure`와 `governance-tool validate`가 다시 성공하기 전에는 원래 일반 작업으로 복귀하지 않는다.

Scope ownership `[ENTRY-CLAUDE.SCOPE]`: Mini-Server 작업으로 시작된 Claude 작업은 프로젝트를 기본 owner로 본다. 프로젝트 목적의 외부 reference나 비독립 PC/IDE/Git execution은 owner를 바꾸지 않는다. foreign governed workspace write는 nested handoff하며, 사용자가 새 독립 작업 또는 owner 전환을 명시한 경우에만 full scope switch한다.

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
