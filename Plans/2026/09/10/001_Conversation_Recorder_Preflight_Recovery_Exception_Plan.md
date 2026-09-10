---
artifact_id: PLAN-20260910-001
work_id: WORK-20260910-RECORDER-PREFLIGHT-RECOVERY
created_at: 2026-09-10T10:56:47.005+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/10/001_Conversation_Recorder_Preflight_Recovery_Exception_Task.md
  - ../../../../Reports/2026/09/10/005_Conversation_Recorder_Preflight_Recovery_Exception_Implementation_Report.md
---
# [계획서] Conversation Recorder Preflight 복구 예외 거버넌스 보강

- 작성일: 2026-09-10
- `work_id`: `WORK-20260910-RECORDER-PREFLIGHT-RECOVERY`
- 상태: **완료 — governance v1.3.2 운영 반영 및 검증 완료**
- 관련 Task: `Tasks/2026/09/10/001_Conversation_Recorder_Preflight_Recovery_Exception_Task.md`
- 근거 보고서: `Reports/2026/09/10/003_Git_Index_ProcMon_Evidence_and_Codex_Continuation_Report.md`
- 선행 문제 확인: `Reports/2026/09/09/012_Git_Index_Corruption_Prevention_Independent_Review_Report.md`

---

## 1. 문제 정의

현재 `RULE-6.2.4`/`RULE-6.2.9`와 각 AI 진입점은 `conversation-recorder ensure --platform all`이 실패하면 일반 작업을 시작하지 않도록 한다. 정상 상황에서는 대화 무결성을 보장하는 적절한 fail-closed 정책이다.

그러나 recorder 자체의 Chat 저장·잠금·원자적 교체 장애 또는 recorder 거버넌스 결함이 preflight 실패 원인인 경우, 같은 규칙 때문에 recorder를 진단·복구하거나 Rule을 교정하는 작업까지 차단될 수 있다. 2026-09-09 `Chat` atomic rename `EPERM` 사고에서 이 순환 의존성이 실제로 관찰됐다.

Antigravity는 Windows 검색 parser, persistent command grant parser, conversation storage API 등 플랫폼 고유 제약이 capability에 이미 기록되어 있어, 동일한 목적을 달성하더라도 복구 수단이 Codex와 다를 수 있다.

## 2. 목표

- 일반 작업의 fail-closed 기본값은 유지한다.
- recorder 또는 그 거버넌스 자체를 복구하기 위한 **최소 범위 recovery exception**만 명문화한다.
- 플랫폼별 도구 동일성을 강제하지 않고 capability별로 같은 안전 결과를 달성하도록 한다.
- 복구 성공 전 원래 기능 구현·운영 병합으로 복귀하지 못하게 한다.
## 3. 제안하는 Rule 의미 변경

`6-2-9` 자체를 다음 의미로 보강하고 새 하위 조항은 만들지 않는다.

> preflight 재시도 후에도 실패하면 원래 요청의 일반 작업은 차단한다. 단, 실패 원인이 recorder/Chat 저장/잠금/원자적 교체 또는 이 preflight를 구성하는 Rule·노드에 있고, 사용자가 복구를 명시 승인했거나 플랫폼 capability에 검증된 recovery 경로가 정의되어 있으면 recorder 진단·증거 보존·백업·복구·Rule/노드 검토와 그 기록에 필요한 최소 작업만 허용한다. 이 예외는 기능 구현·운영 병합·무관한 일반 파일 변경으로 확대하지 않으며, 복구 후 recorder ensure와 governance validate가 성공하기 전에는 원래 일반 작업으로 복귀하지 않는다.

기존 `6-2-9`가 이미 실패 상태와 작업 차단을 담당하므로 같은 leaf를 보강하는 것이 새 노드/새 router route를 만드는 것보다 구조적으로 단순하다.

## 4. 동기화 대상

최소 변경 대상은 다음과 같다.

- `Staging/Rule.md`의 `6-2-9` 후보.
- `.agent-governance/records/conversation-automation.md`.
- `.agent-governance/records/conversation-storage.md`.
- `AGENTS.md`, `GEMINI.md`, 필요 시 `CLAUDE.md`의 preflight 진입 문구.
- `traceability/human-rule-map.yaml`, `rule-section-baseline.yaml`, manifest Rule hash/version 및 관련 node digest.

`tools.conversation-exception`은 이미 수동 Chat 복구의 승인 범위를 정의하므로, Validation에서 의미 공백이 확인될 때만 추가 변경한다.

## 5. 구현 순서

1. Plan/Task와 현재 증거를 Validation 1~8로 검토한다.
2. 운영 `Rule.md`를 직접 바꾸지 않고 `Staging/Rule.md` 후보를 작성한다.
3. `sync-status`의 현재 Rule hash를 기준으로 `sync-plan --section 6-2-9`를 수행한다.
4. 후보 의미를 대상 실행 노드와 진입점에 동등하게 투영한다.
5. traceability·baseline·manifest를 같은 버전 단위로 갱신한다.
6. `validate --expected-rule-sha`와 recorder ensure를 통과시킨다.
7. 검증 보고서를 발행하고 HUMAN-11.6~11.8의 운영 Rule 반영 경계를 따른다.
## 6. 허용 범위와 차단 범위

Recovery exception에서 허용하는 행위는 recorder 상태 조회, 원본·Chat·receipt·lock의 읽기/증거 보존, 실패 원인 진단, 승인된 복구, 관련 Rule/노드 검토·Staging 후보 작성, 복구 보고서 작성으로 제한한다.

다음은 예외 중에도 차단한다.

- 원래 요청의 기능 개발 또는 운영 코드 변경.
- 운영 배포·병합·destructive data action.
- recorder 장애와 무관한 일반 파일의 임의 수정.
- 원자적 저장 보장을 낮추는 direct-write fallback.
- 플랫폼 capability에 없는 기능을 있다고 가정하는 우회.

## 7. 검증 기준

- 정상 preflight 성공 시 기존 작업 흐름이 변하지 않는다.
- 실패 시 일반 구현은 계속 차단된다.
- recorder 자체 복구만 제한적으로 진행할 수 있고 작업 범위가 문서로 추적된다.
- 복구 후 `ensure` 실패 상태에서는 일반 작업 복귀가 불가능하다.
- Antigravity/Codex/Claude 진입점이 같은 안전 결과를 표현하되 플랫폼별 실제 수단은 capability를 따른다.
- Rule↔노드↔entrypoint↔traceability↔manifest 검증 오류 0건.

## 8. 롤백

후보가 검증되지 않으면 운영 `Rule.md`와 현재 v1.3.1 노드를 그대로 유지하고 Staging 후보만 폐기한다. 운영 반영 후 문제가 발견되면 Rule 6-2-9와 대응 노드·entrypoint·traceability·manifest를 직전 검증 버전으로 같은 변경 단위에서 되돌린다.

---

## 9. 2026-09-10 구현 결과

사용자 명시 승인 후 Staging 통합 Rule 후보와 독립 `.agent-governance` 사본을 구성하여 `6-2-9` 변경을 먼저 검증했다. Staging 후보는 governance v1.3.2, 41노드, 오류 0, 경고 0으로 통과했다.

검증된 후보만 운영 `Rule.md`, 두 conversation 노드, 세 AI entrypoint, section baseline, manifest에 반영했다. 운영 반영 후 `sync-status inSync=true`, governance validate 오류·경고 0, recorder ensure 정상, Git index 불변을 재확인했다.

최종 구현 세부사항은 `Reports/2026/09/10/005_Conversation_Recorder_Preflight_Recovery_Exception_Implementation_Report.md`를 기준으로 한다.
