---
artifact_id: REPORT-20260909-013
work_id: WORK-20260909-CHATGPT-PUSH-RECORDER
created_at: 2026-09-09T16:03:36.314+09:00
related_artifacts:
  - ../../../../Plans/2026/09/09/006_ChatGPT_Plugin_Push_Conversation_Recording_Plan.md
  - ../../../../Tasks/2026/09/09/009_ChatGPT_Plugin_Push_Conversation_Recording_Task.md
---
# [계획 검증 보고서] ChatGPT Plugin Push형 대화 기록 Provider 도입

- 작성일: 2026-09-09
- work_id: `WORK-20260909-CHATGPT-PUSH-RECORDER`
- 상태: **계획 검증 완료 — 구현은 사용자 승인 대기**
- 관련 계획: `Plans/2026/09/09/006_ChatGPT_Plugin_Push_Conversation_Recording_Plan.md`
- 관련 Task: `Tasks/2026/09/09/009_ChatGPT_Plugin_Push_Conversation_Recording_Task.md`
- 검증 작업자: ChatGPT GPT-5.6 Sol

---

## 1. 검증 범위와 선행 조건

본 검증은 ChatGPT Plugin 세션을 기존 대화 기록기에 Push provider로 추가하는 **계획의 타당성**만 평가한다. 실제 recorder/Rule/노드 수정, 현재 세션 기록, backfill은 수행하지 않았다.

사용자가 확정한 조건은 다음과 같다.

- ChatGPT Push provider 방향 채택
- Data Export backfill/이중화 제외
- 현재 ChatGPT 세션은 아직 저장하지 않음
- 계획 작성 동안 현재 Chat 미기록 상태는 사용자 명시 예외 승인

`governance-tool validate`는 governance v1.3.0, manifest/human map 41개 노드, 오류 0, 경고 0으로 통과했다. `plan + architecture + create-file`은 proposal-or-plan/document-archive/general-file-change 라우트에 정상 매칭되었다.

---

## 2. Validation 1 — 거버넌스 준수성
### 근거

- Plan/Task/Report를 연·월·일 계층과 독립 파일로 분리하였다.
- 실제 구현은 Staging 선행 및 사용자 운영 병합 승인 전까지 차단하였다.
- 향후 Rule 변경은 일반 파일 변경으로 처리하지 않고 `review-rule/edit-rule/sync-rule` 전용 경로를 사용하도록 계획에 명시하였다.
- 현재 Chat 미기록 예외는 계획 문서 작성 허용에만 한정하고 대화 저장 권한으로 확대하지 않았다.

### 위험

현재 `RULE-6.2.4/6.2.9`의 fail-closed와 recorder 복구 예외 사이의 연결 부족은 선행 `012` 보고서에서 이미 확인되었다. 실제 구현 시 이 복구 경계도 함께 정비해야 한다.

**판정: 통과(조건부) — Rule 변경 단계에서 정식 sync 절차 필수.**

---

## 3. Validation 2 — 사용자 의도 달성도

- 사용자가 원한 것은 현재 대화를 억지로 저장하는 것이 아니라 향후 ChatGPT Plugin 세션을 정상 기록할 방법의 계획화이다.
- backfill 이중화는 명시적으로 제외하였다.
- 현재 세션을 저장하지 않는다는 조건을 Task/Plan 양쪽에 기록하였다.
- Push provider가 활성화된 이후 신규 visible event부터 기록하는 것을 기본값으로 하여 사용자 의도와 일치한다.

**판정: 통과.**

---

## 4. Validation 3 — 정적 논리 호환성
### 긍정적 측면

- ChatGPT를 기존 Pull polling 배열에 억지로 넣지 않고 Push ingest로 분리하므로 원본 부재 문제를 구조적으로 해결한다.
- 공통 `createEvent` / writer lock / provenance / projector를 재사용하여 중복 구현을 줄인다.
- Push provider는 1.5초 polling을 추가하지 않아 기존 recorder 부하를 증가시키지 않는다.
- `occurred_at`과 `recorded_at`을 분리하여 `RULE-6.1.7`의 시각 위조 금지 원칙을 유지할 수 있다.

### 위험 및 검증 필요

- ChatGPT conversation/event stable ID가 현재 Plugin runtime에서 어느 수준까지 노출되는지 구현 전에 capability 검증이 필요하다.
- assistant source timestamp가 제공되지 않을 때 fallback header가 기존 parser/정렬 로직과 충돌할 수 있다.
- Push와 Pull이 같은 날짜 파일을 동시에 쓰는 시나리오에서 반드시 동일 writer lock을 사용해야 한다.

**판정: 통과(조건부) — ID와 timestamp capability를 Staging에서 검증해야 함.**

---

## 5. Validation 4 — 운영 병합 영향

구현은 기존 Codex/Antigravity Pull provider를 유지한 채 ChatGPT 경로를 additive하게 추가하는 구조다. ChatGPT provider만 비활성화할 수 있어야 하며 기존 Chat 파일을 소급 변환하지 않는다.

운영 병합 전 기존 recorder 전체 회귀 테스트와 Rule/traceability hash 동기화가 필수이다.

