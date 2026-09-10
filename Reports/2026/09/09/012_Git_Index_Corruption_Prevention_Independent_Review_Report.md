---
artifact_id: REPORT-20260909-012
work_id: WORK-20260909-GIT-INDEX-REVIEW
created_at: 2026-09-09T15:33:55.510+09:00
related_artifacts:
  - ../../../../Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md
  - ../../../../Tasks/2026/09/09/008_Git_Index_Corruption_Prevention_Independent_Review_Task.md
---
# [독립 검토 보고서] Git 인덱스 0바이트 손상 재발 방지 계획 기술 검토

- 작성일: 2026-09-09
- work_id: `WORK-20260909-GIT-INDEX-REVIEW`
- 상태: **검토 완료 — 기존 계획 수정 후 재검토 필요**
- 관련 계획: `Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md`
- 관련 Task: `Tasks/2026/09/09/008_Git_Index_Corruption_Prevention_Independent_Review_Task.md`
- 기존 구현 Task: `Tasks/2026/09/09/007_Git_Index_Corruption_Prevention_Task.md`
- 검토 작업자: ChatGPT GPT-5.6 Sol

---

## 1. 종합 결론

기존 `005_Git_Index_Corruption_Prevention_Plan.md`는 `.git/index` 복구 절차와 반복 발생을 문제로 인식한 점은 타당하나, 근본 원인과 예방책의 효과를 현재 증거보다 강하게 단정하고 있다.

**판정: 현재 계획 그대로 구현하지 말고 수정 후 재검토한다.**

핵심 이유는 다음과 같다.

1. 사용자 반복 관찰에 따르면 `.git/index` 0바이트화는 **VS Code의 Antigravity 확장에서 Gemini가 실제 파일 변경을 수행한 경우에만 발생**한다. 따라서 발생 트리거 범위는 Antigravity/Gemini 파일 변경 경로로 상당히 좁혀졌다.
2. 다만 Antigravity 내부의 어떤 프로세스가 어떤 파일 I/O 동작으로 `.git/index`를 0바이트로 만드는지까지는 아직 포착되지 않았다. "트리거가 특정됨"과 "저수준 가해 프로세스가 특정됨"은 구분해야 한다.
3. 기존 계획의 `core.fscache`, `core.preloadindex`, `core.trustctime`, `core.untrackedCache` 설정은 주로 성능·stat 캐시 최적화 항목이며 index corruption을 직접 방지하는 기능으로 볼 근거가 부족하다.
4. Git 공식 문서는 background `git status`가 index refresh 결과를 기록하면서 lock contention을 만들 수 있음을 명시하며, background/read-only probe에는 `git --no-optional-locks status` 사용을 권고한다.
5. 자동 Self-Healing은 필요하지만, `git reset`을 무조건 실행하는 형태는 staged 상태와 진행 중인 merge/rebase 등의 상태를 고려하지 못한다.

---

## 2. 확인된 사실과 신뢰도 구분

### 2.1 사용자 재현 관찰 — 높은 신뢰도

사용자가 반복적으로 확인한 조건은 다음과 같다.

- 일반 작업에서는 동일 현상이 관찰되지 않음.
- **Antigravity 확장의 Gemini가 프로젝트 파일에 실제 변경을 발생시키는 작업을 수행한 경우에만** `.git/index`가 0바이트가 되는 현상이 반복됨.
- 따라서 재발 방지 조사의 1차 범위는 일반적인 Windows/NTFS 전체가 아니라 **Antigravity/Gemini의 파일 변경 전후 Git·IDE·에이전트 동작**으로 한정하는 것이 합리적이다.

이 정보는 사용자에 의해 관찰된 재현 조건이며 본 검토자가 별도 자동 재현 시험으로 검증한 사실은 아니다. 보고서에서는 이를 숨은 시스템콜 수준의 원인 확정과 구분한다.

### 2.2 현재 로컬 환경에서 직접 확인한 사실

- Git: `git version 2.55.0.windows.3`
- 시스템 Git 설정에 이미 `core.fscache=true`가 존재함.
- 현재 `.vscode/settings.json`의 watcher 제외는 `**/Chat/.state/**`만 등록되어 있음.
- 기존 계획서가 추가하려는 `core.fscache=true`는 현재 환경에서는 중복 설정이다.

