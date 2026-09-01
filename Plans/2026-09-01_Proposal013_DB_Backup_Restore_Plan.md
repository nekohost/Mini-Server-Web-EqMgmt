# [기획서] [제안-013] 웹 기반 DB 데이터 백업 및 복원 (Administrator Backup & Restore)

## 1. 개요 및 배경

### 1-1. 배경 및 목적
- **배경**:
  - 본 시스템은 Linux Lite 미니서버(특히 SD 카드 또는 소형 SSD 기반 환경)에서 구동되므로, 하드웨어 장애나 전원 단락, 또는 관리자의 실수로 인한 데이터 손실 위험에 항상 노출되어 있습니다.
  - 현재 자산 관리 데이터(`equipment`), 사용자 정보(`users`), 보안 감사 로그(`audit_logs`), 접근 로그(`access_logs`) 등이 단일 SQLite 파일(`equipment.db`)에 영구 저장되고 있으나, 관리자가 웹 UI를 통해 클릭 한 번으로 DB를 즉시 백업받거나 유사시 롤백/복원할 수 있는 웹 기반 재난 복구(Disaster Recovery) 수단이 부재합니다.
- **목적**:
  - 관리자 전용 웹 화면에서 단일 클릭으로 완벽한 원자적(Atomic) DB 백업본을 다운로드할 수 있는 기능 제공.
  - 백업된 `.db` 파일을 웹으로 업로드하여 현재 운영 DB를 안전하게 이전 시점으로 복원(Restore)할 수 있는 기능 제공.
  - 복원 실행 시 발생할 수 있는 데이터 오염을 원천 차단하기 위해 **4중 안전 방어막(무결성 검사, 필수 테이블 검증, 복원 직전 자동 스냅샷 백업, 온라인 백업 API 적용)** 구축.

### 1-2. 연관 제안 및 문서
- **연관 제안**:
  - `[제안-013]`: 웹 기반 DB 데이터 백업 및 복원 (본 기획서 대상)
  - `[제안-022 & 033]`: 장비 상태 및 라이프사이클 관리 (향후 DB 스키마 확장을 앞두고 최우선 안전망으로 작동)
- **준수 규칙**:
  - `Rule.md` 제4-3조: 3-Tier 메타 주석 및 **각 코드 줄마다 상세 주석 작성** 원칙 준수.
  - `Rule.md` 제4-4조: 데이터 보존 원칙 준수 (복원 전 자동 백업 보장).
  - `Rule.md` 제4-5조: 보안 수칙 준수 (관리자 전용 RBAC 권한 체크 및 감사 로그 기록).
  - `Rule.md` 제7-3조: `Staging/` 디렉토리를 통한 격리 개발 및 검증 필수.

---

## 2. 세부 설계 및 아키텍처

### 2-1. SQLite 온라인 백업(Online Backup API) 채택 이유
- 현재 시스템은 동시성 향상 및 디스크 쓰기 병목 해소를 위해 **SQLite WAL(Write-Ahead Logging) 모드**를 활성화하여 운용 중입니다.
- 단순 OS 파일 복사(`shutil.copy` 등) 방식은 트랜잭션 진행 중에 실행될 경우 WAL 저널 파일(`equipment.db-wal`)의 미반영 분이 누락되거나 파일 락(Lock) 충돌로 인해 손상된 백업 파일이 생성될 위험이 있습니다.
- 따라서 Python 내장 `sqlite3.Connection.backup()` 메소드를 채택합니다:
  - **원자성(Atomicity)**: 소스 DB의 페이지 단위 락을 걸고 WAL 저널 데이터를 완벽히 흡수하여 단일 `.db` 파일로 일관성 있게 복제.
  - **무정지 라이브 백업**: 서비스가 가동 중인 상태에서도 읽기/쓰기 블로킹을 최소화하며 안전하게 스냅샷 생성.
  - **무손실 복원**: 복원 시에도 `upload_conn.backup(live_conn)`을 통해 실행 중인 SQLite 커넥션에 페이지 단위로 안전하게 덮어쓰기 적용.

