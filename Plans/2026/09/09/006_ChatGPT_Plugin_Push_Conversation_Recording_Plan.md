---
artifact_id: PLAN-20260909-006
work_id: WORK-20260909-CHATGPT-PUSH-RECORDER
created_at: 2026-09-09T15:59:44.925+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/09/009_ChatGPT_Plugin_Push_Conversation_Recording_Task.md
  - ../../../../Reports/2026/09/09/013_ChatGPT_Plugin_Push_Conversation_Recording_Plan_Validation_Report.md
---
# [계획서] ChatGPT Plugin Push형 대화 기록 Provider 도입 계획

- 작성일: 2026-09-09
- work_id: `WORK-20260909-CHATGPT-PUSH-RECORDER`
- 작업 모드: 대화 기록 아키텍처 확장 계획 (Plan / Architecture)
- 관련 Task: `Tasks/2026/09/09/009_ChatGPT_Plugin_Push_Conversation_Recording_Task.md`
- 계획 검증 보고서: `Reports/2026/09/09/013_ChatGPT_Plugin_Push_Conversation_Recording_Plan_Validation_Report.md`
- 선행 참고: `Reports/2026/09/09/012_Git_Index_Corruption_Prevention_Independent_Review_Report.md`
- 상태: **계획 수립 완료, 사용자 검토 대기 — 구현 및 현재 세션 기록 미착수**

---

## 1. 배경과 문제 정의

현재 대화 기록기는 로컬 PC에 지속적으로 생성되는 플랫폼 원본을 Pull 방식으로 수집한다.

- Codex: `%USERPROFILE%/.codex/sessions/**/*.jsonl`
- Antigravity: `%USERPROFILE%/.gemini/antigravity*/brain/.../transcript*.jsonl`

현재 ChatGPT 세션은 ChatGPT 웹/앱에서 Remote Desktop Commander Plugin을 호출하여 NKHST-5800H에 접근하는 구조이며, Plugin 자체가 이 ChatGPT 세션 전체를 로컬 transcript 파일로 생성하지 않는다.

따라서 기존 watcher가 아무리 정상이어도 현재 ChatGPT 사용자 발언과 ChatGPT 응답은 Codex/Antigravity 원본 수집 경로에 나타나지 않으며 자동 기록 대상이 될 수 없다.

본 계획의 목적은 ChatGPT에만 **Push형 provider**를 추가하여 기존 공통 event/provenance/projector 체계에 정식 편입하는 것이다.
## 2. 사용자 확정 조건과 범위

이번 계획에는 다음 사용자 결정을 고정 조건으로 반영한다.

1. ChatGPT Plugin 세션을 기록 가능한 정식 provider로 설계한다.
2. ChatGPT Data Export를 이용한 backfill 또는 이중화 경로는 이번 범위에서 제외한다.
3. 현재 진행 중인 ChatGPT 세션은 아직 `Chat/`에 수동 저장하지 않는다.
4. 계획 수립 및 검토 동안 현재 ChatGPT 세션이 자동 기록되지 않는 상태는 사용자가 명시적으로 예외 승인하였다.
5. 위 예외 승인은 현재 대화의 백필·수동 append·강제 기록 승인이 아니다.
6. 본 문서는 계획과 검증만 수행하며 recorder 코드, Rule.md, 노드, 운영 설정은 변경하지 않는다.

### 비목표

- 브라우저 DOM scraping 또는 비공개 ChatGPT 네트워크 API 감시
- ChatGPT Data Export 자동 수집
- 과거 ChatGPT 전체 이력 소급 이관
- Remote Desktop Commander 자체를 대화 원본 저장소로 간주
- assistant 원본 timestamp가 없는데 임의의 발생 시각을 생성하는 동작

---

## 3. 목표 아키텍처

기존 Pull provider와 ChatGPT Push provider를 공통 event core에서 합류시키는 구조를 사용한다.
```text
Codex JSONL ───────────────┐
Antigravity transcript ────┼─> 공통 event core ─> provenance/receipt ─> Chat/YYYY/MM/DD.md
ChatGPT Plugin Push ────────┘
```

ChatGPT provider는 로컬 파일을 polling하지 않는다. ChatGPT가 현재 turn에서 사용자에게 실제 표시되는 이벤트를 생성할 때 프로젝트의 ingest 경로로 전달한다.

초기 구현은 현재 사용 중인 Remote Desktop Commander를 **전송 수단(transport)** 으로 사용할 수 있으나, recorder 내부에서는 transport와 provider 의미를 분리한다. 향후 다른 ChatGPT Plugin/Action으로 교체해도 `provider=chatgpt` event 계약은 유지한다.

### 권장 Push 흐름