### 2.3 아직 확정되지 않은 항목

- Antigravity 내부에서 `.git/index`를 실제 truncate/replace하는 정확한 PID 및 실행 파일.
- Windows Defender(`MsMpEng.exe`)가 손상 순간에 `.git/index` 또는 `.git/index.lock`을 점유했는지 여부.
- 일반 VS Code Git extension 자체가 0바이트화를 발생시키는지 여부.

---

## 3. 기존 원인 분석의 문제점

### 3.1 Git index 교체 메커니즘에 대한 과도한 단정

Git의 lockfile API는 index 갱신 시 `$GIT_DIR/index.lock`을 먼저 생성하고 새 내용을 쓴 뒤 최종 목적지인 `$GIT_DIR/index`로 rename하는 구조를 사용한다. Git 문서는 파일시스템이 atomic rename을 제공한다는 전제에서 reader가 old/new 중 하나를 보도록 설계된다고 설명한다.

따라서 기존 Gemini 설명의 "Git이 `.git/index`를 직접 쓰는 찰나에 다른 `git status`가 0바이트 파일을 읽어 손상된다"는 서술은 Git의 정상적인 lockfile 설계와 정확히 일치하지 않는다.

Race Condition 또는 외부 프로세스 간섭 가능성 자체는 배제할 수 없지만, **정상 Git index 갱신만으로 기존 index가 0바이트가 되는 메커니즘을 확정했다고 볼 수 없다.**

### 3.2 background `git status` 경합 가능성은 실제 근거가 있음

Git 공식 `git-status` 문서는 `git status`가 기본적으로 index를 refresh하고 cached stat 정보를 다시 index에 기록할 수 있다고 명시한다. background 실행 시 이 쓰기 과정의 lock이 다른 동시 Git 프로세스와 충돌할 수 있으므로 다음 사용을 권고한다.

```bash
git --no-optional-locks status
```

동일 목적의 환경 변수는 다음과 같다.

```text
GIT_OPTIONAL_LOCKS=0
```

따라서 Antigravity/Gemini 또는 프로젝트의 AI·거버넌스 도구가 수행하는 **읽기 전용 `git status` / `git diff` probe부터 optional lock을 제거하는 방안**이 기존 계획의 Git config 튜닝보다 우선 검토되어야 한다.

---

## 4. 기존 3중 방어 체계 평가

### 4.1 Git config 4종 — 재분류 필요

| 설정 | 기존 계획의 취급 | 독립 검토 판정 |
| :--- | :--- | :--- |
| `core.fscache=true` | index 경합 완화 | 현재 시스템 설정에 이미 활성화. 성능 최적화 성격이며 corruption 직접 방지 근거 부족 |
| `core.preloadindex=true` | index lock 점유 시간 단축 | 파일 stat 비교의 병렬화·성능 항목. 손상 방지책으로 단정 부적절 |
| `core.trustctime=false` | index 강제 재작성 억제 | ctime 신뢰 정책에 관한 설정. 현재 문제의 직접 대응 근거 없음 |
| `core.untrackedCache=true` | 미추적 파일 I/O 완화 | `git status` 성능 향상용 캐시. integrity 방지와 분리하여 취급해야 함 |

결론적으로 이 항목들은 필요 시 별도의 **Git 성능 최적화** 작업으로 다룰 수 있으나, `.git/index` 0바이트 재발 방지의 핵심 방어선으로 정의하면 안 된다.

### 4.2 VS Code `files.watcherExclude` — 보조책

`.git/index*` 등을 `files.watcherExclude`에 넣는 것은 파일 watcher 이벤트 부하를 줄이는 보조책일 수 있다. 그러나 이것이 Source Control 또는 Agent Host의 Git 명령 실행 자체를 중단한다고 보장할 수 없다.

따라서 "watcherExclude를 등록하면 IDE가 index를 동시 조회하지 않는다"는 인과관계는 증명되지 않았다. 적용 여부는 실제 Antigravity/VS Code 프로세스 관측 결과와 함께 판단해야 한다.

