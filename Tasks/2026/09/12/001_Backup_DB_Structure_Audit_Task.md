---
artifact_id: TASK-20260912-001
work_id: DB-STRUCTURE-AUDIT-20260912
created_at: 2026-09-12T14:06:19.511+09:00
related_artifacts:
  - ../../../../Reports/2026/09/12/001_Backup_DB_Structure_Audit_Report.md
---

# 백업 서버 DB 구조 감사 Task

- work_id: `DB-STRUCTURE-AUDIT-20260912`
- 작업 모드: 읽기 전용 검토
- 대상 DB: `/home/nekohost/services/Mini-Server-Web-EqMgmt/equipment.db`
- 코드 대조 대상: `app.py`, `db_migration.py`, `down_migration.py`

## 목적

백업 서버에서 실제 운용 중인 SQLite DB의 구조를 직접 조사하고, 애플리케이션 코드가 전제하는 스키마와의 차이를 확인한다.

## 점검 범위

1. SQLite 버전 및 DB PRAGMA 상태
2. 테이블·뷰·트리거·인덱스 정의
3. 컬럼·PK·NOT NULL·기본값·외래키
4. 테이블별 레코드 수와 식별자 범위
5. 무결성·외래키·고아 데이터·삭제 상태 분포
6. `app.py` 및 마이그레이션 코드와 실제 스키마의 차이

## 안전 조건

- SQLite URI `mode=ro`로만 연결한다.
- 비밀번호 해시, 세션 토큰, 인증 토큰, 이메일 등 민감한 실제 값은 출력하지 않는다.
- INSERT, UPDATE, DELETE, DDL, VACUUM, REINDEX를 실행하지 않는다.
- 조사 결과는 별도 Report에 기록한다.