1. ChatGPT가 사용자 메시지의 실제 source timestamp와 원문을 확인한다.
2. Plugin을 통해 프로젝트의 ChatGPT ingest 명령을 시작한다.
3. JSON payload는 shell command-line 인자로 넣지 않고 표준입력 또는 동등한 구조화 입력으로 전달한다.
4. ingest 계층이 payload를 검증하여 공통 `createEvent` 입력으로 정규화한다.
5. 기존 writer lock 안에서 중복 검사, provenance 생성, 날짜별 projection, receipt 저장을 수행한다.
6. 성공 receipt를 반환하고, 실패 시 cursor나 receipt를 성공 처리하지 않는다.

원문을 임시 spool 파일에 장기 저장하거나 Git 추적 영역에 별도 복제하지 않는 구조를 우선한다.

---

## 4. ChatGPT Push Event 계약
ChatGPT event는 최소 다음 필드를 가진다.

```json
{
  "provider": "chatgpt",
  "conversation_id": "<stable conversation/thread id>",
  "source_event_id": "<stable event id when available>",
  "actor": "user | assistant",
  "channel": "user | commentary | final_answer",
  "content": "<visible original text>",
  "occurred_at": "<platform timestamp or null>",
  "recorded_at": "<plugin receipt timestamp>",
  "timestamp_source": "platform | plugin_receipt | unavailable"
}
```

### 식별자 원칙

- `conversation_id`는 서로 다른 ChatGPT 대화를 섞지 않기 위한 안정 식별자여야 한다.
- `source_event_id`가 플랫폼에서 제공되면 그대로 사용한다.
- 플랫폼 event ID가 없으면 content만으로 임의 ID를 만들지 않고, 검증된 조합(`conversation_id`, actor, source timestamp, ordinal 등)으로 결정적 ID를 생성한다.
- 동일 이벤트 재전송은 기존 provenance/receipt를 통해 idempotent하게 무시한다.

### 원문 범위

기존 Rule 6-2-2와 동일하게 실제 사용자 발언, 사용자에게 표시된 commentary, 최종 답변만 허용한다. system/developer 지시, 숨은 reasoning, tool call/result, approval 내부 정보는 push payload에 포함하지 않는다.

---
## 5. Timestamp 정책 — 발생 시각과 기록 시각 분리

이 계획의 핵심 설계 항목이다. 현재 `RULE-6.1.7`은 파일 수정 시각이나 기록기 실행 시각을 실제 발언 시각으로 가장하는 것을 금지한다.

ChatGPT 환경에서는 사용자 메시지에 플랫폼 source timestamp가 제공될 수 있지만 assistant 메시지의 source timestamp가 항상 provider 입력으로 노출된다고 보장할 수 없다.

따라서 다음 세 값을 분리한다.

- `occurred_at`: 플랫폼이 제공한 실제 이벤트 발생 시각. 검증할 수 없으면 `null`.
- `recorded_at`: Plugin/ingest가 이벤트를 실제 수신한 시각. 항상 기록 가능.
- `timestamp_source`: `platform`, `plugin_receipt`, `unavailable` 중 하나.

### 표시 규칙 제안

1. `timestamp_source=platform`이면 기존 KST 밀리초 헤더를 그대로 사용한다.
2. `occurred_at`이 없으면 `recorded_at`을 기존 발언 시각처럼 위장하지 않는다.
3. 원본 시각 미제공 이벤트를 위한 명시적 fallback 헤더 규격을 Rule에 신설한다.
4. fallback 헤더는 기록 시각과 원본 발언 시각 미확정 상태를 사람이 구분할 수 있어야 한다.

예시 후보:

```text
## ChatGPT [원본시각 미제공 | 기록 2026-09-09 16:00:00.123 KST]
```

최종 문자열 형식은 Staging에서 기존 header parser, 정렬, 중복 검사와의 호환성을 검증한 후 확정한다.
## 6. Rule.md 및 거버넌스 변경 범위

실제 구현 승인 시 Rule 자체를 변경하는 작업이므로 `review-rule` / `edit-rule` / `sync-rule` 전용 절차를 별도로 수행한다.

최소 검토 대상은 다음과 같다.

| Rule 영역 | 관련 노드 | 예정 변경 취지 |
| :--- | :--- | :--- |
| `RULE-6.1.3` | `records.conversation-integrity`, `workflow.multi-agent-handoff` | ChatGPT 실제 작업자/대상 표기 규격 포함 여부 검토 |
| `RULE-6.1.6` | `records.conversation-storage`, `tools.conversation-exception` | Pull writer 외 검증된 Push ingest 경로 허용 |
| `RULE-6.1.7` | `records.timestamps` | `occurred_at`과 `recorded_at` 분리 및 fallback 시각 정책 |
| `RULE-6.2.1~2` | `records.conversation-storage` | ChatGPT visible event push 범위 명문화 |
| `RULE-6.2.4` | `records.conversation-automation` | Pull preflight와 Push provider health의 관계 정의 |
| `RULE-6.2.9` | `records.conversation-automation` | Push 실패 시 복구/차단 범위 정의 |
| `RULE-6.2.12` | `records.conversation-automation` | 활성 provider에 ChatGPT 추가 |
| `RULE-6.3.1` | `records.conversation-integrity` | 대상 AI 및 timestamp fallback 헤더와 호환 검토 |

