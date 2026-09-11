---
artifact_id: REPORT-20260911-001
work_id: WORK-20260910-CHATGPT-SCOPE-ROUTED-RECORDING
created_at: 2026-09-11T09:36:28.000+09:00
related_artifacts:
  - ../../../../Plans/2026/09/10/005_ChatGPT_Scope_Routed_Conversation_Recording_Plan.md
  - ../../../../Tasks/2026/09/10/009_ChatGPT_Scope_Routed_Conversation_Recording_Task.md
  - ../../../../Reports/2026/09/10/018_ChatGPT_Scope_Routed_Conversation_Recording_Validation_Report.md
---
# [Implementation] ChatGPT Scope Routed Conversation Recording

- 결과: **완료 — 6/6, 남은 단계 0**
- Mini-Server governance: **v1.5.0**
- General routed-delivery governance: **v0.12.1**

## 구현 결과

`RULE-6.2.14`를 추가하여 ChatGPT + Remote Desktop Commander 대화를 native/raw collector가 아닌 General dispatcher authority 기반의 agent-mediated routed ingest로 정의했다.

Mini-Server `chatgpt-remote` capability는 `routed-ingest-supported`를 선언하며 target/authority Rule·manifest·capability·bootstrap fingerprint를 모두 검증한다. 성공한 event만 기존 conversation recorder writer lock, provenance marker, atomic replace, receipt state를 재사용해 기록한다.

General은 historical `routing_revision`으로 owner를 결정하며 foreign `Chat` 경로를 직접 추측하거나 쓰지 않는다.
## E2E에서 발견·수정한 결함

Target 저장 성공 후 General observation cursor가 더 진행된 상태에서 과거 delegated event를 재전달하면 `cursor-conflict`가 발생하는 경계를 발견했다. General v0.12.1에 본문을 저장하지 않는 `delegated_observations` 최소 ledger를 추가하여 동일 provenance 재전달은 idempotent하게 허용하고 불일치는 fail-closed하도록 수정했다.

## 최종 검증

- General 전체 regression: **86/86 PASS**
- Mini-Server 전체 governance/tooling regression: **54/54 PASS**
- General↔Mini full-switch / historical revision / nested handoff E2E: **3/3 PASS**
- Mini governance validate: errors 0 / warnings 0 / `inSync=true`
- General governance validate: errors 0 / warnings 0 / `inSync=true`
- Mini 기존 recorder verify: `ok=true`, missing 0, duplicates 0
- production General/Mini Chat의 E2E sentinel: 0건
- production General dispatcher test residual: state 0 / receipt 0
- temp E2E root residual: 0

## 운영 경계

ChatGPT native/raw transcript collector는 구현되지 않았다. 같은 ChatGPT conversation에서는 conversation-local opaque `session_key`를 한 번 생성·재사용하고, 실제 General routed delivery receipt를 받은 visible event만 저장 성공으로 간주한다. exact timestamp/session binding이 없는 과거 누락 구간은 임의 backfill하지 않는다.

Git commit/push 및 Linux 서비스 적용은 본 작업 승인 범위에 포함하지 않아 수행하지 않았다.
