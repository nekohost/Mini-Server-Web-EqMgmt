---
artifact_id: REPORT-20260910-007
work_id: WORK-20260910-PROJECT-SCOPE-BOUNDARY
created_at: 2026-09-10T13:07:14.172+09:00
related_artifacts:
  - ../../../../Plans/2026/09/10/002_Project_Scope_Boundary_and_General_Handoff_Plan.md
  - ../../../../Tasks/2026/09/10/002_Project_Scope_Boundary_and_General_Handoff_Task.md
---
# [구현 보고서] Project Scope Boundary 및 General Handoff 운영 반영

- 작성일: 2026-09-10
- `work_id`: `WORK-20260910-PROJECT-SCOPE-BOUNDARY`
- 상태: **운영 반영 및 최종 검증 완료**
- 관련 Plan: `Plans/2026/09/10/002_Project_Scope_Boundary_and_General_Handoff_Plan.md`
- 관련 Task: `Tasks/2026/09/10/002_Project_Scope_Boundary_and_General_Handoff_Task.md`
- 선행 Validation: `Reports/2026/09/10/006_Project_Scope_Boundary_Plan_Validation_Report.md`

## 1. 최종 설계

프로젝트 경계를 단순한 파일 경로로 판정하지 않고 세 범위로 분리했다.

- `owner scope`: 현재 작업의 목적·승인·기록·기본 governance 소유자.
- `reference scope`: owner 작업을 위한 외부 read-only 관찰 범위. owner 유지.
- `execution scope`: owner 작업을 위한 실제 외부 조치 대상. 경로만으로 owner를 바꾸지 않음.

다른 governed workspace 내부의 실제 write만 `nested handoff`로 대상 governance에 위임하고, 완료 후 부모 owner로 복귀한다. 사용자가 독립 작업으로 의도를 전환한 경우에만 `full scope switch`한다.
## 2. 운영 반영 내용

Mini-Server governance를 `1.3.2`에서 `1.4.0`으로 갱신했다.

주요 변경은 다음과 같다.

- Rule에 `1-4` ~ `1-4-7` scope 경계 조항과 `6-2-13` scope-aware 기록 경계를 추가했다.
- always-load node `context.scope-boundary`를 추가했다.
- router에 scope intent와 외부 path guard를 추가했다.
- 외부 path는 `external-reference`, `external-execution`, `nested-handoff`, `switch-scope` 등 명시적 scope intent 없이는 fail-closed한다.
- Codex, Antigravity, Claude capability에 project-bound scope 동작을 명시했다.
- `CHATGPT.md`, `capabilities/chatgpt-remote.yaml`, `ENTRY-CHATGPT.SCOPE`를 추가했다.
- ChatGPT + Remote Desktop Commander는 도구 사용 자체가 아니라 사용자 의도와 부모 작업 연속성으로 owner를 판단한다.
- 현재 ChatGPT conversation 자동 recorder는 통합되지 않았다고 명시했다.
- `rule-map.yaml`과 `entrypoint-map.yaml`의 source ID 존재성을 validator가 양방향 검사하도록 강화했다.
- 강화 검증 과정에서 기존 누락 `RULE-7.2.3`, `RULE-7.2.4`를 `rule-map.yaml`에 복구했다.
## 3. Staging 및 운영 검증

운영 반영 전에 `Staging/Rule.md`, Staging governance tree, 4개 platform bootstrap으로 독립 후보를 구성했다. 후보는 `v1.4.0`, manifest/human map 42개 node, YAML 11개, 오류 0, 경고 0, Rule `inSync=true`로 통과했다.

운영 반영 시 기존 파일 16개와 신규 파일 3개를 대상으로 rollback 사본을 생성한 뒤 후보 19개 파일을 SHA-256 일치 상태로 복사했다. 이후 회귀 테스트 갱신과 `.gitattributes`의 `CHATGPT.md text eol=lf` 추가를 후속 보강으로 반영했다.

운영 위치의 최종 governance 결과:

- governance version: `1.4.0`
- manifest nodes: `42`
- human map nodes: `42`
- parsed YAML: `11`
- errors: `0`
- warnings: `0`
- Rule SHA-256: `A5D0D845C298D98268746326812D1279A3F72CE0D9E9B0C63D7EBE34F2D98E39`
- sync-status: `inSync=true`

라우팅 검증에서는 일반 프로젝트 작업에서도 `context.scope-boundary`가 기본 로드되고, scope intent 없이 외부 path를 전달하면 exit code 1로 차단됨을 확인했다.
## 4. 회귀 테스트 및 무결성

초기 `npm test` 재실행에서 `governance-tool.test.mjs`가 node 41개/YAML 10개를 하드코딩한 구버전 기대값 때문에 실패했다. 테스트 fixture를 v1.4.0에 맞게 갱신하고 scope 회귀 항목을 추가한 뒤 전체 테스트를 다시 수행했다.

최종 결과:

- governance-tool regression: `14/14` 통과
- conversation-recorder: `17/17` 통과
- artifact-manager: `12/12` 통과
- git-readonly: `3/3` 통과
- `conversation-recorder ensure`: Codex/Antigravity 정상, 신규 누락 0
- `git diff --check`: exit 0

`.gitattributes`의 LF 고정 대상에 `CHATGPT.md`를 추가했고, 이번 governance/bootstrap 변경 파일의 CRLF를 LF로 정규화했다. 최종 `diff --check`에 남은 줄바꿈 경고는 이번 범위 밖의 기존 `.vscode/settings.json` 및 2026-09-09 index 문서뿐이다.

실제 `.git/index`는 작업 전후 모두 32,063 bytes, SHA-256 `4C33BF3C6D5D6BBFBCF80DB1F6D954556FD899ACE6967B76D81DF1C9B139D5E8`, mtime `2026-09-09T20:03:28.9805921+09:00`로 불변이다.

## 5. 현재 의미

Mini-Server 작업은 프로젝트 해결을 위해 저장소 밖을 참조하거나 비독립 PC 환경을 조치해도 owner를 유지한다. 다른 governed workspace의 실제 변경만 nested handoff하며, 사용자의 독립 작업 전환 의도가 있을 때만 General 또는 다른 owner로 full switch한다.

General은 Mini-Server의 상위 governance가 아니며, Mini-Server도 foreign governed workspace의 규칙을 완화할 수 없다.
