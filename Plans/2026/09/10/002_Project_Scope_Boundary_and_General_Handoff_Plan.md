---
artifact_id: PLAN-20260910-002
work_id: WORK-20260910-PROJECT-SCOPE-BOUNDARY
created_at: 2026-09-10T12:38:43.279+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/10/002_Project_Scope_Boundary_and_General_Handoff_Task.md
  - ../../../../Reports/2026/09/10/007_Project_Scope_Boundary_and_General_Handoff_Implementation_Report.md
---
# [계획서] Mini-Server Project Scope Boundary 및 General Handoff 통합

- 작성일: 2026-09-10
- `work_id`: `WORK-20260910-PROJECT-SCOPE-BOUNDARY`
- 상태: **완료 — Mini-Server governance v1.4.0 운영 반영 및 검증 완료**
- 상위 설계: `D:\General\Plans\2026\09\10\002_Cross_Scope_Ownership_and_Reference_Model_Plan.md`

## 1. 목적

Mini-Server 작업이 저장소 밖의 Git·IDE·OS·네트워크·PC 환경을 조사하거나 조치해야 하는 경우에도, 그 행위가 프로젝트 목적의 연속이면 Mini-Server governance가 owner로 유지되도록 명문화한다.

동시에 다른 governed workspace를 실제 변경하거나 사용자가 독립 General 작업으로 전환하는 경우에는 잘못된 governance 침범을 막는 handoff 경계를 만든다.

## 2. Scope 모델

- owner scope: 부모 작업의 목적·승인·기록·governance 소유자.
- reference scope: 프로젝트 해결을 위한 외부 read-only 관찰 범위. owner 유지.
- execution scope: 프로젝트 해결을 위한 실제 조치 대상. 경로만으로 owner를 바꾸지 않음.
- nested handoff: foreign governed workspace write만 대상 governance에 subtask 위임.
- full scope switch: 사용자 명시적 새 독립 작업/owner 전환일 때만 수행.
## 3. 플랫폼별 의미

1. VS Code에서 Mini-Server workspace로 시작한 Codex/Antigravity 작업은 프로젝트를 기본 owner로 본다.
2. Git index, extension host, VS Code 설정처럼 저장소 밖 문제를 조사해도 프로젝트 복구 목적이면 owner는 유지된다.
3. ChatGPT + Remote Desktop Commander는 특정 workspace에 물리적으로 묶이지 않으므로 active owner를 사용자 의도와 현재 작업 연속성으로 추적한다.
4. Remote Desktop Commander 사용 자체는 General 전환 근거가 아니다.
5. 독립 PC 유지보수 요청으로 사용자가 의도를 바꾸면 General로 full switch할 수 있다.

## 4. 구현 범위

- Rule에 project scope boundary 조항 추가.
- 새 `context.scope-boundary` node 추가.
- router에 external reference/execution/nested/full switch intent 추가.
- 4개 플랫폼 bootstrap에 owner/reference/execution 구분 안내.
- ChatGPT + Remote Desktop capability와 entrypoint를 최소 등록.
- project Chat 기록 경계에 full switch / nested handoff 의미 반영.

## 5. 안전 경계

다른 governed workspace의 read-only reference는 ownership을 바꾸지 않는다. 실제 write는 대상 governance를 읽고 nested handoff한다. 부모 governance는 대상 규칙을 완화할 수 없으며 충돌 시 사용자 결정을 받는다.

## 6. 완료 결과

운영 반영 결과와 최종 검증은 Reports/2026/09/10/007_Project_Scope_Boundary_and_General_Handoff_Implementation_Report.md를 최신 사실 기준으로 사용한다. Mini-Server governance는 v1.4.0으로 활성화되었고 owner/reference/execution/nested/full-switch 모델이 운영 Rule·node·router·platform bootstrap에 반영되었다.