### 4.3 Defender 전체 프로젝트 제외 — 현재 보류

현재 `MsMpEng.exe`가 손상 순간의 원인이라는 직접 증거가 없다. Microsoft도 Defender 제외는 문제 진단과 대안을 먼저 검토한 뒤 필요한 경우 제한적으로 사용하도록 안내한다.

프로젝트 전체 Defender 제외는 보안 가시성을 낮추므로 **Process Monitor 등에서 Defender의 실제 개입이 확인되기 전에는 적용하지 않는다.**

---

## 5. Self-Healing 설계 평가

손상 index를 자동 감지하고 백업한 뒤 복구하는 방향 자체는 적절하다. 그러나 기존 계획의 `git reset` 자동 실행은 다음 상태를 명시적으로 구분하지 않는다.

- staged 변경이 존재했는지 여부
- merge 진행 중인지 여부
- rebase 진행 중인지 여부
- cherry-pick / revert 진행 중인지 여부
- unmerged index가 존재했는지 여부

`git reset`의 기본 mixed 동작은 index를 재설정하므로, 이를 "데이터 유실 0%"라고 일반화해서는 안 된다. 작업 트리 파일을 보존하더라도 staged 상태는 별도 정보이다.

정상적인 단일 HEAD 상태이고 index가 이미 손상되어 재구성이 필요한 경우에는 다음 원칙을 권장한다.

1. 손상된 `.git/index`와 존재하는 `.git/index.lock`의 메타데이터·시각을 먼저 기록한다.
2. 손상 index를 `index.corrupt.<timestamp>.bak`으로 보존한다.
3. merge/rebase/cherry-pick/revert 등 진행 상태가 없는지 검사한다.
4. 안전 조건이 만족되면 `git read-tree HEAD`로 HEAD tree 정보를 index에 다시 읽는다.
5. `git status`로 working tree와 재생성 index의 관계를 확인한다.
6. `git fsck --full --no-dangling`으로 object/reference 측 검사를 수행한다.

Git 공식 문서상 `git read-tree`는 tree 정보를 index에 읽되 `-u`를 사용하지 않는 한 working-tree 파일을 실제로 갱신하지 않는다.

또한 `git fsck`의 성공은 "Git object database의 connectivity와 validity 검사에서 오류가 발견되지 않음"으로 표현해야 하며 저장소의 모든 의미론적 상태가 100% 무결하다고 확대 해석하지 않는다.

---

## 6. 수정 권고 재발 방지 순서

### 1순위 — Antigravity/Gemini Git probe 감사 및 optional lock 제거

Antigravity/Gemini가 파일 변경 전후 실행하는 `git status`, 읽기 전용 `git diff` 등 Git probe를 우선 추적한다. 읽기 전용 조회에는 가능한 범위에서 `GIT_OPTIONAL_LOCKS=0` 또는 `git --no-optional-locks`를 적용하여 불필요한 index refresh write와 lock 획득을 방지한다.

2026-08 공개된 VS Code Agent Host 이슈에서도 read-only `git status`/`git diff` probe에 `GIT_OPTIONAL_LOCKS=0`을 적용하여 index lock race를 줄이는 방향이 제기되어 있다. 이 이슈는 본 저장소 손상의 직접 원인 증명은 아니지만 동일 계열 에이전트 Git probe의 경쟁 가능성을 뒷받침하는 참고 사례이다.

### 2순위 — 실제 0바이트 생성 프로세스 포착

사용자의 재현 조건이 명확하므로 다음 Antigravity/Gemini 파일 변경 작업 시 Process Monitor 등으로 다음 경로를 집중 추적한다.

```text
D:\Project\Mini-Server-Web-EqMgmt\.git\index
D:\Project\Mini-Server-Web-EqMgmt\.git\index.lock
```

관찰 대상은 Process Name/PID, CreateFile, WriteFile, SetEndOfFile, rename/replace 계열 동작, Result 및 발생 시각이다. 이 단계가 성공하면 "Antigravity/Gemini가 트리거"에서 "정확한 내부 프로세스와 파일 연산"까지 원인을 좁힐 수 있다.

