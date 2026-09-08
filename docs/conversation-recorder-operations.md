# 대화 자동 기록기 운영 가이드

## 적용 범위

대화 기록기는 개발 PC의 Codex 및 Antigravity 원본에서 현재 프로젝트의 사용자 대화와 허용된 하위 에이전트 handoff를 읽어 Git 제외 경로인 `Chat/`에 저장한다. Flask 애플리케이션, DB와 Linux 서비스에는 접근하지 않는다. Claude는 이번 버전에서 지원하지 않는다.

## 일반 작업 전 실행

플랫폼 진입점이 다음 명령 중 하나를 manifest 검증보다 먼저 실행한다.

```powershell
node .agent-governance/tooling/conversation-recorder.mjs ensure --platform all --workspace . --json
```

`ensure`는 미반영 이벤트를 먼저 재조정하고 살아 있는 watcher가 없을 때 숨김 백그라운드 프로세스 하나를 시작한다. VS Code가 폴더 열기 자동 Task를 허용하면 `.vscode/tasks.json`도 Codex와 Antigravity watcher를 보조 시작한다.

## 점검 명령

```powershell
node .agent-governance/tooling/conversation-recorder.mjs status --workspace . --json
node .agent-governance/tooling/conversation-recorder.mjs verify --workspace . --platform all --json
node .agent-governance/tooling/conversation-recorder.mjs reconcile --workspace . --platform all --force --json
```

- `status --json`: watcher PID, 마지막 재조정, 플랫폼 상태, receipt와 원본 수를 표시한다.
- `verify`: 원본 이벤트, Chat provenance, 하위 companion과 receipt의 누락·중복을 대조한다. 불일치가 있으면 종료 코드 2를 반환한다.
- `reconcile`: 변경된 원본을 한 번 반영한다. `--force`는 fingerprint와 무관하게 전체 원본을 다시 대조한다.

## 파일과 장애 처리

- 상태: `Chat/.state/conversation-recorder.json`
- PID: `Chat/.state/recorder.pid.json`
- 오류: `Chat/.state/recorder-errors.log`
- writer 잠금: `Chat/.state/recorder.lock`
- 하위 작업: `Chat/Subagents/YYYY/MM/DD/*.md`

writer는 임시 파일을 `fsync`한 뒤 원자적으로 교체한다. Chat 기록이 확인된 뒤에만 receipt와 원본 fingerprint를 갱신하므로 중단 후 같은 이벤트를 다시 대조해도 provenance가 중복을 막는다.

오류가 반복되면 `status --json`과 오류 로그를 확인한다. 손상된 원본이나 알 수 없는 스키마가 원인이면 해당 플랫폼 cursor는 전진하지 않는다. 상태 파일을 임의로 삭제한 뒤 전체 append하지 않고 `verify`와 provenance 대조로 복구한다.

## watcher 종료와 롤백

`status --json`에서 확인한 PID에 정상 종료 신호를 보낸다. 다음 `ensure`가 stale PID를 식별하고 필요하면 다시 시작한다.

자동화를 롤백할 때는 세 진입점의 preflight, `records.conversation-automation` 노드, router·manifest·capability와 recorder 코드를 같은 변경 단위로 되돌린다. 이미 정상적으로 생성된 Chat 기록은 삭제하지 않는다.
