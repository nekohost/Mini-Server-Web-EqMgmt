---
artifact_id: PLAN-20260909-005
work_id: WORK-20260909-GIT-INDEX-PREVENTION
created_at: 2026-09-10T08:16:08.353+09:00
updated_at: 2026-09-10T16:47:00+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/09/007_Git_Index_Corruption_Prevention_Task.md
  - ../../../../Reports/2026/09/10/001_Git_Index_Corruption_Prevention_Third_Revision_Validation_Report.md
  - ../../../../Reports/2026/09/10/002_Git_Index_Corruption_Prevention_Implementation_and_ProcMon_Approval_Report.md
  - ../../../../Reports/2026/09/10/003_Git_Index_ProcMon_Evidence_and_Codex_Continuation_Report.md
---
# [계획서] Git 인덱스 0바이트 손상 방지 및 증거 보존 계획 (4차 개정)

- 최초 작성일: 2026-09-09
- 3차 개정일: 2026-09-10
- 4차 개정일: 2026-09-10
- `work_id`: `WORK-20260909-GIT-INDEX-PREVENTION`
- 작업 모드: 형상 관리 안정화 및 거버넌스 보강
- 관련 Task: `Tasks/2026/09/09/007_Git_Index_Corruption_Prevention_Task.md`
- 선행 검토: `Reports/2026/09/09/014_Git_Index_Corruption_Prevention_Second_Review_Report.md`
- 실증 보고서: `Reports/2026/09/10/003_Git_Index_ProcMon_Evidence_and_Codex_Continuation_Report.md`
- 상태: **4차 개정 완료 — 1~5단계 즉시 예방 조치 및 ProcMon 위험 경로 실증 완료, 잔여 0바이트 세부 재현 조건은 사후 forensic 과제로 유지**

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
6. 2026-09-10 통제된 Process Monitor 재현(`Reports/2026/09/10/003`)에서 VS Code extension-host `Code.exe`(PID 29080)가 Antigravity Inline Diff renderer의 Git refresh 경로를 통해 `.git/index`에 265바이트 전체를 비원자적 `WriteFile`로 4회 직접 쓰는 동작과 호출 스택을 캡처했다. (재실행 간격 약 167ms, 162ms)
7. 격리된 단독 실행 정상 재현에서는 index가 0바이트로 절단되지 않았다. 따라서 Antigravity Inline Diff가 `index.lock` 원자적 교체 없이 직접 재쓰는 위험 경로는 실증 확정되었으나, 과거 5건에서 0바이트를 유발한 Windows 파일 잠금 경합·비정상 프로세스 중단 등 복합 조건은 미재현 상태로 유지한다.

Process Monitor 실증을 통해 Antigravity 비원자적 직접 index 쓰기 경로가 확정되었으며, 격리 및 방지 조치(1~3단계)가 실환경에 적용되었다. 미재현된 0바이트 세부 조건은 차단 조건이 아닌 사후 forensic 과제로 관리한다.

---

## 2. 목표와 범위

### 목표

- Antigravity Inline Diff의 직접 index 쓰기 경로를 워크스페이스에서 비활성화한다. **[완료]**
- 프로젝트가 제어하는 read-only Git probe는 `GIT_OPTIONAL_LOCKS=0`을 사용하도록 실행 경로와 capability를 고정한다. **[완료]**
- 거버넌스 핵심 파일의 LF를 `.gitattributes`로 고정한다. **[완료]**
- 손상 재발 시 기본 index를 작업 파일로 사용하지 않고 증거를 먼저 보존하는 복구 후보 절차를 설계한다. **[완료]**
- 통제된 재현에서 실제 writer 프로세스와 호출 스택을 확보한다. **[완료]** (`Reports/2026/09/10/003`)
- 향후 일상 개발 환경에서 해당 보호 설정을 유지하고, 잔여 0바이트 발생 메커니즘을 백그라운드 forensic 과제로 모니터링한다. **[운영 지속]**

