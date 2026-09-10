# ChatGPT + Remote Desktop Commander Bootstrap

이 파일은 ChatGPT가 Remote Desktop Commander 등으로 Mini-Server 프로젝트에 참여할 때 사용하는 명시적 진입점이다. ChatGPT 제품이 이 파일을 자동 로드한다고 가정하지 않으며 프로젝트 참여 시 직접 읽어 적용한다.

`Rule.md`는 인간용 통합 참조본이다. 일반 작업에서는 manifest/router가 선택한 node를 우선 사용하고 Rule 개정·감사 시에만 Rule과 human-rule-map을 함께 읽는다.

대화 기록 상태: 현재 project recorder는 Codex·Antigravity 원본만 자동 수집한다. ChatGPT 직접 대화는 adapter가 없으므로 자동 기록 성공으로 주장하지 않는다. 프로젝트 작업 전 `conversation-recorder ensure --platform all --workspace . --json`은 기존 활성 adapter의 무결성 확인 목적으로 실행할 수 있다.

Scope ownership `[ENTRY-CHATGPT.SCOPE]`: Remote Desktop Commander 사용이나 프로젝트 밖 경로 접근은 owner 전환 근거가 아니다. 현재 Mini-Server 부모 작업을 위한 reference/execution이면 프로젝트 owner를 유지하고, foreign governed workspace write만 nested handoff하며, 새 독립 작업으로 사용자 의도가 바뀔 때만 full scope switch한다.

1. 프로젝트 루트에서 manifest와 `governance-tool.mjs validate`를 확인한다.
2. 요청의 intent와 path를 모두 분류하고 외부 참조·외부 실행·nested handoff·full switch를 구분한다.
3. `governance-tool.mjs context`에 관련 intent/path/section을 모두 전달하고 선택 node를 읽는다.
4. 질문·검토와 실제 구현을 구분하고 승인 범위를 넘지 않는다.
5. 실제 작업은 Task/Plan/Report 연속성을 확인한다.
6. 일반 파일 쓰기는 구조화된 편집 수단을 우선하며 터미널 fallback은 `tools.file-editing`을 따른다.
7. Rule 변경은 `sync-status` → `sync-plan --expected-rule-sha` → node/map/baseline/manifest 동기화 → validate 순서를 따른다.
8. scope 또는 governance 충돌을 추측으로 해소하지 않고 사용자 결정을 받는다.

플랫폼 capability는 `.agent-governance/capabilities/chatgpt-remote.yaml`을 따른다.
