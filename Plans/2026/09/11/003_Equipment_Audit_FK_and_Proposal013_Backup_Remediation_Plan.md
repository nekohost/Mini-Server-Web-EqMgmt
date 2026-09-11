---
artifact_id: PLAN-20260911-003
work_id: WORK-20260911-EQUIPMENT-AUDIT-FK-BACKUP-REMEDIATION
created_at: 2026-09-11T10:02:41.510+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/11/003_Equipment_Audit_FK_and_Proposal013_Backup_Remediation_Task.md
  - ../../../../Reports/2026/09/11/004_Equipment_Audit_FK_and_Proposal013_Backup_Remediation_Validation_Report.md
  - ./002_Equipment_Deletion_and_Node_Usage_Consistency_Plan.md
  - ../../../../Plans/2026/09/07/001_Proposal013_DB_Backup_Restore_Plan.md
---

# [계획서] 장비 감사 로그 외래키 및 제안 013 백업 실패 개선

- 작성일: 2026-09-11
- 작업 ID: `WORK-20260911-EQUIPMENT-AUDIT-FK-BACKUP-REMEDIATION`
- 상태: 운영 증상·원인 확정 / 별도 계획 및 사전 검토 완료 / 구현 미착수
- 귀속: 제안 013 운영 결함 수정 및 제안 047 삭제 생명주기 후속 개선

## 1. 분리 판단

`002_Equipment_Deletion_and_Node_Usage_Consistency_Plan.md`는 옵션 관리 UI/API와 노드 사용량 정합성을 주 범위로 하며, 감사 테이블 스키마 조정은 별도 migration 승인 대상으로 명시했다. 이번 결함은 실제 운영 DB의 테이블 재구축과 기존 감사 기록 보존, 제안 013 백업 회귀 검증을 요구한다. 변경 위험과 롤백 기준이 옵션 관리 작업보다 크므로 기존 002에 병합하지 않고 별도 계획으로 분리한다.

다만 원인은 장비 하드 삭제 생명주기에서 발생했으므로 002의 필수 연계 계획으로 두고, 백업 실패를 직접 해소하므로 제안 013의 결함 수정 계획으로도 연결한다. 신규 독립 기능 제안 번호는 부여하지 않는다.

## 2. 운영에서 확인된 증거와 원인

- 관리자 점검 모드에서 `POST /api/admin/database/backup`이 반복해서 HTTP 500을 반환했다.
- DB 파일 소유자는 `nekohost`, 무결성 검사 결과는 `integrity: ok`, 디스크 여유 공간은 89GB였다.
- `PRAGMA foreign_key_check`는 `equipments_audit_log` rowid 1~4가 `equipments`를 참조하는 위반 4건을 반환했다.
- 현재 삭제 API는 `equipments_audit_log`에 DELETE 스냅샷을 기록한 뒤 `equipments` 행을 물리 삭제한다.
- 현재 감사 테이블은 `equipment_id INTEGER NOT NULL`과 `FOREIGN KEY (equipment_id) REFERENCES equipments(id)`를 함께 선언한다.
- DB 연결에서 외래키 강제가 일관되게 활성화되지 않아 삭제는 성공하지만 감사 기록이 고아 외래키로 남는다.
- 제안 013의 `inspect_database_file()`은 온라인 백업 후 `foreign_key_check` 결과가 하나라도 있으면 백업 다운로드를 거부한다.

따라서 직접 원인은 파일 권한이나 저장 공간이 아니라, 삭제된 장비의 식별자를 영구 보존해야 하는 감사 로그와 살아 있는 장비만 허용하는 외래키 제약의 의미 충돌이다.

## 3. 목표와 데이터 보존 계약

1. 기존 `equipments_audit_log` 모든 행과 원래 `equipment_id`, 시간, 이전값·새값을 그대로 보존한다.
2. 감사 기록은 장비 본체 삭제 후에도 독립적으로 존속하며 살아 있는 `equipments` 행을 필수 부모로 요구하지 않는다.
3. 기존 고아 감사 행을 삭제하거나 임의의 다른 장비 ID로 치환하지 않는다.
4. 장비 삭제의 현재 하드 삭제 정책은 이번 계획에서 소프트 삭제로 확대하지 않는다.
5. 마이그레이션 완료 후 `PRAGMA integrity_check`는 `ok`, `PRAGMA foreign_key_check`는 0건이어야 한다.
6. 제안 013 백업 다운로드가 같은 운영 DB 스냅샷을 정상 생성·검증·전송해야 한다.
7. 브라우저에는 내부 정보를 숨긴 기존 안전 문구를 유지하고, 서버 제한 로그에는 실패 단계와 상관관계 ID를 남긴다.

## 4. 스키마 개선 설계

`equipments_audit_log.equipment_id`는 삭제 당시 장비 식별자를 보존하는 감사 스냅샷 값으로 유지하되 `equipments(id)` 외래키 제약을 제거한다. `equipment_id`의 이름·값·NOT NULL 계약은 유지하여 기존 조회 코드와 감사 의미를 깨지 않는다.

SQLite 전진 마이그레이션은 다음 순서로 수행한다.

