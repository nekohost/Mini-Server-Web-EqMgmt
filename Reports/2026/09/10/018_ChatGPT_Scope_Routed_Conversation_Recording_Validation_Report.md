---
artifact_id: REPORT-20260910-018
work_id: WORK-20260910-CHATGPT-SCOPE-ROUTED-RECORDING
created_at: 2026-09-10T21:28:00.000+09:00
related_artifacts:
  - ../../../../Plans/2026/09/10/005_ChatGPT_Scope_Routed_Conversation_Recording_Plan.md
  - ../../../../Tasks/2026/09/10/009_ChatGPT_Scope_Routed_Conversation_Recording_Task.md
---
# [Validation 1~8] ChatGPT Scope Routed Conversation Recording

- 판정: **구현 진행 가능**
- 전제: Mini-Server 부모 owner, General 변경은 nested handoff

## Validation 1 — Governance

Mini-Server v1.4.0과 General v0.11.0은 모두 errors 0 / warnings 0 / inSync=true에서 시작한다. 양쪽 모두 path/tool이 owner 신호가 아니며 per-turn owner 신호 없는 기록 추정을 금지하므로 제안 구조와 정합한다.

## Validation 2 — 사용자 의도

사용자는 프로젝트를 한 번 지정하면 작업 연속성에 따라 기록 목적지가 따라가고, 프로젝트 전환 시에는 새 owner로 라우팅되는 구조를 요구했다. General dispatcher의 session-local owner/revision을 authority로 사용하는 방식이 직접 부합한다.

## Validation 3 — 정적 논리

General route는 historical receipt의 `next_owner`를 사용한다. 따라서 현재 owner만 보고 과거 메시지를 잘못 소급 저장하는 문제를 피할 수 있다. target project는 owner 판정이 아니라 검증된 delivery만 수신한다.

## Validation 4 — 운영 영향

Codex/Antigravity watcher는 유지하며 ChatGPT는 별도 routed push path를 추가한다. 기존 raw collector와 watcher poll 구조를 교체하지 않는다.

## Validation 5 — 보안·예외

Target capability, canonical owner, General authority fingerprint, routing revision 중 하나라도 검증되지 않으면 write하지 않는다. shell invocation과 foreign path guessing을 금지하고 stdin envelope + regular-file entrypoint만 허용한다.

## Validation 6 — 롤백

양 scope의 Rule/governance/bootstrap/index를 `D:\Temp\ChatGPT-Routed-Recording-Rollback-20260910`에 보존했다. Mini-Server는 현재 Git HEAD `31f8027b...` 기준 clean 상태이므로 소스 변경도 비교 가능하다.

## Validation 7 — 휴먼 에러

사용자가 reference 경로를 언급한 것만으로 owner가 바뀌지 않도록 transition type을 명시적으로 분리한다. session key를 잃거나 revision이 불명확한 경우 새 owner를 추측하지 않고 fail-closed한다.

## Validation 8 — AI 메타

현재 ChatGPT native raw transcript adapter는 존재하지 않는다. 따라서 구현 결과를 `agent-mediated routed ingest`로만 표시하며 native automatic collector라고 주장하지 않는다. visible user/commentary/final만 입력 가능하고 숨은 reasoning/tool 이벤트는 기록 대상이 아니다.

## 종합

**8/8 통과 — 구현 진행 가능.** 구현 후 temp runtime E2E와 양 governance 전체 회귀를 다시 수행한다.
