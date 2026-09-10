---
artifact_id: REPORT-20260909-014
work_id: WORK-20260909-GIT-INDEX-REVIEW-2
created_at: 2026-09-09T16:28:45.580+09:00
related_artifacts:
  - ../../../../Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md
  - ../../../../Tasks/2026/09/09/010_Git_Index_Corruption_Prevention_Second_Review_Task.md
---
# [2차 독립 검토 보고서] Git 인덱스 0바이트 손상 방지 2차 개정안 재검토

- 작성일: 2026-09-09
- work_id: `WORK-20260909-GIT-INDEX-REVIEW-2`
- 상태: **검토 완료 — 핵심 방향 수용, 구현 전 3차 수정 필요**
- 검토 대상: `Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md` (2차 개정안)
- 관련 구현 Task: `Tasks/2026/09/09/007_Git_Index_Corruption_Prevention_Task.md`
- 선행 검토: `Reports/2026/09/09/012_Git_Index_Corruption_Prevention_Independent_Review_Report.md`
- 본 검토 Task: `Tasks/2026/09/09/010_Git_Index_Corruption_Prevention_Second_Review_Task.md`
- 검토 작업자: ChatGPT GPT-5.6 Sol
- Chat 기록: 사용자 명시 승인에 따라 현재 ChatGPT 세션 자동 기록 예외 적용

---

## 1. 종합 판정

2차 개정안은 1차 계획의 핵심 문제였던 과도한 원인 단정, 근거 없는 Git 성능 설정, Defender 전체 제외, 무조건 `git reset` 복구를 대부분 제거하여 **기술적 방향은 현저히 개선되었다.**

특히 다음 항목은 그대로 유지할 가치가 있다.

1. Antigravity/Gemini 파일 변경 시점과 손상 발생의 높은 상관관계를 유지하되 저수준 writer는 미확정으로 구분한 점.
2. 읽기 전용 Git probe의 optional index refresh를 억제하려는 방향.
3. merge/rebase/cherry-pick/revert 상태를 확인한 뒤 복구하려는 상태 인식형 접근.
4. Defender 제외를 직접 증거 확보 전까지 보류한 점.
5. 복구 사실과 staged 상태 손실 가능성을 사용자에게 숨기지 않는 점.

그러나 **현재 문서 그대로 구현 승인해서는 안 된다.** 아래 4개 차단 항목을 수정한 뒤 재검토해야 한다.
## 2. 구현 승인 차단 항목

### 2.1 1단계의 `GIT_OPTIONAL_LOCKS=0` 적용 대상이 현재 코드와 맞지 않음

2차 계획은 `governance-tool.mjs`, `conversation-recorder.mjs` 등에 `GIT_OPTIONAL_LOCKS=0`을 적용한다고 적었다. 그러나 본 검토에서 `.agent-governance` 전체를 정적 검색한 결과 현재 이 도구들에는 `git status`, `git diff`, `GIT_OPTIONAL_LOCKS` 또는 Git subprocess 실행 코드가 발견되지 않았다.

따라서 현재 계획 문구대로 거버넌스 도구에 환경 변수를 추가해도 **실제로 억제할 Git probe가 없다.**

Git 공식 문서는 background `git status`가 index stat 정보를 refresh하고 이를 다시 index에 기록할 수 있으며, background script에는 `git --no-optional-locks status`를 고려하라고 명시한다. `GIT_OPTIONAL_LOCKS=0`은 동일한 의미이다.

또한 2026-08-10 공개된 VS Code Agent Host 이슈 #329893은 Agent Host 자체의 read-only `git status` / `git diff`가 optional lock을 사용해 race를 만들 수 있음을 기록하고, 해당 **read-only probe 각각에만** `GIT_OPTIONAL_LOCKS=0`을 적용하는 수정을 제안한다.

따라서 1단계는 다음과 같이 바꿔야 한다.

- 먼저 Antigravity/VS Code가 실제로 실행하는 Git subprocess를 Process Monitor 등으로 식별한다.
- 프로젝트가 직접 실행하는 read-only Git 명령이 발견되면 그 호출 지점에만 `GIT_OPTIONAL_LOCKS=0`을 적용한다.
- 외부 확장 내부 probe라면 저장소 코드 변경으로 해결된다고 가장하지 않고, 확장/Agent Host 환경에서 적용 가능한 실제 제어 지점을 별도 확인한다.
- `GIT_OPTIONAL_LOCKS=0`을 "index write 원천 차단"이라고 표현하지 않고 **optional refresh write 및 optional lock 억제**라고 표현한다.