### 제외 범위

- Git 성능 설정(`core.preloadindex`, `core.trustctime`, `core.untrackedCache`)을 손상 방지책으로 변경하지 않는다.
- 근거 없이 Windows Defender 제외를 추가하지 않는다.
- `conversation-recorder`의 원자적 rename 실패를 직접 `writeFile`로 우회하지 않는다.
- 손상된 기본 `.git/index`에 곧바로 `git reset` 또는 `git read-tree HEAD`를 실행하지 않는다.
- 자동 복구가 기존 staged 상태까지 복원한다고 보고하지 않는다.

---

## 3. 실행 단계

### 1단계: 즉시 격리 [완료]

`.vscode/settings.json`에 다음 설정을 적용 완료했다.

```json
"antigravity.enableInlineDiff": false
```

이 설정은 Antigravity가 `InlineDiffZoneRenderer` 대신 `SideBySideDiffZoneRenderer`를 선택하게 하여 문제의 Git refresh 경로 호출을 차단한다. VS Code 일반 Diff 표시 설정인 `diffEditor.renderSideBySide`는 이 제어점의 대체 수단으로 사용하지 않는다.

### 2단계: read-only Git probe 격리 [완료]

1. `.agent-governance/tooling/git-readonly.mjs` wrapper를 구현했다.
2. 허용된 조회 subcommand만 실행하며 자식 Git 프로세스에 `GIT_OPTIONAL_LOCKS=0`을 강제한다.
3. Codex, Gemini/Antigravity, Claude capability에 read-only Git probe는 해당 wrapper 또는 동등한 호출별 환경 주입을 사용하도록 명시했다.
4. `artifact-manager.mjs`의 `git log` 호출에도 같은 환경 변수를 명시했다.
5. `GIT_OPTIONAL_LOCKS=0`은 optional refresh write와 optional lock을 억제할 뿐, Antigravity의 `workspace.fs.writeFile()` 직접 쓰기를 차단한다고 표현하지 않는다.

### 3단계: LF 정책 고정 [완료]

루트 `.gitattributes`에 다음 범위를 `text eol=lf`로 고정 완료했다.

- `.gitattributes`
- `Rule.md`
- `AGENTS.md`
- `GEMINI.md`
- `CLAUDE.md`
- `.agent-governance/**`

현재 dirty worktree의 사용자 변경을 staging하지 않기 위해 `git add --renormalize .`는 자동 실행하지 않았으며, `git check-attr`와 파일 인코딩 검사를 통해 줄바꿈 일관성과 거버넌스 해시 안정성을 확인했다.

### 4단계: 증거 보존형 복구 설계 [완료]

손상이 재발할 경우 다음 순서만 허용하도록 복구 절차를 규정했다.

1. 기본 index 크기·mtime·hash, `index.lock`, HEAD 및 진행 상태를 incident로 기록한다.
2. merge, rebase, cherry-pick, revert, detached/unborn HEAD, sparse index/worktree, submodule/worktree 여부를 검사한다.
3. 기존 index를 보존한다.
4. `GIT_INDEX_FILE=<recovery-candidate>`에 `git read-tree HEAD`를 실행해 후보를 만든다.
5. 같은 alternate index로 `git ls-files --stage`를 검증한다.
6. 사용자 staged 상태 손실 가능성을 보고한다.
7. 기본 index 교체는 별도 구현·검증과 명시적 복구 판단 전에는 자동화하지 않는다.

위험한 자동 교체 코드는 운영 preflight에 넣지 않으며, 원인 증거 보존을 최우선으로 한다.

### 5단계: Process Monitor 통제 재현 [완료]

- 격리된 일회용 저장소 및 portable VS Code 환경에서 Process Monitor 통제 재현을 완료했다 (`Reports/2026/09/10/003`).
- VS Code extension host `Code.exe` (PID 29080)가 Antigravity Inline Diff의 Git refresh 경로에서 `.git/index`에 265바이트 전체를 비원자적 `WriteFile`로 4회 직접 쓰는 동작과 호출 스택을 캡처했다.
- 대용량 PML 및 stack XML 증거 파일은 작업 저장소를 오염시키지 않도록 임시 증거 경로에 안전하게 보존되었다.