**판정: 통과(조건부).**
---

## 6. Validation 5 — 보안 및 예외 엣지 케이스

- 대화 원문을 shell command-line이나 환경변수로 전달하지 않고 stdin/구조화 입력을 사용하도록 계획하였다.
- system/developer/reasoning/tool 내부 원문은 schema 단계에서 기록 대상에서 제외한다.
- workspace 식별을 강제하여 다른 프로젝트 Chat에 잘못 쓰는 것을 차단한다.
- 실패 payload를 일반 error log에 원문 그대로 남기지 않는다.
- 임시 spool이 필요할 경우 Git 비추적·단기 수명·정리 정책을 별도 검증한다.

추가 위험은 악의적/오류 payload가 `provider`, `actor`, `channel`, timestamp 필드를 조작하는 경우이다. ingest schema는 허용 enum과 필드 조합을 엄격히 검증해야 한다.

**판정: 통과(조건부) — transport 입력 검증 필수.**

---

## 7. Validation 6 — 롤백 및 역방향 파급

- ChatGPT provider는 독립 비활성화할 수 있도록 설계한다.
- 기존 Codex/Antigravity adapter를 수정 최소화하여 rollback 범위를 제한한다.
- 과거 Chat 문서를 소급 변환하지 않으므로 provider 롤백이 기존 기록 대량 rewrite를 요구하지 않는다.
- 정상 기록된 ChatGPT 이벤트는 영구 기록으로 유지하며 provider disable을 이유로 삭제하지 않는다.
- provenance ID 규칙은 재활성화 시 기존 이벤트가 중복 생성되지 않도록 안정적으로 유지해야 한다.

**판정: 통과.**
---

## 8. Validation 7 — 휴먼 에러 및 사용자 가시성

- Push 실패를 조용히 무시하지 않고 receipt 미생성과 실패 상태를 사용자에게 알린다.
- `recorded_at`을 실제 발언 시각처럼 표시하지 않아 사용자가 시간 정보의 신뢰 수준을 구분할 수 있다.
- 현재 세션 미기록 예외를 수동 저장 승인으로 오해하지 않도록 문서에 반복하여 범위를 제한했다.
- 구현 후에는 provider health와 최근 성공 receipt를 사용자가 확인할 수 있는 상태 명령을 제공하는 것이 바람직하다.

**판정: 통과.**

---

## 9. Validation 8 — AI 메타 거버넌스

- 사용자가 아직 저장하지 말라고 한 현재 세션을 기록하지 않았다.
- Data Export/backfill을 유용하다는 이유로 임의 추가하지 않았다.
- 현재 Remote Desktop Commander라는 transport를 ChatGPT 원본 저장소라고 과장하지 않고 transport/provider를 분리하였다.
- assistant source timestamp가 확보되지 않을 가능성을 숨기지 않고 명시적 fallback 정책으로 다루었다.
- 구현 승인을 받은 것으로 확대 해석하지 않고 Plan/Task/Report 문서화까지만 수행하였다.

**판정: 통과.**

---

## 10. 종합 판정

**계획은 사용자 검토 단계로 진행하기에 적합하다. 구현은 아직 승인되지 않았다.**

아키텍처상 가장 중요한 원칙은 다음 세 가지이다.

1. ChatGPT는 Pull polling 대상이 아니라 Push provider로 분리한다.
2. Push transport가 바뀌어도 공통 event/provenance 계약은 유지한다.
3. 원본 발언 시각과 Plugin 기록 시각을 절대 혼동하지 않는다.

구현 전 필수 확인 사항은 stable conversation/event ID capability와 assistant timestamp fallback header의 Staging 호환성이다.

본 검증 과정에서는 `Chat/`에 현재 세션 원문을 추가하지 않았고, recorder 코드·Rule.md·노드·Plugin 설정도 수정하지 않았다.

---

## 11. 검증 중 추가 발견 — Git index 재발

문서 생성 후 최종 `git diff --check`를 `GIT_OPTIONAL_LOCKS=0` 환경에서 실행했으나 `fatal: .git/index: index file smaller than expected`로 실패했다.

직접 파일 메타데이터 확인 결과 `.git/index`는 2026-09-09 16:02:39.800 KST에 수정되었고 크기는 0바이트였다.

이번 재발은 ChatGPT가 Remote Desktop Commander Plugin을 통해 Plan/Task/Report/index 파일을 작성한 세션 중 관찰되었다. 따라서 선행 `012` 보고서의 "Antigravity/Gemini 파일 변경 시에만 발생"은 당시 사용자 재현 관찰로서는 유효했지만, 현재 증거 기준으로는 독점적 조건으로 유지할 수 없다. 다만 본 검증만으로 ChatGPT/Remote Desktop Commander가 직접 index를 truncate했다고 인과를 확정하지 않는다.

본 작업 범위에는 Git index 복구 승인이 포함되지 않았으므로 복구·백업·Git 설정 변경은 수행하지 않았다. 이 때문에 `git diff --check` 최종 검증은 **차단 상태**로 기록한다.