**판정: 방향 수용, 대상과 구현 위치 재정의 필요.**
### 2.2 상태 인식형 복구는 개선됐지만 복구 대상 index를 직접 쓰지 않는 편이 더 안전함

2차 계획은 단일 HEAD 상태에서 `git read-tree HEAD`로 index를 재구성하도록 수정했다. `git read-tree`가 working tree 파일을 직접 수정하지 않는다는 방향은 타당하다.

다만 손상된 기본 `.git/index`가 이미 존재하는 상태에서 곧바로 기본 index를 대상으로 복구 명령을 수행하면, 손상 index 읽기 실패나 복구 도중 추가 실패 시 원본/후보 상태가 섞일 수 있다.

Git은 공식적으로 `GIT_INDEX_FILE` 환경 변수로 alternate index를 지원한다. 따라서 다음 구조가 더 안전하다.

1. 0바이트 `.git/index`의 크기·mtime 및 `.git/index.lock` 존재 여부를 incident에 기록한다.
2. merge/rebase/cherry-pick/revert 상태와 HEAD 유효성을 먼저 검사한다.
3. 기존 index는 그대로 보존하고 별도 경로(예: `.git/index.recovery.<incident-id>`)를 `GIT_INDEX_FILE`로 지정한다.
4. 해당 alternate index에 `git read-tree HEAD`를 실행하여 복구 후보를 생성한다.
5. 같은 `GIT_INDEX_FILE`을 사용해 `git ls-files --stage` 등으로 후보가 읽히는지 검증한다.
6. 검증 성공 후에만 기본 `.git/index` 교체를 시도한다. Windows 파일 잠금으로 교체가 실패하면 후보를 보존하고 fail-closed한다.
7. 이후 `git --no-optional-locks status`와 `git fsck --full --no-dangling`을 수행한다.

이 방식은 **손상된 기본 index를 복구 과정의 작업 파일로 사용하지 않는다**는 장점이 있다. staged 상태가 이미 0바이트화로 사라졌을 가능성은 여전히 존재하므로 복구 후보가 HEAD와 일치한다고 해서 기존 staged 상태까지 복원됐다고 보고해서는 안 된다.

또한 현재 계획의 순서는 Self-Healing이 Process Monitor 진단보다 앞선다. 원인 특정이 아직 완료되지 않은 기간에는 최소한 **진단 증거 캡처 → 복구** 순서를 보장해야 한다. 자동 복구가 가해 프로세스의 흔적을 먼저 지워서는 안 된다.

**판정: 개념 수용, alternate-index 기반 후보 생성과 진단 우선 순서로 보강 필요.**
### 2.3 4단계 `rename 실패 → 직접 writeFile fallback`은 현재 Rule과 충돌하며 제거해야 함

이 항목은 2차 개정안의 가장 큰 문제다.

현재 `Rule.md`의 `RULE-6.1.5`는 대화 기록 시 **임시 파일을 fsync한 뒤 원자적으로 교체**하도록 명시한다. `RULE-6.1.6` 역시 전용 writer가 단일 잠금과 원자적 교체를 사용하도록 규정한다. 대응 노드 `records.conversation-storage`도 동일 원칙을 유지한다.

실제 `core.mjs`의 `writeFileAtomic()`은 다음 순서를 사용한다.

1. 같은 디렉터리에 고유 임시 파일 생성
2. UTF-8 전체 본문 기록
3. `fsync`
4. 핸들 close
5. `rename(temporaryPath, targetPath)`로 원자적 교체
6. Windows 교체 실패 시 기존 대상은 삭제하지 않고 임시 파일을 정리한 뒤 오류 반환

즉 현재 구현은 **완성되지 않은 Markdown/JSON이 노출되지 않도록 의도적으로 fail-closed**한다.

2차 계획의 제안처럼 `EPERM`/`EBUSY` 시 target에 `writeFile()`을 직접 수행하면 원자성이 사라진다. 프로세스 중단·부분 쓰기·동시 편집이 발생할 경우 실제 일자 Chat 또는 `.state` 파일이 부분 상태가 될 수 있다.

더욱 중요한 점은 `writeFileAtomic()`이 Chat Markdown만을 위한 함수가 아니라 recorder state JSON 등에도 재사용된다는 것이다. 공통 함수에 직접쓰기 fallback을 넣으면 receipt/cursor 상태 파일의 손상 위험까지 함께 확대된다.

또한 현재 `EPERM` 원인이 "Chat 파일이 에디터에 열려 있기 때문"이라는 직접 증거도 아직 없다. 원인 미확정 상태에서 원자성 보장을 제거하는 것은 문제를 해결하기보다 더 위험한 실패 모드를 추가한다.