1. 운영 적용 전 SQLite Online Backup API로 원본 복구 사본을 생성한다.
2. 사본의 SHA-256, `integrity_check=ok`, 기존 외래키 위반 목록 4건과 감사 테이블 행 수를 기준선으로 기록한다.
3. transaction 안에서 외래키 없는 임시 감사 테이블을 동일 컬럼·기본값으로 생성한다.
4. 모든 행을 명시적 컬럼 목록과 기존 `id` 값으로 복사한다.
5. 원본·후보의 행 수, 최소·최대 ID, 컬럼별 NULL 수와 내용 지문을 비교한다.
6. 비교가 일치할 때만 기존 테이블을 제거하고 후보를 `equipments_audit_log`로 변경한다.
7. 기존 인덱스가 있다면 동일 정의로 재생성하고 `sqlite_sequence`의 다음 ID 안전성을 확인한다.
8. `integrity_check`, `foreign_key_check`, 감사 로그 조회와 신규 CREATE/UPDATE/DELETE 감사 기록을 재검증한 뒤 commit한다.
9. 어느 검증이든 실패하면 transaction을 rollback하고 원본 DB 및 복구 사본을 보존한다.

`app.py`의 신규 설치용 `CREATE TABLE`과 `db_migration.py`의 동일 정의도 함께 수정한다. 실행 중인 기존 DB에는 이름이 고정된 멱등 migration을 한 번만 적용하며, 컬럼이나 제약이 예상과 다르면 임의 재구축하지 않고 중단한다.

## 5. 제안 013 오류 관측성과 작업 디렉터리 보강

- 백업 처리의 허용된 예외를 삼킨 채 500만 반환하지 않고, 서버 로그에 상관관계 ID·실패 단계·예외 유형을 기록한다.
- 응답에는 내부 경로·SQL·스택 트레이스를 넣지 않고 기존 안전 문구와 불투명한 오류 ID만 제공한다.
- `DATABASE_OPERATION_ROOT`와 `candidates`, `backups`, `jobs`는 기존 디렉터리인 경우에도 서비스 계정 전용 `0700` 권한을 재확인한다.
- 현재 확인된 `instance/database-operations`의 `0775`는 직접적인 500 원인은 아니지만 운영 가이드와 불일치하므로 같은 제안 013 보안 보완에 포함한다.
- 수동 `python app.py` 실행 여부와 무관하게 실제 `DATABASE_PATH`와 작업 루트가 시작 로그 또는 관리자 상태 화면에서 비밀 없이 확인 가능하도록 검토한다.

## 6. Staging 구현 및 검증 순서

1. 운영 DB가 아닌 모의 DB에 정상 장비·감사 기록과 장비 삭제 후 고아 감사 기록을 구성한다.
2. 마이그레이션 전 제안 013 백업 검증이 외래키 위반으로 실패하는 것을 재현한다.
3. migration 후보를 적용하고 감사 행·ID·JSON·시각이 바이트 또는 정규화 값 기준으로 보존되는지 확인한다.
4. 마이그레이션 후 백업 생성·검증·다운로드 응답 계약을 시험한다.
5. 빈 감사 테이블, 대량 감사 행, 예상 밖 컬럼·인덱스, migration 중 실패, 중복 실행을 검증한다.
6. `foreign_keys=OFF`와 `ON` 연결 모두에서 신규 삭제와 감사 보존 의미가 일치하는지 검증한다.
7. 작업 디렉터리 권한과 오류 로그 비밀 비노출을 정적으로 검증한다.
8. Staging 검증 결과와 운영 migration·rollback 절차를 별도 보고한 뒤 운영 반영 여부를 결정한다.

## 7. 운영 적용과 롤백

- 실제 운영 DB 변경 전 현재 프로세스를 식별하고 신규 쓰기를 차단하는 점검 상태를 유지한다.
- 온라인 복구 사본은 이번 migration이 검증될 때까지 자동 정리 대상과 분리하여 보존한다.
- migration 실패 시 transaction rollback을 우선하며, DB 파일 수준 문제가 있으면 검증된 사본으로만 복구한다.
- 운영 적용 후에도 기존 외래키 위반이 남거나 감사 행 수·지문이 다르면 제안 013 백업을 재시도하지 않고 점검 상태에서 중단한다.
- 코드 롤백과 스키마 롤백은 분리한다. 외래키를 다시 추가하면 동일 삭제 모순이 재발하므로 단순 Down migration을 자동 실행하지 않고, 보존된 사본과 사용자 판단을 사용한다.

## 8. 완료 기준

- 기존 감사 로그가 한 건도 삭제·변조되지 않는다.
- 삭제된 장비의 과거 ID와 DELETE 당시 `old_value`를 계속 조회할 수 있다.
- 신규·기존 DB 모두 동일한 외래키 없는 감사 테이블 계약을 사용한다.
- 장비 삭제 후 `foreign_key_check`가 0건이다.
- 제안 013 백업 다운로드가 HTTP 200과 유효한 SQLite 첨부 파일을 반환한다.
- 실패 시 서버 로그의 오류 ID로 원인을 추적할 수 있고 브라우저에는 내부 정보가 노출되지 않는다.
- DB 작업 디렉터리와 하위 디렉터리가 서비스 계정 전용 권한을 갖는다.

## 9. 승인 및 실행 경계

이 문서는 원인 확정과 구현 계획·Validation 기준선만 기록한다. Staging 코드·migration 작성, 운영 DB 변경, 서버 권한 변경, 배포·재시작은 아직 수행하지 않는다. 구현 지시가 내려오면 먼저 모의 DB 기반 Staging 후보와 자동화 시험을 작성한다.