### 3순위 — 진단 우선 Self-Healing

0바이트 감지 즉시 무조건 복구하지 않고 먼저 가해 프로세스 식별에 필요한 증거를 보존한 뒤 안전 조건에서 복구한다. 복구 발생 사실은 숨기지 않고 incident 로그와 사용자 보고 대상으로 남긴다.

### 4순위 — 성능 최적화는 별도 취급

`fscache`, `preloadindex`, `untrackedCache` 등은 필요하면 성능 측정 후 별도 최적화로 적용한다. `trustctime=false`는 현재 문제에 대한 직접 근거가 없어 기본 방안에서 제외한다.

---

## 7. 본 검토 중 발견된 거버넌스 preflight 예외 구조 문제

이번 보고서 발급 전 `AGENTS.md`가 요구하는 다음 preflight를 실행했다.

```powershell
node .agent-governance/tooling/conversation-recorder.mjs ensure --platform all --workspace . --json
```

동일한 오류가 반복 발생했다.

```text
EPERM: operation not permitted, rename '...\Chat\2026\09\09.md.tmp-...' -> '...\Chat\2026\09\09.md'
```

recorder watcher PID를 종료한 뒤 재실행해도 같은 `EPERM`이 발생하여 watcher 자체가 대상 파일을 잠근 원인이라는 가설은 배제되었다.

`governance-tool validate`는 governance v1.3.0, 41개 노드, 오류 0, 경고 0으로 통과했으므로 Rule↔노드 동기화 손상이 아니라 **정상 규칙 사이의 복구 경로 표현 부족**이 문제이다.

### 관련 Rule 및 노드

- `RULE-6.2.4` / `records.conversation-automation`: 일반 작업 전에 `ensure` 강제.
- `RULE-6.2.9` / `records.conversation-storage`, `records.conversation-automation`: preflight 재시도 후에도 실패하면 일반 작업 시작 금지.
- `RULE-6.1.6` / `records.conversation-storage`: 전용 writer 밖 수동 복구는 플랫폼 capability와 `tools.conversation-exception` 절차를 따름.
- `RULE-8.0` / `tools.conversation-exception`: Chat 기록 복구에는 일반 터미널 쓰기 규칙보다 제6조를 우선 적용.
- `RULE-9.3` 대응 `core.precedence`: 규칙 충돌 시 실행 중지 후 사용자 결정을 요구.

### 7.1 문제의 본질

현재 Rule은 "preflight 실패 시 일반 작업 금지"와 "Chat 수동 복구 예외"를 각각 정의하지만, **preflight 자체가 Chat 저장 실패 때문에 막힌 경우 사용자가 복구를 명시 승인한 뒤 어떤 제한된 행위를 허용하고 언제 일반 작업으로 복귀하는지**를 연결하는 조항이 없다.

이 때문에 원칙대로만 적용하면 recorder 장애를 분석·수정하거나 그 장애에 대한 보고서를 남기는 작업 자체가 preflight에 의해 차단되는 순환 의존성이 생길 수 있다.

이번 작업에서는 사용자가 거버넌스 작성자임을 밝히고, 해당 장애 상황에서 자신의 명시적 승인이 우선된다는 해석을 직접 제공했으며, `Reports`에 본 검토 결과를 기록하도록 명시적으로 지시했다. 따라서 **그 승인 범위를 보고서·Task 작성 및 검증에 한정하여 적용**하고 운영 코드나 Rule 자체는 변경하지 않았다.

### 7.2 Rule 개선 권고

향후에는 `RULE-6.2.9` 또는 인접 조항에 다음 취지의 복구 예외를 명문화하는 것을 권고한다.

1. recorder preflight 실패 원인이 Chat 저장/잠금/원자적 교체 장애인 경우 일반 작업은 계속 차단한다.
2. 단, 사용자 명시 승인 또는 사전에 정의된 안전한 복구 capability가 있는 경우 **recorder 진단·백업·복구 및 그 복구 기록에 필요한 최소 작업**만 허용한다.
3. 복구 작업 후 `ensure`를 다시 실행하고 성공하기 전에는 원래 요청의 일반 구현 작업으로 복귀하지 않는다.
4. Rule/노드 자체의 결함이 원인인 경우 `review-rule` / `edit-rule` 전용 복구 경로를 사용할 수 있도록 별도 bootstrap 예외를 정의한다.
5. 이 예외는 기능 구현·운영 병합·임의 파일 변경 권한으로 확대되지 않는다.