필요한 traceability 변경은 `human-rule-map.yaml`, `rule-section-baseline.yaml`, `rule-map.yaml`, `manifest.yaml`이며 실제 변경 섹션의 digest/hash를 동일 작업에서 동기화한다.

신규 capability는 예를 들어 `.agent-governance/capabilities/chatgpt-plugin.yaml`로 분리하고 transport, source timestamp 보장 수준, visible event 범위, 실패 정책을 명시한다.

---

## 7. Recorder 구현 설계
기존 `ACTIVE_PLATFORMS=['codex','antigravity']`는 polling provider 목록으로 유지하고 ChatGPT를 단순히 같은 배열에 넣지 않는다. ChatGPT는 별도 Push ingest 명령 또는 함수로 분리한다.

권장 구조:

```text
conversation-recorder.mjs
  ├─ reconcile/ensure/watch   # 기존 Pull provider
  └─ ingest                   # 신규 Push provider
       └─ chatgpt adapter/validator
            └─ common createEvent/projectEvents
```

### ingest 요구사항

- JSON schema 검증 후 알 수 없는 필드를 임의 해석하지 않는다.
- `provider=chatgpt` 이외의 값을 ChatGPT 경로에서 받으면 fail-closed 한다.
- payload 원문은 shell command-line, 환경변수, error log에 노출하지 않는다.
- 가능한 경우 `stdin` 또는 구조화된 Plugin 입력을 사용한다.
- 기존 `recorder.lock`을 공유하여 Pull reconcile과 Push ingest가 동시에 `Chat/*.md`를 쓰지 못하게 한다.
- `writeFileAtomic` 및 기존 provenance/receipt 체계를 재사용한다.
- 성공 receipt가 생성되기 전에는 전송 성공으로 보고하지 않는다.
- 동일 `source_event_id` 재전송은 중복 Markdown을 만들지 않는다.

Push provider는 watcher polling을 필요로 하지 않으므로 1.5초 polling 부하를 추가하지 않는다.

---

## 8. 실패·복구 및 preflight 정책
ChatGPT Push 실패가 발생했을 때 조용히 누락시키지 않는다. 다만 Pull recorder 장애와 Push 전송 장애를 동일한 실패로 취급하지 않고 provider별 health를 분리한다.

제안 정책:

1. Push ingest 실패 시 해당 event receipt를 만들지 않고 사용자에게 기록 실패를 알린다.
2. 실패한 이벤트 원문을 임의 재구성하거나 timestamp를 추정하지 않는다.
3. 프로젝트 변경 작업 중 기록 실패가 발생하면 기존 Rule의 fail-closed 원칙에 맞춰 이후 일반 파일 변경을 중단하고 복구 경로로 전환한다.
4. 읽기·설명·복구 진단까지 함께 막는 순환 의존성은 `RULE-6.2.9` 복구 예외 개정과 함께 해소한다.
5. 복구 후 provider health와 receipt를 확인하기 전에는 누락이 해소됐다고 보고하지 않는다.

### 현재 세션 예외

현재 ChatGPT 세션은 이미 Push provider가 구현되기 전에 시작되었고 자동 기록 원본이 존재하지 않는다. 사용자는 이 계획을 수립하는 동안 **현재 세션의 Chat 미기록 상태를 명시적으로 예외 승인**하였다.

이 예외의 효력은 다음에 한정한다.

- recorder preflight가 현재 ChatGPT 메시지를 수집하지 못한다는 이유만으로 본 계획 문서 작성을 차단하지 않음.
- 현재 세션을 `Chat/`에 수동 append하거나 backfill하는 권한은 포함하지 않음.
- 이후 사용자가 별도 지시하지 않는 한 현재 세션의 원문 저장 작업은 수행하지 않음.

---

## 9. Staging 구현 및 검증 순서
사용자 구현 승인 후 다음 순서로 진행한다.

