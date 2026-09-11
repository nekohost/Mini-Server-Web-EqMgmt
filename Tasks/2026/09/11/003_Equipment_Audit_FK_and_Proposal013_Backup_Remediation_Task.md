---
artifact_id: TASK-20260911-003
work_id: WORK-20260911-EQUIPMENT-AUDIT-FK-BACKUP-REMEDIATION
created_at: 2026-09-11T10:02:41.510+09:00
related_artifacts:
  - ../../../../Plans/2026/09/11/003_Equipment_Audit_FK_and_Proposal013_Backup_Remediation_Plan.md
  - ../../../../Reports/2026/09/11/004_Equipment_Audit_FK_and_Proposal013_Backup_Remediation_Validation_Report.md
  - ../../../../Plans/2026/09/11/002_Equipment_Deletion_and_Node_Usage_Consistency_Plan.md
---

# [Task] 장비 감사 로그 외래키 및 제안 013 백업 실패 개선

- 작업 ID: `WORK-20260911-EQUIPMENT-AUDIT-FK-BACKUP-REMEDIATION`
- 상태: 원인 확정·별도 계획·Validation 완료 / 구현 미착수

## 완료된 작업

- [x] 운영 백업 HTTP 500과 안전 오류 문구 확인
- [x] 서비스 실행 방식, DB 파일 권한과 디스크 여유 확인
- [x] 운영 DB `integrity_check=ok` 확인
- [x] `equipments_audit_log` 외래키 위반 4건 확인
- [x] 장비 삭제 API와 감사 테이블 스키마의 의미 충돌 확인
- [x] 기존 002 계획과의 병합·분리 판단
- [x] 별도 migration·제안 013 회귀 계획 작성
- [x] Validation 1~8 사전 검토 기록

## 구현 대기 작업

- [ ] 운영 commit·실제 감사 테이블 SQL·인덱스·행 수 기준선 확인
- [ ] 모의 DB와 고아 감사 기록 재현 fixture 작성
- [ ] 멱등적 감사 테이블 재구축 migration 후보 작성
- [ ] 기존 감사 행·ID·내용·시각 보존 검증 작성
- [ ] 신규 설치용 `app.py` 및 `db_migration.py` 스키마 정의 후보 수정
- [ ] 제안 013 백업 실패 단계·오류 ID 서버 로깅 후보 작성
- [ ] DB 작업 디렉터리 `0700` 권한 보강 후보 작성
- [ ] Staging 단위·실패 주입·중복 실행·rollback 시험
- [ ] 사용자 검토 후 운영 소스 병합
- [ ] Linux 운영 DB 사전 백업·migration·무결성·백업 다운로드 시험

## 차단 조건

- 운영 DB 복구 사본과 감사 행 보존 기준선이 없으면 실제 migration을 실행하지 않는다.
- 실제 테이블 정의가 계획과 다르면 임의로 맞추지 않고 차이를 보고한다.
- 감사 행 삭제, 장비 ID 치환, 백업 외래키 검사 우회는 해결책으로 사용하지 않는다.