### 6단계: 사후 운영 모니터링 및 잔여 forensic 대응 [운영 중]

- 1~3단계의 예방 설정(`antigravity.enableInlineDiff=false`, read-only Git probe 격리, `.gitattributes` LF 고정)을 일상 개발 환경에서 지속 유지한다.
- 과거 사건에서 실제로 0바이트 절단을 유발한 세부 OS/동시성 실패 조건은 프로젝트 일반 작업을 차단하지 않는 별도 forensic 과제로 분리하여 관리한다.

---

## 4. 검증 결과

1. `governance-tool validate` 검증: **통과** (42개 노드 정상, 오류 0건, 경고 0건).
2. `.vscode/settings.json` 파싱 및 `antigravity.enableInlineDiff=false` 적용 확인: **통과**.
3. capability 3종에서 read-only Git probe 정책 확인: **통과**.
4. wrapper 단위 테스트 및 임시 저장소 테스트: **통과**.
5. wrapper를 통한 `git status` 전후 index 크기·mtime·SHA-256 불변 확인: **통과**.
6. `.gitattributes`의 `text` 및 `eol=lf` 속성 확인: **통과**.
7. `git diff --check` 공백 오류 없음: **통과**.
8. 기존 사용자 작업 영역 및 실제 저장소 `.git/index` (32,063 bytes) 불변 확인: **통과**.

---

## 5. 롤백 방안

- Inline Diff 격리: `.vscode/settings.json`에서 해당 키를 제거하고 VS Code를 다시 로드한다.
- read-only wrapper: capability의 wrapper 지시와 tooling 파일을 함께 되돌린다.
- LF 정책: `.gitattributes` 항목을 되돌린다. 자동 renormalize를 하지 않으므로 기존 working tree와 index를 역변환하지 않는다.
- 진단 도구: 다운로드·설치 위치와 산출물을 보고서에 기록하고 승인된 범위에서만 제거한다.

---

## 6. 승인 및 개정 이력

- **2026-09-09 (1·2차 개정)**: 초기 계획 수립 및 독립 감사 보고서(012, 014) 검토의견을 수용하여 위험한 자동 index 재설정 제거, 진단 분리, 공통 `work_id` 체계 도입.
- **2026-09-10 08:30 KST**: 사용자로부터 계획 직접 수정 및 1~5단계 안전한 조치(Process Monitor 통제 재현 포함) 실행 승인 획득.
- **2026-09-10 (3차 개정)**: 1~3단계 즉시 예방 조치 반영 및 통제 재현 환경 설계.
- **2026-09-10 (4차 개정)**: Process Monitor 실증 완료(`Code.exe` PID 29080의 비원자적 `WriteFile` 포착) 및 Codex 중단 작업 복원 결과를 전면 반영하여 1~5단계 완료 상태로 정리하고, 잔여 0바이트 세부 재현 조건을 사후 forensic 과제로 분리 명시.

---

## 7. 잔여 과제 및 사후 관리

1. **0바이트 세부 실패 조건 forensic 추적**:
   격리 단독 재현에서는 index가 265바이트로 정상 갱신되어 0바이트 절단이 발생하지 않았다. 따라서 향후 예방 설정에도 불구하고 유사 증상이 관찰될 경우, 4단계의 alternate index 증거 보존 절차에 따라 즉시 incident를 기록하고 보존된 PML/XML 증거와 대조 분석한다.
2. **거버넌스 순환 차단 개선 분리**:
   `Chat` 저장/원자적 교체 실패 시 recorder preflight가 진단 작업까지 차단하는 순환 의존성 문제는 본 Git index 작업과 분리하여 거버넌스 복구 예외 과제로 독립 관리한다.
