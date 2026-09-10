---
artifact_id: TASK-20260909-007
work_id: WORK-20260909-GIT-INDEX-PREVENTION
created_at: 2026-09-10T08:27:35.106+09:00
related_artifacts:
  - ../../../../Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md
  - ../../../../Reports/2026/09/10/003_Git_Index_ProcMon_Evidence_and_Codex_Continuation_Report.md
---
# [Task] Git 인덱스 0바이트 손상 방지 및 증거 보존

- 최초 작성일: 2026-09-09
- 3차 개정일: 2026-09-10
- 최종 상태 갱신일: 2026-09-10
- `work_id`: `WORK-20260909-GIT-INDEX-PREVENTION`
- 상태: **핵심 완료 — 예방 조치 및 Process Monitor 위험 경로 실증 완료, 정확한 0바이트 실패 조건만 미재현**
- 관련 계획: `Plans/2026/09/09/005_Git_Index_Corruption_Prevention_Plan.md`
- 선행 검토: `Reports/2026/09/09/014_Git_Index_Corruption_Prevention_Second_Review_Report.md`
- 3차 계획 검증: `Reports/2026/09/10/001_Git_Index_Corruption_Prevention_Third_Revision_Validation_Report.md`
- 구현 및 승인 검토: `Reports/2026/09/10/002_Git_Index_Corruption_Prevention_Implementation_and_ProcMon_Approval_Report.md`
- 최종 증거·인계: `Reports/2026/09/10/003_Git_Index_ProcMon_Evidence_and_Codex_Continuation_Report.md`

## 작업 목록

- [x] 5건의 0바이트 사건 시각과 Antigravity 직접 index 쓰기 경로 확인
- [x] Plan 005를 3차 개정하고 공통 `work_id` 부여
- [x] 3차 계획 Validation 1~8 및 검토 보고서 발행
- [x] Antigravity Inline Diff 비활성화 및 설정 반영 확인
- [x] read-only Git wrapper와 capability 3종 정책 반영
- [x] `artifact-manager.mjs` Git 조회 환경 격리
- [x] `.gitattributes`로 핵심 거버넌스 파일 LF 고정
- [x] 단위·통합·거버넌스·recorder·Git 무결성 검증
- [x] Process Monitor 반입 및 통제 재현 승인 검토 보고서 발행
- [x] 격리 저장소에서 Process Monitor 호출 스택 및 `WriteFile` 증거 캡처
- [x] 캡처 결과와 Codex 중단 지점을 반영한 최종 증거·인계 보고서 발행
- [ ] 과거 사건에서 index가 정확히 0바이트가 되는 Windows/동시성 실패 조건 재현 — 재발 시 forensic follow-up, 예방 완료의 차단 조건 아님

## 현재 완료 기준

운영 저장소의 예방 조치와 위험 경로 실증은 완료했다. 실제 저장소 index는 실증 과정에서 불변이었고, 재현은 일회용 저장소에서 수행됐다. 남은 0바이트 세부 실패 조건은 원인 은폐를 피하기 위해 별도 forensic 과제로 유지하며, 현재 적용된 보호조치를 되돌리는 조건으로 사용하지 않는다.