수정 시 연동 대상은 최소 `records.conversation-automation`, `records.conversation-storage`, `tools.conversation-exception`, 필요 시 `core.precedence`와 `human-rule-map.yaml`이다.

---

## 8. Validation 1~8 독립 검토

### 1단계: 거버넌스 준수성
- 기존 계획은 Plan/Task 구조를 따르지만 원인 확정 근거가 부족한 상태에서 구현 승인으로 넘어갈 위험이 있다.
- 본 독립 검토는 별도 Task를 먼저 발급하고 review/create-file 라우팅 및 Validation 체인을 적용했다.
- recorder preflight 실패 예외 경로가 불완전한 거버넌스 결함을 추가 발견했다.
- **판정: 조건부 통과 — Rule 개선 필요 사항 존재.**

### 2단계: 사용자 의도 달성도
- 사용자가 파악한 재현 조건인 "Antigravity/Gemini의 파일 변경 시에만 발생"을 핵심 사실로 반영했다.
- 목적을 단순 복구가 아니라 재발 방지와 잘못된 기존 계획 교정으로 유지했다.
- **판정: 통과.**

### 3단계: 정적 논리 호환성
- 기존 계획의 Git config 4종은 integrity 대응과 performance tuning을 혼합하고 있다.
- watcherExclude만으로 Git Source Control/Agent Host probe가 중단된다고 보장할 수 없다.
- unconditional `git reset` self-heal은 staged/merge 상태를 잃거나 왜곡할 수 있다.
- `--no-optional-locks` 적용과 상태 확인 후 `git read-tree HEAD` 복구가 더 논리적이다.
- **판정: 기존 계획 부적합, 수정 필요.**

### 4단계: 운영 병합 영향도
- 현재 계획을 그대로 적용하면 효과가 불명확한 설정이 운영 저장소에 추가되고 원인이 은폐될 수 있다.
- 본 검토에서는 운영 코드·Git 설정·Rule을 변경하지 않았다.
- **판정: 구현 보류가 안전.**

### 5단계: 보안 및 예외 엣지 케이스
- 근거 없는 프로젝트 전체 Defender 제외는 보안 탐지 범위를 줄인다.
- 자동 복구가 merge/rebase/cherry-pick 상태를 무시하면 index 상태를 잘못 재구성할 수 있다.
- incident 증거를 복구 전에 보존하지 않으면 실제 가해 프로세스 특정 기회를 잃는다.
- **판정: 기존 계획 보강 필요.**

### 6단계: 롤백 가능성
- Git config 및 `.vscode/settings.json` 변경 자체는 되돌리기 쉽다.
- 그러나 0바이트 index 발생 전 staged 상태는 HEAD 재구성만으로 복원되지 않을 수 있으므로 "데이터 유실 0%"라는 표현은 금지해야 한다.
- 손상 index 백업, 진행 상태 검사, 복구 후 status/fsck 검증을 필수화해야 한다.
- **판정: 조건부 통과.**

### 7단계: 휴먼 에러 방지
- 완전 자동 self-heal이 오류를 조용히 숨기면 사용자는 반복 원인을 인지하지 못할 수 있다.
- 자동 복구 시 incident 번호, 발생 시각, index 크기, 복구 방식, staged 상태 손실 가능성을 명시적으로 기록해야 한다.
- **판정: 사용자 가시성 보강 필요.**

### 8단계: AI 메타 거버넌스
- 기존 Gemini 답변은 IDE/NTFS/Defender 경합을 증거 수준보다 강하게 "근본 원인"으로 확정하고 99%/100% 방어 표현을 사용했다.
- 2026-09-09 12:10~12:12의 Codex 분석은 "경합 정황은 있으나 index를 실제 절단한 프로세스는 미확정"으로 구분하여 증거 수준에 더 부합했다.
- 현재 사용자 관찰로 Antigravity/Gemini 파일 변경 경로가 트리거로 좁혀졌으므로 이후 분석은 그 조건을 중심으로 갱신해야 한다.
- **판정: 기존 계획의 표현과 근거 수준 수정 필요.**