직접 `writeFile`이 다른 프로세스의 공유 모드 때문에 성공한다는 보장도 없으므로, **안전성을 낮추면서 해결 성공도 보장하지 못한다.**

**판정: 4단계는 현 계획에서 제거 또는 별도 recorder 장애 복구 계획으로 분리. 현재 형태는 구현 금지.**
### 2.4 문서 추적성 문제: `work_id` 누락 및 구현 Report 번호 충돌

`workflow.plans`와 `Rule.md` 제7-2-3/7-2-4는 Plan·Task·Report를 공통 `work_id`로 연결하도록 요구한다. 그러나 현재 `005` Plan과 `007` Task에는 공통 `work_id`가 없다.

따라서 3차 개정 시 예를 들어 다음과 같은 공통 ID를 부여해야 한다.

```text
WORK-20260909-GIT-INDEX-PREVENTION
```

그리고 Plan 005, Task 007, 향후 구현/검증 Report가 동일 ID를 사용해야 한다.

또한 `007_Git_Index_Corruption_Prevention_Task.md`는 결과 보고서를 다음 경로로 예약하고 있다.

```text
Reports/2026/09/09/013_Git_Index_Corruption_Prevention_Implementation_Report.md
```

하지만 `013`은 이미 다음 문서가 사용 중이다.

```text
013_ChatGPT_Plugin_Push_Conversation_Recording_Plan_Validation_Report.md
```

따라서 구현 Report 번호를 `013`으로 고정하면 문서 생명주기 규칙과 충돌한다. 향후 실제 발급 시점의 다음 가용 순번을 다시 확인하도록 Task를 수정해야 한다.

**판정: 거버넌스 문서 메타데이터 수정 필수.**

---

## 3. 2차 개정안에서 적절하게 수정된 항목
### 3.1 사실과 가설의 분리

2차 개정안은 1차 계획의 "NTFS/IDE/Defender가 근본 원인"이라는 단정을 제거하고, 사용자 반복 관찰과 저수준 미확정 사실을 분리했다. 이 수정은 적절하다.

본 검토 직전 원격 ChatGPT 작업 시간대에도 `.git/index` 0바이트 상태가 관찰되었지만, 사용자 추가 설명에 따르면 같은 시간대 Antigravity/Gemini가 별도로 파일 변경 작업을 수행하며 계속 오류를 발생시키고 있었다. 따라서 그 사건은 Remote Desktop Commander 경로의 독립 재현 사례로 사용할 수 없다.

현재 증거 수준에서는 다음 표현이 가장 적절하다.

- Antigravity/Gemini 파일 변경 시점은 **높은 신뢰도의 재현 트리거/상관 조건**이다.
- 정확한 `.git/index` writer PID·바이너리·파일 연산은 **미확정**이다.
- Defender 개입은 **미확정**이다.

### 3.2 기존 Git 성능 config 제거

`core.fscache`, `core.preloadindex`, `core.trustctime`, `core.untrackedCache`를 corruption 직접 방지책에서 제거한 것은 적절하다. 특히 현재 시스템에는 이미 `core.fscache=true`가 존재하므로 이전 중복 제안도 해소되었다.

### 3.3 Defender 제외 보류

저수준 증거 없이 프로젝트 전체를 Defender 제외하는 방안을 제거한 것은 적절하다. 문제 원인을 좁히기 전에 보안 가시성을 낮출 이유가 없다.

### 3.4 상태 인식형 중단 조건

`MERGE_HEAD`, rebase 디렉터리, `CHERRY_PICK_HEAD`, `REVERT_HEAD`를 검사하고 해당 상태에서는 자동 재구성을 중단한다는 방향은 적절하다. 여기에 detached HEAD, unborn HEAD, sparse index/worktree 여부도 구현 단계의 추가 엣지 케이스로 포함하는 것이 좋다.

---

## 4. 권고하는 3차 계획의 실행 순서
권고 순서는 다음과 같다.

1. **문서 정합성부터 수정**
   - Plan 005 / Task 007에 공통 `work_id` 추가.
   - Task 007의 고정된 Report 013 경로 제거 또는 다음 가용 순번 방식으로 수정.
2. **진단 대상 실제 식별**
   - Antigravity/Gemini 파일 변경 직전 Process Monitor를 준비.
   - `.git/index`, `.git/index.lock`에 대한 Process Name/PID, CreateFile, WriteFile, SetEndOfFile, rename/replace, Result를 캡처.
