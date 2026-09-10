---
artifact_id: REPORT-20260909-016
work_id: WORK-20260909-RECORDER-PID-REUSE
created_at: 2026-09-09T20:09:51.406+09:00
related_artifacts:
  - ../../../../Plans/2026/09/09/007_Conversation_Recorder_PID_Reuse_Fix_Plan.md
  - ../../../../Tasks/2026/09/09/012_Conversation_Recorder_PID_Reuse_Fix_Task.md
---
# [검증 보고서] Conversation Recorder PID 재사용 오판 수정

- 작성 시각: 2026-09-09T20:05:11.364+09:00
- work_id: `WORK-20260909-RECORDER-PID-REUSE`
- 관련 계획: `Plans/2026/09/09/007_Conversation_Recorder_PID_Reuse_Fix_Plan.md`
- 관련 Task: `Tasks/2026/09/09/012_Conversation_Recorder_PID_Reuse_Fix_Task.md`
- 검증 작업자: Codex
- 상태: 구현 및 검증 완료 (2026-09-09T20:14:11.819+09:00)

## Validation 1 — 거버넌스 준수성

manifest와 41개 노드 검증은 오류·경고 없이 통과했다. 사용자는 증상 조치와 원인 해결을 명시 승인했다. stale 상태 파일은 삭제하지 않고 복구 가능한 이름으로 이동했으며 NexonPlug는 변경하지 않았다. 구현은 Staging 후보 검증 후 운영 도구에 반영한다.

판정: 통과.

## Validation 2 — 사용자 의도 달성도

즉시 증상만 해소하는 데 그치지 않고 PID 재사용 오판의 재발 방지까지 범위에 포함했다. 다른 사용자 작업인 Antigravity 테스트 변경은 보존한다.

판정: 통과.

## Validation 3 — 논리적 구동 가능성

기존 검사는 PID 존재 여부만 확인하므로 PID 재사용을 구분할 수 없다. 프로세스 시작 시각을 함께 검증하면 종료된 recorder와 이후 같은 PID를 받은 무관 프로세스를 구분할 수 있다. 조회 실패 시 active로 취급해 동시 writer lock 탈취를 막는다.

판정: 조건부 통과 — Staging 및 회귀 테스트 필요.

## Validation 4 — 운영 병합 영향

변경은 recorder의 lock/PID owner 판정에만 한정한다. Chat Markdown 형식, event provenance, cursor, receipt 형식은 변경하지 않는다. 신규 lock/PID 필드는 이전 reader가 무시할 수 있는 추가 필드이며 이전 레코드도 fallback 비교로 처리한다.

판정: 통과.

## Validation 5 — 보안과 예외 엣지 케이스

PowerShell 조회에는 정수 검증된 PID만 전달하며 대화 원문이나 외부 입력을 명령줄에 포함하지 않는다. 조회 실패·잘못된 timestamp·권한 오류는 stale로 단정하지 않는다. 손상 JSON lock을 자동 제거하지 않는 기존 정책도 유지한다.

판정: 통과.

## Validation 6 — 롤백과 역방향 파급

코드 diff는 독립적으로 되돌릴 수 있다. stale 상태 파일은 동일 디렉터리에 백업되어 있다. 복구된 Chat 이벤트는 정상 영구 기록이므로 롤백 대상이 아니다.

판정: 통과.

## Validation 7 — 휴먼 에러와 UX 방어

무관한 동일 PID 프로세스를 종료하지 않고 recorder 레코드만 판정한다. 상태 출력이 무관 프로세스를 watcher로 표시하는 문제도 같은 identity 검사로 해소한다.

판정: 통과.

## Validation 8 — AI 메타 거버넌스

PID가 같다는 이유로 NexonPlug를 recorder라고 단정하지 않고 실제 실행 파일과 명령줄을 확인했다. 기존 dirty worktree와 사용자 변경을 보존하고, Rule.md는 이번 범위에서 읽거나 변경하지 않는다.

판정: 통과.

## 선행 종합 판정

차단 조건은 없다. Staging에서 PID 재사용 판정과 fail-safe 동작을 확인한 뒤 구현할 수 있다.

## 구현·검증 결과

### 구현 결과

- `core.mjs`에 프로세스 시작 시각 레코드와 `isRecordedProcessAlive` 판정을 추가했다.
- 신규 lock과 watcher PID 파일은 `processStartedAt`을 저장한다.
- 이전 형식 레코드는 `createdAt`/`startedAt`과 실제 프로세스 시작 시각을 비교한다.
- writer lock, watcher `ensure`, `watch`, `status`가 동일한 identity 판정을 사용한다.
- 시작 시각 조회 실패 시 활성 owner로 취급하는 fail-safe를 유지했다.
- 기존 Antigravity 테스트 변경은 보존하고 PID 재사용 회귀 테스트만 추가했다.

### 실제 장애 복구 결과

- PID `20216`은 `NexonPlug.exe -autostart`로 확인되었고 종료하지 않았다.
- stale lock/PID 파일은 `Chat/.state/recorder.lock.stale-20260909T101951Z`와 `recorder.pid.json.stale-20260909T100346Z`로 보존했다.
- 첫 복구 `ensure`에서 누락 이벤트 13건을 기록했다.
- 수정 전 watcher PID `18788`은 명령줄 identity 확인 후 종료했다.
- 수정된 watcher PID `28512`를 시작했고 `processStartedAt` 기록 및 heartbeat 갱신을 확인했다.
- 두 번째 `ensure`는 새 프로세스를 만들지 않고 PID `28512`를 재사용했다.
- 실제 NexonPlug PID `20216`과 사고 시 lock 시각을 새 판정 함수에 입력한 결과 `staleOwnerAccepted=false`였다.

### 검증 결과

- Staging 후보 테스트: 3/3 통과
- recorder 단독 테스트: 17/17 통과
- 전체 governance tooling 테스트: governance 12/12, recorder 17/17, artifact manager 12/12 통과
- `conversation-recorder verify`: `ok=true`, source events 1137, missing 0, missing receipts 0, duplicates 0
- `governance-tool validate`: 오류 0, 경고 0, 통과
- `git diff --check`: 오류 없음. 기존 working tree의 LF→CRLF 안내만 출력됨

### 후속 Validation 3~8 교차 확인

- 논리: 실제 PID 재사용 사례와 active watcher 재사용 사례가 모두 기대대로 종료되었다.
- 운영 영향: event/cursor/receipt 형식은 바꾸지 않았고 verify 결과 누락·중복이 없다.
- 보안: 정수 PID만 PowerShell 프로세스 조회에 사용하고 대화 원문은 전달하지 않는다.
- 롤백: 코드 diff와 `.stale-*` 상태 백업이 남아 있다.
- 휴먼 에러: 무관 프로세스를 종료하지 않으며 status의 잘못된 실행 표시도 해소했다.
- AI 메타: 기존 dirty worktree의 다른 변경과 Rule.md를 수정하지 않았다.

종합 판정: 완료. 확인된 차단 조건이나 미해결 결함은 없다.
