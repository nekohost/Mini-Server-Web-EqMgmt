---
artifact_id: REPORT-20260910-003
work_id: WORK-20260909-GIT-INDEX-PREVENTION
created_at: 2026-09-10T10:54:00.915+09:00
related_artifacts:
  - ../../../../Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md
  - ../../../../Tasks/2026/09/09/007_Git_Index_Corruption_Prevention_Task.md
---
# [최종 증거·인계 보고서] Git 인덱스 ProcMon 실증 및 Codex 중단 작업 복원

- 작성일: 2026-09-10
- `work_id`: `WORK-20260909-GIT-INDEX-PREVENTION`
- 상태: **ProcMon 실증 완료 — 위험한 직접 index 재쓰기 경로 확정, 0바이트가 되는 정확한 실패 조건은 미재현**
- 관련 계획: `Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md`
- 관련 Task: `Tasks/2026/09/09/007_Git_Index_Corruption_Prevention_Task.md`
- 선행 보고서: `Reports/2026/09/10/002_Git_Index_Corruption_Prevention_Implementation_and_ProcMon_Approval_Report.md`

---

## 1. 복원에 사용한 근거

이번 상태 복원은 다음 원본을 서로 대조했다.

1. `Chat/2026/09/09.md` 및 `Chat/2026/09/10.md`의 사용자·Codex 가시 대화.
2. 최신 Codex 세션 `C:/Users/dooly/.codex/sessions/2026/09/09/rollout-2026-09-09T19-58-17-01a085d1-89fd-7d02-84b5-090d99671fa4.jsonl`.
3. Plan 005, Task 007, Reports 012/014/001/002와 현재 저장소 상태.
4. Process Monitor 산출물과 마지막 Codex 도구 결과.

Codex 세션에는 `reasoning` 레코드가 존재하지만 `summary`는 비어 있고 본문은 `encrypted_content`로 저장되어 있다. 따라서 숨은 추론 원문을 복호화하거나 추정하지 않고, 가시 메시지·도구 호출·도구 결과·파일 상태만으로 진행도를 판정했다.

최신 Codex turn은 2026-09-10 09:24:12 KST에 `cyber_policy` 오류로 종료되었으며 `last_agent_message` 없이 중단되었다. 이는 프로젝트 Task의 정상 완료 이벤트가 아니다.
## 2. Codex가 실제로 완료한 작업

저장소 내부 예방 조치는 이미 완료되어 있었다.

- `.vscode/settings.json`: `antigravity.enableInlineDiff=false` 적용.
- `.agent-governance/tooling/git-readonly.mjs`와 테스트 추가.
- Codex/Antigravity/Claude capability의 read-only Git probe 정책 반영.
- `artifact-manager.mjs`의 read-only Git 호출에 `GIT_OPTIONAL_LOCKS=0` 적용.
- `.gitattributes`로 핵심 거버넌스 파일의 LF 고정.
- 당시 전체 테스트 44/44, governance 41/41, recorder 누락 0, `git fsck` 정상 확인.
- 실제 작업 저장소 `.git/index`는 작업 전후 크기·mtime·SHA-256이 불변임을 확인.

사용자는 08:30 KST에 Process Monitor 반입부터 목표 달성까지 진행을 승인했다. 이후 Codex는 Microsoft 공식 Process Monitor를 반입하고 서명 검증, 일회용 저장소, 격리된 portable VS Code, 복사된 Antigravity 확장을 사용해 실제 작업 저장소와 사용자 VS Code를 건드리지 않는 재현 환경을 구성했다.

여러 초기 재현 실패 뒤 backend·인증 경로를 제거하고 복사된 Antigravity의 `AgentEditManager`에 diff를 직접 전달하여 실제 Inline Diff renderer의 Git refresh 경로를 실행하는 데 성공했다.

## 3. Process Monitor 최종 증거

성공 캡처에서 VS Code extension-host `Code.exe` PID `29080`이 `ReproRepo7/.git/index`에 전체 265바이트를 직접 `WriteFile`했다. 같은 전체 쓰기가 네 차례 관찰되었으며 두 재실행 간격은 각각 약 167ms와 162ms로, Antigravity 코드의 즉시 실행 후 약 150ms 재실행 구조와 일치한다.

따라서 **Antigravity Inline Diff 경로가 Git의 `index.lock` 원자적 교체와 별개로 기존 `.git/index`를 직접 다시 쓰는 위험 경로라는 점은 실증 완료**로 판정한다.

다만 정상 재현에서는 결과 index가 0바이트가 되지 않았다. 그러므로 과거 5건의 실제 0바이트 사건까지 동일 코드가 직접 발생시켰다고 확정하기보다는, **손상을 유발할 수 있는 직접 재쓰기 경로는 확정했지만 0바이트가 되는 정확한 Windows/동시성 실패 조건은 아직 미재현**으로 유지한다.
## 4. 고정된 증거와 안전 상태

Codex가 중단 직전 고정한 값은 다음과 같다.