---

## 9. 최종 권고 및 작업 상태

1. `Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md`는 **수정 전 구현 승인 대상으로 사용하지 않는다.**
2. `Tasks/2026/09/09/007_Git_Index_Corruption_Prevention_Task.md`의 기존 config/watcher/self-heal 구현 항목은 계획 수정 전까지 보류한다.
3. 수정 계획의 우선순위는 `Antigravity/Gemini read-only Git probe 감사 → GIT_OPTIONAL_LOCKS=0 적용 검토 → 실제 index/index.lock writer 포착 → 증거 보존형 Self-Healing` 순으로 재편한다.
4. Defender 제외와 일반적인 Git 성능 config는 실제 측정·증거가 있을 때 별도 항목으로 검토한다.
5. recorder preflight 장애 시 복구 작업마저 차단되는 순환 의존성을 해소하도록 Rule 6-2 계열의 복구 예외를 별도 계획으로 검토한다.

본 보고서는 **검토와 문서화만 수행**했으며 Git config, `.vscode/settings.json`, conversation-recorder 코드, Rule.md 및 거버넌스 노드는 변경하지 않았다.

---

## 10. 외부 기술 근거

- Git `git-status` BACKGROUND REFRESH: https://git-scm.com/docs/git-status
  - background `git status`의 index refresh write와 lock contention, `--no-optional-locks` 권고 근거.
- Git lockfile API: https://git-scm.com/docs/api-lockfile/2.2.3.html
  - `index.lock` 작성 후 최종 `index`로 rename하는 상호배제·atomic update 설계 근거.
- Git `git-read-tree`: https://git-scm.com/docs/git-read-tree
  - tree 정보를 index에 읽되 기본적으로 working-tree 파일을 갱신하지 않는 복구 특성 근거.
- Git `git-fsck`: https://git-scm.com/docs/git-fsck
  - object database의 connectivity와 validity 검사 범위 근거.
- Microsoft Defender exclusions overview: https://learn.microsoft.com/en-us/defender-endpoint/defender-endpoint-exclusions-overview
  - 제외 설정 전에 진단 및 대안을 먼저 검토해야 한다는 근거.
- VS Code Agent Host issue #329893: https://github.com/microsoft/vscode/issues/329893
  - read-only agent Git probe에 `GIT_OPTIONAL_LOCKS=0` 적용 필요성이 제기된 참고 사례. 본 저장소 원인의 직접 증명 자료로 사용하지 않음.

---

## 11. 검증 후 상태

- `governance-tool validate`: **PASS** — governance v1.3.0, manifest 노드 41개, human map 노드 41개, 오류 0, 경고 0.
- `git diff --check`: 공백 오류 없음. 기존 작업 트리의 LF→CRLF 경고만 출력됨.
- 검증 시 `.git/index` 크기: **29,936 bytes**, 정상적인 비영(非零) 상태.
- Git 상태 조회는 본 보고서 권고와 동일하게 `GIT_OPTIONAL_LOCKS=0` 환경에서 수행함.
- preflight 장애 분석을 위해 기존 conversation recorder watcher PID `33568`을 종료했으나, 종료 후에도 Chat atomic rename `EPERM`이 동일하게 재현되어 watcher 자체 원인 가설은 배제됨.
- 조사 종료 시 conversation recorder watcher를 다시 시작했으며 최종 상태는 **running=true, PID 17828, interval=1500ms**로 확인함.
- 본 검토 과정에서 Git commit/push, 기존 Plan 수정, Rule/노드 수정, Git config 변경, Defender 제외 적용은 수행하지 않음.
- watcher 복구 후 최종 `ensure` 재시도에서도 동일한 `Chat\2026\09\09.md` atomic rename `EPERM`이 재현됨. 따라서 preflight 장애는 **현재도 미해결**이며 보고서 작성과 별개의 후속 거버넌스/recorder 복구 과제로 남김.
