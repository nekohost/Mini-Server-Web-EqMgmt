# ChatGPT + Remote Desktop Commander Bootstrap

이 파일은 ChatGPT가 Remote Desktop Commander 등으로 Mini-Server 프로젝트에 참여할 때 사용하는 명시적 진입점이다. ChatGPT 제품이 이 파일을 자동 로드한다고 가정하지 않으며 프로젝트 참여 시 직접 읽어 적용한다.

`Rule.md`는 인간용 통합 참조본이다. 일반 작업에서는 manifest/router가 선택한 node를 우선 사용하고 Rule 개정·감사 시에만 Rule과 human-rule-map을 함께 읽는다.

대화 기록 상태: Codex·Antigravity raw collector는 기존 watcher가 자동 수집한다. ChatGPT native/raw transcript collector는 여전히 없으며 `automatic_project_recording: false`다. 대신 General dispatcher가 session owner와 historical `routing_revision`을 확정한 visible user/commentary/final event는 `chatgpt-remote` capability의 agent-mediated routed ingest로 이 프로젝트에 전달할 수 있다. 이 경로는 target/authority governance fingerprint를 검증한 뒤 기존 project recorder의 writer lock·provenance·atomic write를 재사용한다. routed event 전달 성공을 ChatGPT 플랫폼 자체의 native 자동 수집으로 표현하지 않는다.

Scope ownership `[ENTRY-CHATGPT.SCOPE]`: Remote Desktop Commander 사용이나 프로젝트 밖 경로 접근은 owner 전환 근거가 아니다. 현재 Mini-Server 부모 작업을 위한 reference/execution이면 프로젝트 owner를 유지하고, foreign governed workspace write만 nested handoff하며, 새 독립 작업으로 사용자 의도가 바뀔 때만 full scope switch한다.

1. 프로젝트 루트에서 manifest와 `governance-tool.mjs validate`를 확인한다.
2. 요청의 intent와 path를 모두 분류하고 외부 참조·외부 실행·nested handoff·full switch를 구분한다.
3. `governance-tool.mjs context`에 관련 intent/path/section을 모두 전달하고 선택 node를 읽는다.
4. 질문·검토와 실제 구현을 구분하고 승인 범위를 넘지 않는다.
5. 실제 작업은 Task/Plan/Report 연속성을 확인한다.
6. 일반 파일 쓰기는 구조화된 편집 수단을 우선하며 터미널 fallback은 `tools.file-editing`을 따른다.
7. Rule 변경은 `sync-status` → `sync-plan --expected-rule-sha` → node/map/baseline/manifest 동기화 → validate 순서를 따른다.
8. routed ChatGPT event는 General dispatcher가 확정한 revision과 owner를 그대로 따르며 현재 디렉터리나 도구 위치로 destination을 재판정하지 않는다.
9. scope 또는 governance 충돌을 추측으로 해소하지 않고 사용자 결정을 받는다.

플랫폼 capability는 `.agent-governance/capabilities/chatgpt-remote.yaml`을 따른다.
10. 같은 ChatGPT conversation에서는 최초 명시적 owner 선택 때 만든 conversation-local opaque `session_key`를 계속 재사용한다. 실제 routed delivery receipt가 없는 이벤트를 저장된 것으로 간주하지 않으며, exact timestamp/session binding을 확인할 수 없는 과거 구간은 현재 시각으로 꾸며 backfill하지 않는다.

## Context 진단 계약 (Rule 9-1·9-3)

먼저 `governance-tool.mjs catalog`로 작업 종류·경로를 확인한다. 실제 대상은 `--path`, 읽기 전용 참고·영향 대상은 `--reference-path`로 구분한다. Staging 후보만으로 DB/UI intent의 필수 규칙을 선택할 수 있으며 참고 경로는 수정 승인이 아니다. 실패 시 일반 구현은 중단하되 승인 범위 안의 읽기 전용 진단·근거 있는 입력 정정은 가능하다. validate와 새 context 성공 및 전체 pack 읽기 후에만 재개한다. 규칙 축소·무관한 경로 추가·정책/권한 충돌의 자동 해소는 금지한다. 구조화 diagnostics의 원인과 정정 근거를 기록한다.
