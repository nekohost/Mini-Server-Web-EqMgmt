---
artifact_id: TASK-20260911-002
work_id: WORK-20260911-EQUIPMENT-DELETION-NODE-USAGE
created_at: 2026-09-11T09:36:07.846+09:00
updated_at: 2026-09-11T09:39:58.167+09:00
related_artifacts:
  - ../../../../Plans/2026/09/11/002_Equipment_Deletion_and_Node_Usage_Consistency_Plan.md
  - ../../../../Reports/2026/09/11/003_Equipment_Deletion_and_Node_Usage_Consistency_Validation_Report.md
---

# 장비 삭제·옵션 관리·노드 사용량 정합성 개선 Task

- 상태: 원인 확정 및 통합 계획 완료 / 구현 승인 대기
- 작업 모드: 계획
- 귀속: 제안 047 후속 개선

## 작업 목록

- [x] 장비 삭제 API와 equipments 스키마 정의 확인
- [x] 관리자 노드의 장비·옵션 집계 및 삭제 차단 조건 확인
- [x] 소프트 삭제 가설과 현재 소스의 차이 기록
- [x] 별도 계획 분리 및 Validation 1~8 수행
- [x] 옵션 잔존 원인 사용자 확인 및 기존 계획 병합 판단
- [x] 기존 옵션 API와 관리자 화면의 기능 공백 확인
- [ ] 운영 commit·DATABASE_PATH·실제 스키마 read-only 확인
- [ ] Staging 수정 후보 및 회귀 테스트 작성
- [ ] 관리자 옵션 조회·추가·수정·안전 삭제 UI/API 검증
- [ ] 사용자 승인 후 운영 소스 병합
- [ ] Linux 실제 삭제·관리자 화면 확인
