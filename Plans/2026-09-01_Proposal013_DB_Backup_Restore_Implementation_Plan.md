# [기획서] [제안-013] 웹 기반 DB 데이터 백업 및 복원 (Administrator Backup & Restore)

미니서버(Linux Lite) 환경의 하드웨어 장애나 관리자 실수에 대비하여, 웹 관리자 화면에서 단일 클릭으로 SQLite DB 백업본을 안전하게 다운로드하고, 필요시 검증된 백업 파일을 업로드하여 100% 롤백/복원할 수 있는 재난 복구(Disaster Recovery) 인프라를 구축합니다.

---

## User Review Required

> [!IMPORTANT]
> **1. SQLite WAL 저널 모드와 온라인 백업 API(`Connection.backup`) 채택**
> - 현재 시스템은 동시성 제어를 위해 SQLite WAL 모드를 운용 중입니다. 단순 파일 복사 방식은 쓰기 트랜잭션 중 WAL 파일(`equipment.db-wal`) 분실 위험이 있습니다.
> - 따라서 Python 내장 `sqlite3.Connection.backup()` API를 사용하여 **무정지·원자적(Atomic) 스냅샷**을 생성하며, 복원 시에도 동일한 API로 라이브 DB에 원자적 반영을 수행합니다.
> 
> **2. 복원 시 4중 안전 방어막 및 자동 백업(Fail-Safe Rollback)**
> - 잘못되거나 오염된 파일 복원으로 인한 시스템 파괴를 방지하기 위해:
>   1. 확장자 및 파일 시그니처 16바이트(`SQLite format 3\000`) 검사
>   2. 임시 파일 대상 `PRAGMA integrity_check` 무결성 검증
>   3. 필수 핵심 테이블(`equipment`, `users`, `menus`, `role_menu_permissions` 등) 존재 여부 검사
>   4. **복원 직전 라이브 DB를 `equipment_auto_backup_before_restore_*.db`로 자동 백업 강제** (복원 오류 시 즉시 롤백 가능)
> 
> **3. Rule.md 제4-3조 (각 코드 줄마다 주석 작성) 엄격 준수**
> - 신규 작성되는 모든 백엔드 로직 및 프론트엔드 자바스크립트의 각 라인마다 상세 설명 주석을 100% 작성합니다.

---

## Proposed Changes

### [Phase 1: Staging 개발 환경 격리 구축]
- `Rule.md` 제7-3조에 따라 운영 루트 코드를 건드리지 않고, `Staging/` 디렉토리에 작업 환경을 격리 셋업합니다.

#### [NEW] [Staging/templates/backup_restore.html](file:///d:/Project/Mini-Server-Web-EqMgmt/Staging/templates/backup_restore.html)
- 관리자 전용 DB 백업 및 복원 UI 템플릿 신규 생성.
- DB 실시간 현황 카드(용량, 저널 모드, 테이블별 건수), 백업 다운로드 버튼, 복원 업로드 폼 및 이중 확인 모달 포함.

---

### [Phase 2: 백엔드 API 및 DB 관리자 메뉴 확장 (`Staging/app.py`)]

#### [MODIFY] [Staging/app.py](file:///d:/Project/Mini-Server-Web-EqMgmt/Staging/app.py)
1. **메뉴 및 권한 등록 (`init_db`)**:
   - `menus` 테이블에 `backup_restore` 메뉴 등록 (`ParentMenuCode = 'admin_center'`, `SortOrder = 7`).
   - 기본 `admin` 역할에 접근 권한 부여 (`role_menu_permissions`).
2. **페이지 렌더링 라우트**:
   - `@app.route('/backup_restore')`: 관리자 권한(`check_menu_permission('backup_restore')`) 체크 후 화면 렌더링.
3. **DB 현황 요약 API**:
   - `GET /api/admin/db_status`: DB 파일 크기, 최종 수정 시각, WAL 저널 상태, 주요 테이블별 레코드 수 반환.
4. **DB 백업 다운로드 API**:
   - `GET /api/admin/backup`: `sqlite3.Connection.backup()`을 통한 단일 파일 덤프 생성 후 `send_file` 다운로드 스트림 반환. 보안 감사 로그(`log_audit`) 기록.
5. **DB 복원 실행 API**:
   - `POST /api/admin/restore`: 4중 검증(시그니처, 무결성, 필수 테이블, 복원 직전 자동 백업) 후 온라인 덮어쓰기 복원 적용. 감사 로그 기록 및 세션 만료 유도.

---

### [Phase 3: 프론트엔드 UI/UX 구현 (`Staging/templates/backup_restore.html`)]
- Tailwind CSS 기반 반응형 대시보드 카드 구성.
- 백업 다운로드 즉시 트리거 및 로딩 상태 처리.
- 복원 파일 업로드 인터랙션 및 **Human-in-the-Loop 이중 확인 모달**(실수 방지).
- 복원 성공 시 카운트다운 후 재로그인 페이지 리다이렉션.

---

## Verification Plan

### Automated / Static Tests
- **구문 및 정적 무결성 검증**:
  - Python 정적 문법 및 모의 스크립트 실행 검증.
  - HTML 태그 닫힘 및 Jinja 템플릿 태그 정합성 검사.
- **주석 품질 정성 감사 (Rule.md 4-3조)**:
  - 3-Tier 메타 주석(`[역할]`, `[의존성 관계]`, `[변경 시 영향도]`) 및 코드 라인별 설명 주석 100% 준수 검증.
- **SQLite 온라인 백업 및 복원 무결성 테스트**:
  - 모의 백업 생성 스크립트를 통한 `.db` 파일 생성 및 `PRAGMA integrity_check` 통과 확인.
  - 가짜/손상된 파일 업로드 시 거부 방어 테스트.

### Manual / Staging Verification
- `Staging/` 환경에서 정적 코드 감사 보고서(`qualitative_validation_report.md`) 작성 및 사용자 승인 득한 후 운영 루트 병합.
