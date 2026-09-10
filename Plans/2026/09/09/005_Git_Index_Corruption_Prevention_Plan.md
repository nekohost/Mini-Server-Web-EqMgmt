---
artifact_id: PLAN-20260909-005
work_id: WORK-20260909-GIT-INDEX-PREVENTION
created_at: 2026-09-10T08:16:08.353+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/09/007_Git_Index_Corruption_Prevention_Task.md
  - ../../../../Reports/2026/09/10/003_Git_Index_ProcMon_Evidence_and_Codex_Continuation_Report.md
---
# [계획서] Git 인덱스 0바이트 손상 방지 및 증거 보존 계획 (3차 개정)

- 최초 작성일: 2026-09-09
- 3차 개정일: 2026-09-10
- `work_id`: `WORK-20260909-GIT-INDEX-PREVENTION`
- 작업 모드: 형상 관리 안정화 및 거버넌스 보강
- 관련 Task: `Tasks/2026/09/09/007_Git_Index_Corruption_Prevention_Task.md`
- 선행 검토: `Reports/2026/09/09/014_Git_Index_Corruption_Prevention_Second_Review_Report.md`
- 상태: **3차 개정 완료 — 사용자 구현 승인에 따라 선행 검증 후 순차 실행**

---

## 1. 확인된 사실

1. `.git/index`가 0바이트가 된 사건은 다음 5건이다.
   - 2026-09-07 14:29:44.776 KST
   - 2026-09-08 09:36:40.278 KST
   - 2026-09-09 11:32:51.702 KST
   - 2026-09-09 15:00:50.584 KST
   - 2026-09-09 16:11:49.318 KST
2. Antigravity 1.2.1의 Inline Diff 구현은 Git 새로고침 뒤 `.git/index`를 읽고 같은 경로에 `vscode.workspace.fs.writeFile()`로 전체 내용을 다시 쓴다. 같은 refresh를 150ms 뒤 한 번 더 실행한다.
3. 해당 쓰기는 Git의 `index.lock` 원자적 교체 절차를 사용하지 않는다. 따라서 중첩 호출이나 프로세스 중단 시 인덱스가 부분 상태 또는 0바이트 상태로 노출될 위험이 있다.
4. `governance-tool validate`, `context`, `conversation-recorder ensure`에는 `.git/index` 직접 쓰기나 `git status` 호출이 없다. `.agent-governance/tooling`에서 확인된 Git subprocess는 `artifact-manager.mjs`의 `git log`뿐이다.
5. Windows 시스템 Git은 `core.autocrlf=true`이고 저장소에는 `.gitattributes`가 없다. `governance-tool.mjs`는 `Rule.md` 원본 바이트의 SHA-256을 검증하므로, Git 체크아웃이 LF를 CRLF로 바꾸면 의미 변경 없이 검증이 실패할 수 있다.

저수준 Process Monitor 호출 스택은 아직 확보하지 않았다. 따라서 과거 5건 각각의 writer PID는 미확정으로 유지하되, Antigravity의 비원자적 직접 index 쓰기는 제거해야 할 확인된 위험 경로로 취급한다.

---

## 2. 목표와 범위

### 목표

- Antigravity Inline Diff의 직접 index 쓰기 경로를 워크스페이스에서 비활성화한다.
- 프로젝트가 제어하는 read-only Git probe는 `GIT_OPTIONAL_LOCKS=0`을 사용하도록 실행 경로와 capability를 고정한다.
- 거버넌스 핵심 파일의 LF를 `.gitattributes`로 고정한다.
- 손상 재발 시 기본 index를 작업 파일로 사용하지 않고 증거를 먼저 보존하는 복구 후보 절차를 설계한다.
- 통제된 재현에서 실제 writer 프로세스와 호출 스택을 확보한다.

### 제외 범위

- Git 성능 설정(`core.preloadindex`, `core.trustctime`, `core.untrackedCache`)을 손상 방지책으로 변경하지 않는다.
- 근거 없이 Windows Defender 제외를 추가하지 않는다.
- `conversation-recorder`의 원자적 rename 실패를 직접 `writeFile`로 우회하지 않는다.
- 손상된 기본 `.git/index`에 곧바로 `git reset` 또는 `git read-tree HEAD`를 실행하지 않는다.
- 자동 복구가 기존 staged 상태까지 복원한다고 보고하지 않는다.

---

## 3. 실행 단계

### 1단계: 즉시 격리

`.vscode/settings.json`에 다음 설정을 추가한다.

```json
"antigravity.enableInlineDiff": false
```

이 설정은 Antigravity가 `InlineDiffZoneRenderer` 대신 `SideBySideDiffZoneRenderer`를 선택하게 한다. VS Code 일반 Diff 표시 설정인 `diffEditor.renderSideBySide`는 이 제어점의 대체 수단으로 사용하지 않는다.

### 2단계: read-only Git probe 격리

1. `.agent-governance/tooling/git-readonly.mjs`를 추가한다.
2. 허용된 조회 subcommand만 실행하며 자식 Git 프로세스에 `GIT_OPTIONAL_LOCKS=0`을 강제한다.
3. Codex, Gemini/Antigravity, Claude capability에 read-only Git probe는 해당 wrapper 또는 동등한 호출별 환경 주입을 사용하도록 명시한다.
4. `artifact-manager.mjs`의 `git log` 호출에도 같은 환경 변수를 명시한다.
5. `GIT_OPTIONAL_LOCKS=0`은 optional refresh write와 optional lock을 억제할 뿐, Antigravity의 `workspace.fs.writeFile()` 직접 쓰기를 차단한다고 표현하지 않는다.