### 2-2. 백엔드 API 설계 (`app.py`)

#### 1) 권한 및 메뉴 등록 (`init_db`)
- `menus` 테이블에 신규 관리자 메뉴 등록:
  - `MenuCode`: `backup_restore`
  - `MenuName`: `데이터베이스 백업 및 복원`
  - `Url`: `/backup_restore`
  - `Description`: `시스템 SQLite DB 파일 다운로드 백업 및 업로드 복원`
  - `ParentMenuCode`: `admin_center`
  - `SortOrder`: `7`
- `role_menu_permissions`: 기본 `admin` 역할에 권한 부여 (`IsAllowed = 1`).

#### 2) 화면 렌더링 라우트 (`GET /backup_restore`)
- **역할**: 관리자 센터 하위의 DB 백업/복원 전용 웹 화면 렌더링.
- **의존성**: `check_menu_permission('backup_restore')` 권한 검증.
- **제공 데이터**: 템플릿에 세션 사용자 정보 전달.

#### 3) DB 현황 요약 API (`GET /api/admin/db_status`)
- **역할**: 화면 상단에 현재 DB 파일 및 테이블별 레코드 통계 정보 제공.
- **반환 데이터**:
  - `db_size_bytes`: 파일 크기 (바이트 및 읽기 쉬운 KB/MB 단위)
  - `last_modified`: 최종 파일 수정 시각
  - `journal_mode`: 현재 저널 모드 (`WAL`)
  - `table_counts`: `equipment`, `users`, `menus`, `audit_logs`, `access_logs` 등 주요 테이블 건수

#### 4) DB 백업 다운로드 API (`GET /api/admin/backup`)
- **역할**: 관리자가 요청 시 즉시 현재 시점의 완전한 DB 스냅샷 파일을 생성하여 다운로드 스트림으로 전송.
- **동작 흐름**:
  1. 관리자 권한 검증 (`check_menu_permission('backup_restore')`).
  2. 임시 디렉토리(Temp)에 `equipment_backup_YYYYMMDD_HHMMSS.db` 생성.
  3. 라이브 DB 커넥션을 열어 `live_conn.backup(temp_conn)` 수행.
  4. 보안 감사 로그(`log_audit`)에 백업 다운로드 행위 영구 기록.
  5. Flask `send_file(..., as_attachment=True, download_name=...)`로 클라이언트에 전송.

#### 5) DB 복원 실행 API (`POST /api/admin/restore`)
- **역할**: 관리자가 업로드한 `.db` 파일을 검증 후 현재 운영 DB에 안전하게 덮어쓰기 복원.
- **4중 안전 방어막 (Safety Guards)**:
  1. **확장자 및 파일 시그니처 검사**: 파일명이 `.db`인지 확인하고, 파일 바이너리 첫 16바이트가 `SQLite format 3\000`인지 정밀 검증.
  2. **SQLite 파일 무결성 검증**: 업로드된 임시 파일에 접속하여 `PRAGMA integrity_check;`를 실행하여 결과가 `ok`인지 검증 (손상된 파일 즉각 거부).
  3. **필수 스키마 검증**: `SELECT name FROM sqlite_master WHERE type='table'`을 조회하여 필수 테이블(`equipment`, `users`, `menus`, `role_menu_permissions` 등)이 모두 존재하는지 확인.
  4. **복원 직전 자동 백업 (Fail-Safe Rollback)**: 복원 직전 현재 라이브 DB를 `equipment_auto_backup_before_restore_YYYYMMDD_HHMMSS.db`로 강제 스냅샷 백업 생성하여 롤백 보장.
- **복원 적용**:
  - `upload_conn.backup(live_conn)`을 실행하여 라이브 DB에 원자적 반영.
  - 감사 로그 기록: 복원 수행 결과 및 자동 백업 파일명 기록.
  - 세션 정리: 데이터 무결성을 위해 `session.clear()` 후 안내 메시지와 함께 로그인 페이지로 리다이렉트 유도.

---