- PML: `Antigravity-index-capture5.pml`, 271,400,775 bytes, SHA-256 `66F2B68E2AC8ED0063214C37D4BEA632466B925F7984FD2B4F5AACE34C48A74A`.
- stack XML: `Antigravity-index-capture5-stacks.xml`, 3,448,663,641 bytes, SHA-256 `C79C8CED53E323ED74A88E5FCBAF4F656B56ED9CC4CF2130A41755B01FC46472`.
- 재현 index: 265 bytes, SHA-256 `179DDC534AD52600751D76B56C7714ABE722DF48027C48AA396794FC1CCCDF20`, 마지막 수정 2026-09-10 09:13:48.983776 KST.
- 실제 저장소 index: 32,063 bytes, SHA-256 `4C33BF3C6D5D6BBFBCF80DB1F6D954556FD899ACE6967B76D81DF1C9B139D5E8`, 마지막 수정 2026-09-09 20:03:28.980592 KST.
- 실제 `agy.exe`: SHA-256 `E6EBE1D3B63AFD6B39B236D2F2667FB14355B1BD3BC17B44126A188D12E42F61`.
- 격리 portable VS Code 프로세스는 0개로 정리됐고 `.gemini/bin`의 예상 밖 `agy.tmp.*` 파일도 0개였다.

대용량 PML/XML은 저장소에 복사하지 않고 승인된 임시 증거 경로 `C:/Users/dooly/AppData/Local/Temp/MiniServer-EqMgmt-ProcMon-20260910`에 유지한다.

## 5. 아직 못다한 부분

Codex가 실제로 못 끝낸 것은 **실증 자체가 아니라 문서와 상태의 종결 처리**였다. 중단 당시 Task 007은 여전히 “ProcMon 승인 대기”로 적혀 있었고, 호출 스택 캡처와 최종 보고서 두 항목이 미체크 상태였다.

이번 보고서로 해당 불일치를 복구한다. Task 007은 ProcMon 캡처와 최종 증거 보고서를 완료로 갱신하되, “0바이트가 되는 정확한 실패 조건”은 별도 미해결 연구 항목으로 명확히 남긴다.

## 6. 거버넌스가 원인인지에 대한 판정

Git index 직접 재쓰기의 기술적 원인은 프로젝트 거버넌스가 아니다. ProcMon은 격리된 실제 Antigravity Inline Diff renderer가 extension-host에서 index를 직접 다시 쓰는 경로를 포착했다. 현재 예방 설정 `antigravity.enableInlineDiff=false`는 이 위험 경로를 워크스페이스에서 차단하는 적절한 1차 조치다.
반면 거버넌스에는 **작업 진행을 불필요하게 막을 수 있는 별도 결함**이 확인된다. `RULE-6.2.9`, `records.conversation-automation`, `AGENTS.md`, `GEMINI.md`는 recorder preflight가 재시도 후 실패하면 일반 작업을 모두 중단하도록 한다. 2026-09-09 실제 `Chat` atomic rename `EPERM` 사고에서는 기록기 자체를 진단·복구하는 작업조차 이 preflight에 다시 막히는 순환 의존성이 발생했다.

이 문제는 Antigravity에 특히 불리할 수 있다. Antigravity는 별도의 Windows 검색 parser 결함, persistent command grant parser 제약, conversation storage API의 누락/오기입 위험을 이미 capability profile에 가지고 있어 복구 경로가 필요한 빈도가 다른 플랫폼보다 높다. 해당 플랫폼 차이는 현재 `gemini-antigravity.yaml`에 상당 부분 반영되어 있으므로 이를 제거할 이유는 없다.

따라서 Rule을 느슨하게 만드는 것이 아니라 다음의 **제한적 recovery exception**을 추가하는 것이 적절하다.

1. recorder preflight가 실패하면 원래 요청의 일반 구현·운영 변경은 계속 차단한다.
2. 단, 실패 원인이 recorder/Chat 저장/잠금/원자적 교체 또는 그 거버넌스 자체에 있을 때는 사용자 명시 승인 또는 검증된 recovery capability 아래에서 진단·증거 보존·복구·Rule 검토에 필요한 최소 작업을 허용한다.
3. 이 예외 중에는 기능 개발·운영 병합·무관한 일반 파일 변경으로 범위를 확대하지 않는다.
4. 복구 후 `conversation-recorder ensure`와 `governance-tool validate`가 다시 성공하기 전에는 원래 일반 작업으로 복귀하지 않는다.
5. 플랫폼별 기능 차이는 동일 도구 강제가 아니라 동일한 안전 결과를 만족하는 capability별 경로로 처리한다.

이 취지는 기존 Reports 012와 014가 이미 권고한 내용과 일치하며, 현재 Rule의 목적을 약화시키지 않고 순환 차단만 제거한다.

## 7. 후속 처리 결정

- 본 Git-index 예방 작업은 **예방 조치와 위험 경로 실증 완료**로 종결 가능하다.
- 과거 0바이트 사건의 정확한 OS 실패 조건 재현은 필수 예방책의 완료 조건에서 분리하고, 재발 시 확보된 증거를 이용하는 forensic follow-up으로 남긴다.
- recorder preflight recovery exception은 별도 Plan/Task로 분리한다. 이는 Git-index 원인과 다른 거버넌스 설계 문제이므로 같은 Task에 섞지 않는다.
- 운영 `Rule.md` 직접 수정은 기존 HUMAN-11.6~11.8 절차에 따라 Staging 후보와 동기화 검증을 먼저 만든 뒤 반영한다.

---

## 8. 현재 판정

**Git index 작업:** 구현·ProcMon 실증 완료. 직접 재쓰기 위험 경로 확정. 정확한 0바이트 실패 조건만 미재현.

**거버넌스:** 현재 v1.3.1은 parser/추적성 관점에서 정상이나, recorder 자체 장애 시 recovery 작업을 허용하는 제한적 예외가 부족하다. 별도 개선 작업을 시작하는 것이 타당하다.