### 3단계: LF 정책 고정

루트 `.gitattributes`에 다음 범위를 `text eol=lf`로 고정한다.

- `.gitattributes`
- `Rule.md`
- `AGENTS.md`
- `GEMINI.md`
- `CLAUDE.md`
- `.agent-governance/**`

현재 dirty worktree의 사용자 변경을 staging하지 않기 위해 `git add --renormalize .`는 자동 실행하지 않는다. 현재 파일의 줄바꿈과 `git check-attr` 결과를 확인하고, fresh checkout 상당의 별도 검증에서 governance hash 안정성을 확인한다.

### 4단계: 증거 보존형 복구 설계

손상이 재발하면 다음 순서만 허용한다.

1. 기본 index 크기·mtime·hash, `index.lock`, HEAD 및 진행 상태를 incident로 기록한다.
2. merge, rebase, cherry-pick, revert, detached/unborn HEAD, sparse index/worktree, submodule/worktree 여부를 검사한다.
3. 기존 index를 보존한다.
4. `GIT_INDEX_FILE=<recovery-candidate>`에 `git read-tree HEAD`를 실행해 후보를 만든다.
5. 같은 alternate index로 `git ls-files --stage`를 검증한다.
6. 사용자 staged 상태 손실 가능성을 보고한다.
7. 기본 index 교체는 별도 구현·검증과 명시적 복구 판단 전에는 자동화하지 않는다.

이번 작업에서는 자동 교체 코드를 운영 preflight에 넣지 않는다. 원인 증거를 지우거나 사용자 staged 상태를 조용히 대체할 수 있기 때문이다.

### 5단계: Process Monitor 통제 재현

- 대상 경로: `.git/index`, `.git/index.lock`
- 대상 연산: `CreateFile`, `WriteFile`, `SetEndOfFile`, rename/replace 계열
- 대상 프로세스: `Code.exe` extension host, `agy.exe`, `git.exe` 및 실제 관찰 프로세스
- 산출물: PML 또는 CSV, 필터 정의, 사건 시각, PID/TID, 호출 스택과 판정 보고서

Process Monitor가 설치되어 있지 않거나 통제 재현을 위해 Inline Diff를 다시 켜야 하는 경우, 외부 도구 반입 위치·실행 영향·복구 절차를 검토 보고서로 먼저 제출하고 사용자 승인을 받은 뒤 수행한다.

---

## 4. 검증 기준

1. `governance-tool validate` 오류·경고 0건.
2. `.vscode/settings.json`의 JSON 파싱 성공과 `antigravity.enableInlineDiff=false` 확인.
3. capability 3종에서 read-only Git probe 정책 확인.
4. wrapper 단위 테스트와 실제 임시 저장소 테스트 통과.
5. wrapper를 통한 `git status` 전후 index 크기·mtime·SHA-256 불변 확인.
6. `.gitattributes`의 `text` 및 `eol=lf` 속성 확인.
7. `git diff --check`에서 새 공백 오류 없음.
8. 기존 사용자 변경과 staged 상태를 수정하지 않았음을 확인.

---

## 5. 롤백

- Inline Diff 격리: `.vscode/settings.json`에서 해당 키를 제거하고 VS Code를 다시 로드한다.
- read-only wrapper: capability의 wrapper 지시와 tooling 파일을 함께 되돌린다.
- LF 정책: `.gitattributes` 항목을 되돌린다. 자동 renormalize를 하지 않으므로 기존 working tree와 index를 역변환하지 않는다.
- 진단 도구: 다운로드·설치 위치와 산출물을 보고서에 기록하고 승인된 범위에서만 제거한다.

---

## 6. 현재 승인 상태

사용자는 2026-09-10에 계획 직접 수정과 안전한 조치 완료를 승인했다. 저장소 내부의 가역적 조치는 추가 승인 없이 수행한다. 외부 Process Monitor 반입 및 의도적 재현은 위 5단계 조건에 따라 별도 검토 보고서와 승인 요청을 거친다.

---

## 7. 2026-09-10 실행 후 증거 갱신

본 계획의 Process Monitor 단계는 사용자 승인 후 격리된 일회용 저장소에서 실행 완료됐다. 세부 결과와 Codex 중단 복원은 `Reports/2026/09/10/003_Git_Index_ProcMon_Evidence_and_Codex_Continuation_Report.md`를 최신 사실 기준으로 사용한다.

확정된 결과는 다음과 같다.

- Antigravity Inline Diff renderer 경로에서 VS Code extension-host가 `.git/index` 전체를 직접 `WriteFile`하는 동작을 ProcMon으로 실증했다.
- 265바이트 전체 쓰기가 네 차례 관찰됐고, 재실행 간격은 약 167ms/162ms로 즉시 실행 + 약 150ms 재실행 코드 구조와 일치했다.
- 정상 재현에서는 index가 0바이트가 되지 않았으므로, 위험한 직접 재쓰기 경로는 확정하되 과거 사건의 정확한 0바이트 실패 조건은 미재현으로 유지한다.
- 실제 작업 저장소 `.git/index`는 실증 전후 불변이었으며 재현은 임시 저장소에서만 수행했다.
- `antigravity.enableInlineDiff=false`, read-only Git wrapper, LF 고정 등의 예방 조치는 유지한다.

따라서 이 Plan의 “Process Monitor 호출 스택 미확보/승인 대기” 문구는 실행 전 이력으로 보존하되, 현재 상태 판정에는 본 섹션과 Report 003을 우선한다.