3. **실제 read-only Git probe에만 optional-lock 억제 적용**
   - 확인된 `status`/read-only `diff` 호출 지점에 `GIT_OPTIONAL_LOCKS=0` 또는 `--no-optional-locks` 적용.
   - 외부 확장 내부 호출은 제어 가능성을 먼저 검증.
4. **index health guard 및 증거 보존**
   - 크기 0 또는 최소 index 구조 미달 감지.
   - 메타데이터, HEAD, 진행 상태, lock 존재 여부를 incident로 기록.
5. **alternate index에 복구 후보 생성**
   - `GIT_INDEX_FILE=<recovery-file>` + `git read-tree HEAD`.
   - 후보 index를 별도로 검증.
6. **검증된 후보만 기본 index로 교체 시도**
   - 교체 실패 시 직접 write로 우회하지 않고 후보와 incident를 보존한 채 중단.
7. **사후 검증**
   - `git --no-optional-locks status`.
   - `git fsck --full --no-dangling`.
   - staged 상태가 복원됐다고 과장하지 않고 손실 가능성을 보고.
8. **recorder `EPERM` 문제는 별도 계획으로 분리**
   - 먼저 실제 잠금 프로세스/공유 모드를 확인.
   - Rule 6-1-5의 원자성 요구를 유지할 수 있는 해결책을 별도로 설계.

이 순서는 "원인 증거를 먼저 확보하고, 복구는 격리된 후보에서 수행하며, unrelated recorder 문제를 Git index 계획과 분리"한다는 원칙을 따른다.

---

## 5. Validation 1~8 재검토
### 1단계: 거버넌스 준수성
- 긍정: Plan/Task 체계와 Staging 선행 구현 원칙은 유지됐다.
- 문제: `RULE-6.1.5` / `RULE-6.1.6`가 요구하는 원자적 교체를 4단계 직접쓰기 fallback이 완화한다. 하위 구현 계획이 상위 Rule을 완화할 수 없으므로 충돌이다.
- 문제: Plan/Task 공통 `work_id`가 없고 Task의 결과 Report 번호가 이미 사용 중이다.
- **판정: 실패 — 문서 및 4단계 수정 후 재검토 필요.**

### 2단계: 사용자 의도 달성도
- 재발 방지뿐 아니라 원인 특정, 증거 보존, 안전 복구까지 포함하여 사용자 목적에 더 가까워졌다.
- 사용자가 확인한 Antigravity/Gemini 동시 작업 조건도 현재 계획의 사실/미확정 구분과 양립한다.
- **판정: 통과.**

### 3단계: 정적 논리 호환성
- `--no-optional-locks` 방향은 Git 공식 동작과 일치한다.
- 그러나 현재 governance recorder/tool에는 해당 Git probe가 없어 적용 대상이 불명확하다.
- 기본 index 직접 `read-tree`보다 alternate index 후보 생성 방식이 실패 격리에 유리하다.
- 직접 write fallback은 원자성 상실 및 동시 쓰기 위험이 있다.
- **판정: 조건부 실패 — 구현 위치와 복구 알고리즘 수정 필요.**

### 4단계: 운영 병합 영향도
- Git index guard 자체를 Staging에서 검증하는 방향은 적절하다.
- 공통 `writeFileAtomic()`을 변경하면 Chat 본문뿐 아니라 recorder state까지 영향을 받으므로 예상보다 blast radius가 크다.
- Git index 문제와 recorder EPERM 문제를 한 변경 범위로 병합하면 장애 원인과 rollback 단위가 결합된다.
- **판정: 4단계 분리 조건으로 통과 가능.**
### 5단계: 보안 및 예외 엣지 케이스
- Defender 제외를 보류한 것은 적절하다.
- 진행 중인 merge/rebase/cherry-pick/revert 중단 조건도 적절하다.
- 추가로 detached/unborn HEAD, sparse checkout/index, submodule/worktree 여부를 구현 단계에서 검사해야 한다.
- 직접 write fallback은 부분 기록·state 손상이라는 새로운 무결성 위험을 만든다.
- **판정: 4단계 제거 및 엣지 케이스 보강 조건부 통과.**

### 6단계: 롤백 가능성
- 손상 index 백업과 incident 기록 방향은 개선됐다.
- 그러나 0바이트 백업은 기존 staged 정보를 복원하는 수단이 아니며 단지 손상 증거 보존이다.
- alternate index 후보 방식은 실패 시 기본 index에 손대지 않아 rollback 경계를 더 명확하게 만든다.
- `writeFileAtomic` 공통 fallback은 rollback 범위를 Chat/state 전체로 넓히므로 부적절하다.
- **판정: index 부분 조건부 통과, recorder fallback 실패.**

