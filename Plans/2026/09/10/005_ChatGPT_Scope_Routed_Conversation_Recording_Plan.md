---
artifact_id: PLAN-20260910-005
work_id: WORK-20260910-CHATGPT-SCOPE-ROUTED-RECORDING
created_at: 2026-09-10T21:26:00.000+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/10/009_ChatGPT_Scope_Routed_Conversation_Recording_Task.md
  - ../../../../Reports/2026/09/10/018_ChatGPT_Scope_Routed_Conversation_Recording_Validation_Report.md
---
# [계획서] ChatGPT Scope Routed Conversation Recording

- 작성일: 2026-09-10
- `work_id`: `WORK-20260910-CHATGPT-SCOPE-ROUTED-RECORDING`
- 부모 owner: `D:\Project\Mini-Server-Web-EqMgmt`
- 상태: **완료 — 6/6 완료, 남은 단계 0 / Mini-Server v1.5.0 / General v0.12.1**

## 1. 목적

ChatGPT + Remote Desktop Commander 직접 대화를 특정 프로젝트에 고정 저장하지 않고, General dispatcher가 해당 conversation/session의 확정 owner와 `routing_revision`에 따라 General 또는 각 governed workspace의 Chat으로 라우팅하여 기록한다.

“어디서 작업하는가”는 현재 디렉터리나 사용 도구가 아니라 dispatcher의 active owner scope를 의미한다. 외부 reference/execution은 owner를 바꾸지 않고, nested handoff와 full switch만 명시적 transition으로 기록 목적지를 바꾼다.

## 2. 아키텍처

1. General은 session-local owner state와 transition receipt를 유일한 routing authority로 사용한다.
2. ChatGPT visible user/commentary/final event는 exact timestamp와 명시적 `routing_revision`을 가진 normalized event로 전달한다.
3. General owner event는 기존 General recorder에 기록한다.
4. Governed owner event는 General이 target governance/capability를 검증한 뒤 target의 machine-readable routed-ingest entrypoint로 전달한다.
5. General은 foreign `Chat` 경로를 추측하거나 직접 쓰지 않는다.
6. Mini-Server recorder는 자신이 target owner임이 검증된 envelope만 받아 기존 writer lock/provenance/atomic writer로 기록한다.

## 3. General nested handoff 범위

Mini-Server 부모 작업의 일부로 `D:\General`에 nested handoff하여 다음만 변경한다.

- ChatGPT agent-mediated bridge / governed delivery tooling
- routed-delivery contract와 capability/bootstrap/route 등록
- target capability가 선언한 entrypoint 이외의 foreign 실행 금지
- General owner 기록과 governed owner delivery의 교차 E2E

General 자체의 자연어 owner 추론은 추가하지 않는다. caller가 사용자 의도를 명시적 dispatcher event로 제출하며 path/tool만으로 owner를 바꾸지 않는다.

## 4. Mini-Server 구현 범위

- `chatgpt-remote` capability에 `routed-ingest-supported`를 선언한다.
- 기존 `conversation-recorder.mjs`에 `ingest-routed` entrypoint를 추가한다.
- envelope의 target owner, routing revision, General authority, target governance fingerprint를 검증한다.
- 검증 후 기존 `createEvent` / `projectEvents` / writer lock / receipt 상태를 재사용한다.
- raw ChatGPT 원본 collector가 생긴 것으로 주장하지 않는다.

## 5. 실패·보안 원칙

- session state, audit, historical revision, target governance, capability, routed entrypoint 중 하나라도 불명확하면 `hold/reject`한다.
- 다른 프로젝트로 fallback하지 않는다.
- system/developer/reasoning/tool/approval 내부 이벤트는 기록하지 않는다.
- raw session/thread/source identifier는 target recorder state에 새로 영구 저장하지 않는다.
- 동일 provenance event는 exactly-once이며 content mismatch는 conflict로 차단한다.
- 현재 대화의 과거 누락 구간은 exact source timestamp와 event identity가 검증되지 않으면 임의 backfill하지 않는다.

## 6. 6단계 구현 순서

1. 양 scope governance/preflight 및 rollback 확보
2. 부모/자식 Plan·Task·Validation 제출
3. General bridge·delivery 구현 및 governance 등록
4. Mini-Server routed-ingest 구현 및 governance 등록
5. temp session 기반 General→Mini-Server→General/nested/full-switch 교차 E2E
6. 전체 regression, runtime 비오염, 문서 종결 및 cleanup

## 7. 수용 기준

- General owner event는 General Chat 후보로만, Mini-Server owner event는 Mini-Server routed-ingest로만 간다.
- reference/external-execution은 기록 owner를 유지한다.
- historical `routing_revision`이 현재 owner와 달라도 event 발생 당시 owner를 사용한다.
- Mini-Server는 General이 검증한 자기 owner event만 기록하며 foreign owner event를 거부한다.
- target capability가 routed ingest를 선언하지 않으면 General delivery는 fail-closed한다.
- 같은 event 재전달은 중복 기록하지 않는다.
- 실제 사용자 General/Mini-Server Chat 및 production dispatcher runtime은 E2E fixture로 오염시키지 않는다.
- Mini-Server와 General governance validate/sync-status가 모두 errors/warnings 0, inSync=true여야 한다.

## 8. 승인 경계

사용자는 본 설계를 확인한 뒤 구현을 명시적으로 지시했다. 이에 따라 Mini-Server 부모 작업과 필요한 General nested handoff 구현·검증·문서화를 진행한다. Git commit/push 또는 Linux 서비스 적용은 별도 요청이 없는 한 자동 확대하지 않는다.

## 9. 완료 체크포인트

2026-09-11 cross-scope E2E 3/3, General 86/86, Mini-Server 54/54 regression을 통과했다. 최종 구현 보고서는 `Reports/2026/09/11/001_ChatGPT_Scope_Routed_Conversation_Recording_Implementation_Report.md`에 기록한다.
