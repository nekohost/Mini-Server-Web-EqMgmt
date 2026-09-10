---
artifact_id: PLAN-20260909-007
work_id: WORK-20260909-RECORDER-PID-REUSE
created_at: 2026-09-09T20:09:51.405+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/09/012_Conversation_Recorder_PID_Reuse_Fix_Task.md
  - ../../../../Reports/2026/09/09/016_Conversation_Recorder_PID_Reuse_Fix_Report.md
---
# [계획서] Conversation Recorder PID 재사용 오판 수정

- 작성 시각: 2026-09-09T20:05:11.364+09:00
- work_id: `WORK-20260909-RECORDER-PID-REUSE`
- 작업 모드: 버그 수정
- 관련 Task: `Tasks/2026/09/09/012_Conversation_Recorder_PID_Reuse_Fix_Task.md`
- 검증 보고서: `Reports/2026/09/09/016_Conversation_Recorder_PID_Reuse_Fix_Report.md`
- 상태: 구현 및 검증 완료

## 1. 장애 증상과 확인 근거

`conversation-recorder ensure`가 `다른 대화 기록 writer가 실행 중입니다. PID=20216`으로 실패했다. 그러나 PID `20216`의 실제 프로세스는 `NexonPlug.exe -autostart`였고, `conversation-recorder.mjs` Node 프로세스는 존재하지 않았다.

`Chat/.state/recorder.lock`과 `recorder.pid.json`은 이전 recorder의 PID만 보존하고 있었다. Windows가 종료된 recorder의 PID를 NexonPlug에 재사용하자 현재 `isProcessAlive(pid)` 검사가 서로 다른 프로세스를 같은 owner로 오인했다.

## 2. 즉시 복구

- stale `recorder.lock`과 `recorder.pid.json`을 같은 디렉터리의 `.stale-*` 백업명으로 이동한다.
- `ensure`를 다시 실행해 누락 이벤트를 재조정하고 새 watcher를 시작한다.
- NexonPlug 프로세스는 종료하거나 변경하지 않는다.

즉시 복구 결과 누락 이벤트 13건이 기록되었고 watcher PID `18788`이 시작되었다.

## 3. 영구 수정 범위

1. lock/PID 레코드에 recorder 프로세스 시작 시각을 함께 기록한다.
2. PID가 살아 있더라도 현재 PID의 실제 시작 시각이 레코드와 맞지 않으면 PID 재사용으로 판정한다.
3. 이전 형식 레코드는 `createdAt` 또는 `startedAt`보다 현재 프로세스가 나중에 시작했는지 비교해 호환 처리한다.
4. Windows 프로세스 시작 시각 조회가 실패하면 안전 우선으로 활성 owner로 취급한다.
5. writer lock, watcher `ensure`, `watch`, `status`의 모든 PID 판정을 같은 함수로 통합한다.
6. 실제 프로세스가 살아 있는 동시 writer 거부 동작은 유지한다.

## 4. 테스트

- 살아 있는 현재 PID와 오래된 lock 시각 조합이 stale로 회수되는지 확인한다.
- 같은 프로세스 시작 시각을 가진 lock은 동시 writer로 거부되는지 확인한다.
- 오래된 watcher PID 레코드가 `status.running=false`가 되는지 확인한다.
- 기존 recorder 전체 테스트, governance validate, recorder verify를 실행한다.

## 5. 위험과 제한

- Windows 프로세스 시작 시각 조회는 PowerShell을 사용하지만 숫자로 검증한 PID만 인자에 포함하고 shell 확장을 사용하지 않는다.
- 조회 실패 시 stale lock을 삭제하지 않으므로 안전성은 유지되지만 수동 복구가 필요할 수 있다.
- 허용 오차 안에서 극히 빠르게 같은 PID가 재사용되는 경우는 완전히 배제할 수 없으므로 프로세스 시작 시각 레코드를 신규 형식에 포함한다.

## 6. 롤백

- 소스와 테스트 diff를 되돌리면 이전 동작으로 복귀한다.
- 즉시 복구 파일은 `Chat/.state/*.stale-*`에 보존되어 필요 시 원래 이름으로 복원할 수 있다.
- 정상 기록된 Chat 이벤트 13건은 영구 기록이므로 롤백 시 삭제하지 않는다.
