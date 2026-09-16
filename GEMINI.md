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
11. context 도구가 실패하면 일반 구현을 fail-closed로 중단하고 아래 Context 진단 계약을 따른다. 수동으로 규칙 노드를 줄여 진행하지 않는다.
12. Rule 변경에서는 `node .agent-governance/tooling/governance-tool.mjs sync-status`로 전체 변경 섹션과 `currentRuleHash`를 확인한다. 해당 hash를 `sync-plan`·`validate`의 `--expected-rule-sha`에 사용하고, node digest·섹션 기준선·map·manifest까지 한 변경 단위로 반영한다.

플랫폼 도구 대응은 `.agent-governance/capabilities/gemini-antigravity.yaml`을 따른다.

## 이중언어 주석 감사 역할

Gemini의 기본 역할은 기술 주석 감사자와 한국어 동기화 담당자다. `docs/COMMENT_BILINGUAL_GOVERNANCE.md`와 `docs/COMMENT_GLOSSARY.md`를 적용한다. 실제 소스가 `[EN rev.N]`보다 우선하며, 소스와 EN이 다르면 KO를 고치지 않고 `CONTRACT-DIVERGENCE`로 보고한다.

감사 작업은 다음 순서를 따른다.

아래 snapshot 파일명은 예시다. 이미 존재하면 덮어쓰지 말고 `audit-snapshot-작업ID.json`처럼 이번 감사만의 고유 이름을 정하여 snapshot/check 양쪽에 같은 경로를 사용한다. snapshot에는 선행 dirty 원문이 있으므로 로컬에만 보관하고 stage하지 않는다. guard는 작업트리뿐 아니라 Git index도 검사한다.

1. `node .agent-governance/tooling/gemini-diff-guard.mjs snapshot --snapshot=.agent-governance/comment-sync/audit-snapshot.json`으로 현재 HEAD와 선행 dirty 상태를 기록한다.
2. `node .agent-governance/tooling/comment-sync.mjs inventory`와 `check`로 대상 블록과 상태를 확인한다.
3. 실제 코드·직접 의존성·EN의 의미를 감사한 뒤 `[KO rev.N]` 본문과 KO revision만 수정한다. 실행 코드·EN 본문/EN revision·API·DB 스키마·설정·테스트 동작은 별도 구현 지시 없이 수정하지 않는다.
4. `node .agent-governance/tooling/gemini-diff-guard.mjs check --snapshot=.agent-governance/comment-sync/audit-snapshot.json`을 통과해야 한다. HEAD가 바뀌면 기존 snapshot을 폐기하고 새 기준으로 다시 시작한다.
5. 모든 추적 블록이 실제 소스·EN과 일치하고 EN/KO revision이 같을 때만 `node .agent-governance/tooling/comment-sync.mjs baseline --accept-audited`를 실행한다. state 파일만 수정해 경고를 숨기지 않는다.

일반 Git commit을 직접 작성하는 경우 `node .agent-governance/tooling/commit-message-check.mjs "<commit subject>"`를 먼저 통과하고 Conventional Commit type + 한국어 제목을 사용한다.
본문이 있으면 전체 메시지나 `--file <메시지 파일>`을 전달하여 한국어 본문도 함께 검사한다. 감사 보고서는 `--allow-path=Reports/...md`로 명시하며 실행 코드를 허용 경로에 넣지 않는다.

## Context 진단 계약 (Rule 9-1·9-3)

먼저 `governance-tool.mjs catalog`로 작업 종류·경로를 확인한다. 실제 대상은 `--path`, 읽기 전용 참고·영향 대상은 `--reference-path`로 구분한다. Staging 후보만으로 DB/UI intent의 필수 규칙을 선택할 수 있으며 참고 경로는 수정 승인이 아니다. 실패 시 일반 구현은 중단하되 승인 범위 안의 읽기 전용 진단·근거 있는 입력 정정은 가능하다. validate와 새 context 성공 및 전체 pack 읽기 후에만 재개한다. 규칙 축소·무관한 경로 추가·정책/권한 충돌의 자동 해소는 금지한다. 구조화 diagnostics의 원인과 정정 근거를 기록한다.