1. Rule 변경 대상 섹션과 `human-rule-map` 관계를 `sync-status`로 확인한다.
2. `Staging/`에 Rule 후보, ChatGPT capability 후보, recorder ingest 후보를 작성한다.
3. core event schema에 dual timestamp를 추가하되 기존 Codex/Antigravity event 형식을 깨지 않는 호환 계층을 둔다.
4. ChatGPT push adapter/validator와 ingest 진입점을 구현한다.
5. 기존 Pull provider와 동일한 writer lock/provenance/projector를 사용하도록 통합한다.
6. 테스트 fixture에서 user timestamp 제공, assistant timestamp 미제공, 중복 재전송, 순서 역전, ingest 실패를 각각 검증한다.
7. 기존 Codex/Antigravity 전체 테스트를 함께 실행하여 regression이 없는지 확인한다.
8. Validation 1~8을 수행하고 운영 병합 전 사용자 승인을 받는다.
9. 승인된 Staging 변경만 운영에 반영하고 Rule/노드 hash/digest를 동기화한다.
10. 실제 ChatGPT Plugin 세션에서 소수의 테스트 turn으로 end-to-end 기록을 검증한다.

### 필수 테스트 시나리오

- 사용자 `occurred_at` 존재 → 정확한 KST 헤더 생성
- assistant `occurred_at=null` → fallback 헤더로 기록되고 발생 시각을 위조하지 않음
- 동일 event 2회 push → Markdown 1회만 존재
- Push와 Pull writer 동시 실행 → lock으로 직렬화
- commentary와 final 순서 보존
- Plugin 연결 중단 → receipt 미생성 및 명시적 실패
- secret/redaction 규칙 유지
- 기존 Codex/Antigravity `verify` 결과 변화 없음

---

## 10. 보안 및 데이터 보존 원칙
- ChatGPT 원문은 최종 `Chat/` projection 외에 장기 복제 저장하지 않는다.
- shell argument, process list, 일반 오류 로그에 대화 원문이 노출되지 않게 한다.
- 비밀번호·토큰·개인키·개인정보 치환은 기존 `records.conversation-integrity` 정책을 그대로 적용한다.
- ingest는 프로젝트 workspace를 명시적으로 검증하여 다른 저장소의 Chat에 잘못 기록하지 않는다.
- Plugin transport가 예상하지 않은 원문이나 내부 추론 데이터를 전달해도 허용 event schema 밖의 데이터는 기록하지 않는다.
- 임시 입력 버퍼나 파일이 불가피한 경우 Git 비추적 영역, 제한된 수명, 성공/실패 후 즉시 정리 정책을 별도 검증한다.

---

## 11. 롤백 전략

구현은 기존 Pull recorder와 분리된 additive 구조로 진행한다.

- 운영 문제가 발생하면 ChatGPT Push provider만 비활성화하고 Codex/Antigravity recorder를 유지할 수 있어야 한다.
- Rule 변경은 해당 provider 조항과 timestamp fallback 조항 단위로 되돌릴 수 있어야 한다.
- 기존 `Chat/` 블록을 소급 변환하지 않으므로 rollback 시 과거 기록 전체를 재작성하지 않는다.
- 이미 정상 기록된 ChatGPT 이벤트는 영구 기록으로 보존하며 provider 비활성화를 이유로 삭제하지 않는다.
- rollback 후에도 provenance ID가 재사용되어 재활성화 시 중복 이벤트가 생성되지 않도록 한다.

---

## 12. 구현 승인 전 사용자 검토 항목

본 계획에서 사용자가 실제 구현 전에 최종 확인할 핵심은 **timestamp fallback 헤더의 사용자 가독성**이다.

아키텍처 원칙인 `occurred_at` / `recorded_at` / `timestamp_source` 분리는 유지하되, 원본 assistant timestamp가 없는 이벤트의 Markdown 헤더 문자열은 Staging 후보를 보고 최종 확정한다.
---

## 13. 예상 변경 산출물

구현 승인 시 예상 변경 범위는 다음과 같다.

- `Rule.md`의 대화 저장·timestamp·provider 관련 섹션
- `.agent-governance/records/conversation-storage.md`
- `.agent-governance/records/conversation-automation.md`
- `.agent-governance/records/timestamps.md`
- 필요 시 `.agent-governance/records/conversation-integrity.md`
- `.agent-governance/tools/conversation-exception.md`의 복구 경계
- 신규 `.agent-governance/capabilities/chatgpt-plugin.yaml`
- `.agent-governance/manifest.yaml` 및 traceability 파일
- `.agent-governance/tooling/conversation-recorder.mjs`
- 신규 또는 분리된 ChatGPT push adapter/validator
- `.agent-governance/tooling/conversation-recorder.test.mjs` 및 fixture

## 14. 최종 진행 조건

본 계획과 `013_..._Plan_Validation_Report.md`를 사용자가 검토하여 구현을 별도로 승인하기 전에는 위 파일을 수정하지 않는다.

현재 ChatGPT 세션의 과거 대화를 저장하는 작업 역시 별도 승인 없이는 수행하지 않는다. 이후 Push provider가 운영 활성화되면 **활성화 시점 이후의 신규 visible event부터 기록**하는 것을 기본값으로 하며, 현재/과거 세션의 소급 기록은 독립된 사용자 지시가 있을 때만 수행한다.