### 7단계: 휴먼 에러 방지
- 자동 복구를 조용히 숨기지 않고 incident와 staged 손실 가능성을 보고하도록 한 점은 적절하다.
- 복구 후보 검증 실패 또는 Windows 교체 실패 시 사용자에게 명확히 중단 상태를 보여야 한다.
- **판정: 통과 가능.**

### 8단계: AI 메타 거버넌스
- 1차 계획의 99%/100% 단정, Defender 추정, 성능 설정 오분류를 수정한 것은 긍정적이다.
- 그러나 2차 계획의 Validation 표는 실제 Rule 충돌과 적용 대상 부재를 발견하지 못한 채 전 단계 `통과`로 표시했다.
- 특히 "Chat 파일이 에디터에 열려 있을 때 EPERM"을 확인된 사실처럼 기술한 부분은 저수준 handle 증거가 확보되기 전에는 가설로 낮춰야 한다.
- **판정: 조건부 실패 — 자체 검증 판정을 사실에 맞게 수정 필요.**

---

## 6. 최종 결론

**2차 개정안 판정: 핵심 방향은 수용하되 현재 구현 승인 불가. 3차 수정 후 재검토한다.**
구현 전 필수 수정사항은 다음 네 가지다.

1. `GIT_OPTIONAL_LOCKS=0` 적용 대상을 실제 Antigravity/VS Code read-only Git probe로 재정의하고 제어 가능성을 검증할 것.
2. Self-Healing은 alternate index에 후보를 생성·검증한 뒤 교체하도록 변경하고, 저수준 진단 증거 확보를 복구보다 앞세울 것.
3. `writeFileAtomic`의 직접 `writeFile` fallback을 005 계획에서 제거하고 recorder EPERM 문제를 별도 Plan으로 분리할 것. 원인인 handle owner를 먼저 특정할 것.
4. Plan 005 / Task 007에 공통 `work_id`를 부여하고 이미 점유된 Report 013 경로를 수정할 것.

이 네 항목이 반영되면 005 계획의 Git index 관련 핵심 부분은 Staging 구현·검증 단계로 넘어갈 수 있다.

---

## 7. 외부 기술 근거

- Git `git-status` BACKGROUND REFRESH: https://git-scm.com/docs/git-status
  - background `git status`의 optional index refresh와 lock contention, `--no-optional-locks` 권고.
- Git main documentation: https://git-scm.com/docs/git
  - `GIT_OPTIONAL_LOCKS=0`의 의미: optional lock을 요구하는 부수 작업 억제.
- Git `git-read-tree`: https://git-scm.com/docs/git-read-tree
  - tree를 index에 읽고 working tree를 기본적으로 갱신하지 않는 동작 및 temporary index 관련 옵션 근거.
- Git `GIT_INDEX_FILE`: https://git-scm.com/docs/git
  - 기본 `.git/index` 대신 alternate index를 지정할 수 있는 공식 환경 변수.
- VS Code Agent Host issue #329893: https://github.com/microsoft/vscode/issues/329893
  - Agent Host read-only Git probe의 optional lock race와 호출별 `GIT_OPTIONAL_LOCKS=0` 적용 제안 참고 사례.
- Node.js File System API: https://nodejs.org/api/fs.html
  - `fs.rename`과 Windows `EPERM`/`EBUSY` 계열 파일시스템 오류 처리 관련 API 근거. 직접 write가 원자적 rename의 동등 대체라는 보장은 없음.

---

## 8. 검토 시점 상태

- `governance-tool validate`: 본 검토 시작 시 **PASS** — governance v1.3.0, 노드 41/41, 오류 0, 경고 0.
- `.agent-governance` 정적 검색: 현재 governance-tool / conversation-recorder 내부에서 `git status`, `git diff` 또는 `GIT_OPTIONAL_LOCKS` 사용 지점이 발견되지 않음.
- 현재 `.git/index`: **0 bytes** 상태가 계속 유지됨. 본 검토에서는 사용자의 Git 복구 승인이 없으므로 복구·삭제·교체하지 않음.
- `.git/index.lock`: 검토 중 조회 시 존재하지 않음.
- 현재 ChatGPT 세션 대화 기록은 사용자 명시 승인에 따라 예외 처리했으며 Chat에 수동 기록하지 않음.
- Git commit/push, Plan 005 수정, Task 007 수정, Rule/노드 수정, recorder 코드 수정은 수행하지 않음.