### 2-3. 프론트엔드 화면 설계 (`templates/backup_restore.html`)

- **상속**: `miniserver_frame.html` 기반, 반응형 Tailwind CSS 및 다크 모드 완전 지원.
- **주요 UI 섹션**:
  1. **페이지 헤더**: 관리자 센터 허브로 돌아가는 뒤로가기 링크 및 아이콘 타이틀.
  2. **DB 실시간 현황 카드 (3열 반응형)**:
     - 💾 파일 크기 및 저장 위치
     - 🕒 최종 갱신 일시 및 WAL 상태
     - 📊 테이블별 데이터 적재 건수 (장비, 회원, 감사 로그 등)
  3. **백업 다운로드 패널 (좌측/상단)**:
     - 즉각 다운로드 버튼 (`[ 📦 데이터베이스 백업 파일 다운로드 ]`)
     - 안내 가이드 (WAL 저널 병합 및 단일 스냅샷 보장 설명)
  4. **복원 패널 (우측/하단)**:
     - 주의사항 안내 배너 (기존 데이터 교체 경고 및 자동 백업 생성 안내)
     - Drag & Drop 및 파일 선택 인풋 (`.db` 전용)
     - 이중 확인 모달 (Human-in-the-Loop):
       - 복원 버튼 클릭 시 확인 모달 팝업.
       - "복원 시 현재 가동 중인 데이터가 교체됩니다. 복원 직전 안전 자동 백업이 생성됩니다. 진행하시겠습니까?" 문구와 명시적 확인 버튼.
     - 진행 중 프로그레스 스피너 오버레이.

---

## 3. 개발 및 검증 파이프라인 (Phase 계획)

- **페이즈 1**: 기획서 확정 및 Staging 개발 환경 셋업
  - `Staging/` 디렉토리에 격리된 소스 복사 (`Staging/app.py`, `Staging/templates/`)
  - 신규 템플릿 `Staging/templates/backup_restore.html` 생성
- **페이즈 2**: 백엔드 API 구현 (Rule 4-3 라인별 주석 원칙 준수)
  - `GET /api/admin/db_status` (DB 현황 요약)
  - `GET /api/admin/backup` (SQLite 온라인 백업 스트림)
  - `POST /api/admin/restore` (4중 검증 및 온라인 복원)
  - `init_db()` 메뉴 및 권한 확장
- **페이즈 3**: 프론트엔드 UI/UX 연동
  - `backup_restore.html` 마크업 및 비동기 Fetch/Upload 자바스크립트 구현
  - `admin_center.html` 카드 연동 확인
- **페이즈 4**: 정적 및 정성적 검증 (Validation)
  - Python 문법 및 3-Tier 메타 주석, 라인별 주석 전수 검사
  - HTML 태그 닫힘 및 Jinja 문법 무결성 검증
  - 모의 백업 파일 생성 및 무결성 검증 스크립트 실행
  - `VALIDATION_METHODOLOGY.md` 기반 검증 보고서 작성
- **페이즈 5**: 운영 병합 및 원격 반영 (Merge & Git Push)
  - 사용자 최종 승인 득한 후 Staging 코드를 운영 루트로 병합
  - `Staging/` 폴더 초기화 (Rule 7-3-3)
  - `PROPOSALS.md`, `ROADMAP.md`, `FEATURES.md` 최신화 (Rule 7-4)
  - Git Commit & Push 수행

---

## 4. 기대 효과 및 안전성 평가

- **데이터 영속성 확보**: 미니서버의 불시 하드웨어 고장이나 데이터베이스 손상 발생 시 수초 이내에 100% 원복 가능.
- **무정지 안전성**: SQLite 공식 온라인 백업 API를 활용하므로 WAL 저널 분실이나 트랜잭션 충돌 없는 무결성 백업 보장.
- **휴먼 에러 완벽 방어**: 복원 시 4중 방어막과 복원 직전 자동 백업을 강제하여, 잘못된 파일을 올리더라도 이전 상태로 무조건 롤백 가능한 안전망 구축.
