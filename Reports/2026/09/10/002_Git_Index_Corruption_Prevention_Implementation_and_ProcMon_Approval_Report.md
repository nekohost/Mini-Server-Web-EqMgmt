---
artifact_id: REPORT-20260910-002
work_id: WORK-20260909-GIT-INDEX-PREVENTION
created_at: 2026-09-10T08:28:32.412+09:00
related_artifacts:
  - ../../../../Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md
  - ../../../../Tasks/2026/09/09/007_Git_Index_Corruption_Prevention_Task.md
---
# [Report] Git 인덱스 손상 방지 구현 결과 및 Process Monitor 승인 검토

- 작성일: 2026-09-10 (KST)
- `work_id`: `WORK-20260909-GIT-INDEX-PREVENTION`
- 상태: **저장소 내부 조치 완료 / 외부 도구 기반 통제 재현 승인 대기**
- 관련 계획: `Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md`
- 선행 검증: `Reports/2026/09/10/001_Git_Index_Corruption_Prevention_Third_Revision_Validation_Report.md`

## 1. 결론

현재 저장소에 직접 적용할 수 있는 가역적 예방 조치는 완료했다. Antigravity의 실제 index 쓰기 진입점인 Inline Diff를 비활성화했고, 자동화된 Git 조회는 `GIT_OPTIONAL_LOCKS=0`을 강제하는 허용 목록 wrapper로 제한했다. 핵심 거버넌스 파일의 줄바꿈도 LF로 고정했다.

남은 단계는 Process Monitor로 `.git/index` 및 `.git/index.lock` 접근 주체와 호출 스택을 캡처해 원인을 최종 확정하는 일이다. 이 단계에는 외부 실행 파일 반입, 관리자 권한 또는 UAC, Antigravity 쓰기 동작의 의도적 재현이 포함될 수 있으므로 별도 승인을 요청한다.

## 2. 완료한 조치

1. `.vscode/settings.json`에 `"antigravity.enableInlineDiff": false`를 적용했다.
2. `.agent-governance/tooling/git-readonly.mjs`를 추가해 허용된 읽기 전용 하위 명령만 실행하고 `GIT_OPTIONAL_LOCKS=0`을 강제했다.
3. Codex, Gemini Antigravity, Claude capability 3종에 동일한 Git 조회 경로와 금지 조건을 반영했다.
4. `artifact-manager.mjs`의 `git log` 조회 환경에도 `GIT_OPTIONAL_LOCKS=0`을 적용했다.
5. 루트 `.gitattributes`를 추가해 `Rule.md`, 진입점 문서, `.agent-governance/**`를 LF로 고정했다.
6. Staging 후보 검증 후 운영 파일과 테스트를 반영했다.

## 3. 검증 결과

- Staging wrapper 테스트: 3/3 통과
- 운영 wrapper 테스트: 3/3 통과
- `.agent-governance/tooling` 전체 테스트: 44/44 통과
- governance validate: 41개 노드, 오류 0, 경고 0
- conversation recorder verify: 누락 0, receipt 누락 0, 중복 0
- `git fsck --connectivity-only --no-dangling`: 종료 코드 0
- `.vscode/settings.json`: JSON 파싱 및 Inline Diff `false` 확인
- `git check-attr`: 지정한 핵심 파일에 `text=set`, `eol=lf` 확인
- wrapper의 `status --short`, `diff --check`: 종료 코드 0

검증 전후 현재 `.git/index`는 아래 상태로 동일했다.

- 크기: 32,063 bytes
- SHA-256: `4C33BF3C6D5D6BBFBCF80DB1F6D954556FD899ACE6967B76D81DF1C9B139D5E8`
- 마지막 수정 시각: 2026-09-09 20:03:28.9805921

따라서 이번 내부 조치와 검증 과정에서 index의 바이트, 크기, 수정 시각은 변하지 않았다.

## 4. 승인 대상 작업

### 반입 대상

- Microsoft Sysinternals Process Monitor v4.1
- 공식 배포처의 `ProcessMonitor.zip`만 사용
- 격리된 임시 경로 예시: `C:\Users\dooly\AppData\Local\Temp\MiniServer-EqMgmt-ProcMon-20260910\`
- 압축 해제 후 실행 파일의 Authenticode 서명자가 Microsoft인지 확인하고 SHA-256을 기록

### 통제 재현 방법

1. 현재 변경 사항이 있는 작업 저장소에서는 의도적 재현을 하지 않는다.
2. 별도의 일회용 임시 Git 저장소와 별도 VS Code 창을 사용한다.
3. 캡처 시간을 짧게 제한하고 `.git\\index`, `.git\\index.lock` 및 관련 파일 시스템 동작만 필터링한다.
4. 관찰 프로세스는 우선 `Code.exe`, `agy.exe`, `git.exe`로 제한한다.
5. 임시 저장소에서만 Inline Diff를 잠시 활성화하고 Antigravity 편집 1회를 통제 실행한다.
6. 캡처 직후 Inline Diff를 다시 비활성화하고 Process Monitor를 중지한다.
7. PML, 필터 조건, 실행 파일 hash, 확인된 호출 스택을 보고서 증거로 보존한다.

### 영향과 복구

- Process Monitor 드라이버 로딩 과정에서 관리자 권한/UAC 및 EULA 수락이 필요할 수 있다.
- 네이티브 VS Code UI 조작이 필요한 경우 사용자가 UAC 승인과 Antigravity 편집 1회를 직접 수행해야 할 수 있다.
- 재현 실패 시에도 현재 저장소는 건드리지 않으며 임시 저장소만 폐기할 수 있다.
- 임시 도구 및 저장소 삭제는 증거 보고가 끝난 뒤 사용자의 지시에 따라 수행한다.

## 5. 승인 판단

저장소 내부 조치에는 추가 승인이 필요하지 않았고 모두 완료했다. Process Monitor 반입과 통제 재현은 외부 바이너리 실행 및 의도적 위험 동작을 포함하므로, 계획대로 사용자 명시 승인을 받은 뒤에만 진행한다.
