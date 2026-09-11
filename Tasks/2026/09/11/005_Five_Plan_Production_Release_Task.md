---
artifact_id: TASK-20260911-005
work_id: WORK-20260911-FIVE-PLAN-PRODUCTION-RELEASE
created_at: 2026-09-11T10:27:58.365+09:00
related_artifacts:
  - ../../../../Reports/2026/09/11/006_Five_Plan_Production_Release_Report.md
---

# 5개 계획 운영 반영 Task

- 작성: 2026-09-11T10:27:58.365+09:00 (파일 생성 시각 기준)
- 상태: Windows 운영 소스 반영·통합 회귀 완료 / Git·Linux 적용 대기
- 승인: 사용자 명시 승인(추가 확인 없이 Staging → 운영 소스 → commit/push → 가능한 Linux 적용).
- 제외: app.py 교육용 주석 재구축. 기존 변경과 기존 대화 이력은 보존한다.

## 순차 작업

- [x] recorder ensure, manifest/context/validate 및 5개 계획 확인
- [x] 감사 이력 FK 독립화·백업 진단 Staging 구현 (계획 09/11/003)
- [x] 옵션 관리·삭제 참조 일관성 Staging 구현 (계획 09/11/002)
- [x] 전체 모델 경로 Staging 구현 (계획 09/11/001)
- [x] WebMCP Staging 구현 (계획 09/03/006)
- [x] 수신 AI 기록 Staging 재기반 및 Rule 동기화 (계획 09/09/004)
- [x] 순차 검증 1~8 및 교차 시나리오, 운영 소스 병합·재검증
- [x] 릴리스 Task/Report/일자별 index를 실제 상태로 정합화
- [ ] Staging 릴리스 후보 정리 (Linux 실검증 후)
- [ ] commit/push 및 원격 commit 확인
- [ ] Linux 적용·격리 테스트·서비스 확인 (인증 불가 시 정확한 잔여 절차 보고)

## 기록

- 검증 보고서: ../../../../Reports/2026/09/11/006_Five_Plan_Production_Release_Report.md
- 기존 TASK-20260911-004는 다른 계획 작성 작업이므로 보존하고 본 Task 번호만 005로 조정했다.
- 최초 SSH 확인: 대상 192.168.0.166 연결 후 publickey/password 인증 거절. 인증정보를 추측하거나 출력하지 않는다.
