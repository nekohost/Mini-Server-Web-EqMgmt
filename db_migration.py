"""
================================================================================
[파일명]: Staging/db_migration.py
[역할]: 기존 1-Tier 단일 equipment 테이블을 3-Tier 계층 구조(Lineup Node -> Option -> Instance)로 안전하게 정방향 이관하는 DB 마이그레이션 모듈
[의존성 관계]:
  - 외부 모듈: sqlite3, os, json, datetime
  - 대상 DB: equipment.db (SQLite3 WAL 모드)
  - 관련 테이블: equipment (레거시), categories, manufacturers, lineup_nodes, equipment_options, equipments, equipments_audit_log
  - 역방향 스크립트: down_migration.py (장애 시 롤백용)
[변경 시 영향도]:
  - 테이블 DDL, 컬럼명, 트리 구조 매핑 로직 변경 시 백엔드 전체(app.py)의 ORM/쿼리 및 프론트엔드 장비 목록 조회에 직접 영향
================================================================================
"""

# [1] SQLite3 데이터베이스 연결 및 쿼리 실행을 위한 표준 내장 라이브러리 임포트
import sqlite3

# [2] DB 파일의 존재 유무 및 경로 탐색을 위한 표준 os 모듈 임포트
import os

# [3] 감사 로그(Audit Log) 메타데이터 직렬화를 위한 JSON 파싱 라이브러리 임포트
import json

# [4] 마이그레이션 실행 시각 및 백업 테이블 타임스탬프 생성을 위한 datetime 임포트
from datetime import datetime

# [5] 장비 관리 시스템의 기본 SQLite3 데이터베이스 파일 상대 경로 상수 정의
DB_PATH = 'equipment.db'


def run_migration():
    """
    [역할]: 기존 1-Tier 단일 장비 테이블(equipment)을 3-Tier 가변 깊이 모델 트리 구조로 무중단/무손실 정방향 마이그레이션합니다.
    [의존성 관계]:
      - SQLite 파일: equipment.db
      - 참조 마스터 테이블: categories, manufacturers
      - 생성 대상 테이블: lineup_nodes, equipment_options, equipments, equipments_audit_log
    [변경 시 영향도]:
      - 기존 데이터 손실 방지(Rule.md 제4-4조)를 위해 반드시 선행 백업 테이블을 생성한 후 이관 수행
      - 실패 시 모든 변경 사항을 즉시 ROLLBACK 처리하여 데이터 무결성 보장
    [반환값]:
      - bool: 마이그레이션 성공 여부 (True: 성공, False: 실패)
    """
    # [1] 데이터베이스 파일이 실제로 존재하는지 사전 검증
    if not os.path.exists(DB_PATH):
        # DB 파일이 없으면 에러 메시지를 출력하고 함수 조기 종료
        print(f"[오류] 데이터베이스 파일({DB_PATH})을 찾을 수 없습니다.")
        return False

    # [2] 콘솔에 마이그레이션 시작 시각 및 대상 DB 파일명 로깅
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] DB 마이그레이션 시작: {DB_PATH}")

    # [3] SQLite 데이터베이스 연결 수립 (동시성 락 방어를 위해 타임아웃 30초 설정)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)

    # [4] 컬럼명으로 데이터에 접근할 수 있도록 row_factory를 sqlite3.Row로 바인딩
    conn.row_factory = sqlite3.Row

    # [5] SQL 쿼리 실행을 위한 데이터베이스 커서(Cursor) 객체 생성
    cursor = conn.cursor()

    # [6] 마이그레이션 전체 작업을 원자적 트랜잭션으로 보호하기 위한 try-except 블록
    try:
        # [7] 동시 읽기/쓰기 성능 향상을 위해 저널 모드를 WAL(Write-Ahead Logging)로 전환
        cursor.execute("PRAGMA journal_mode = WAL;")

        # [8] 데이터베이스 비지(Busy) 상태 시 최대 30,000ms(30초) 동안 대기하도록 프래그마 설정
        cursor.execute("PRAGMA busy_timeout = 30000;")

        # ---------------------------------------------------------------------
        # 1단계: 기존 equipment 테이블 영구 백업 (Rule.md 제4-4조 데이터 보존 원칙 준수)
        # ---------------------------------------------------------------------
        # [9] 백업 테이블 이름에 부여할 고유 타임스탬프 문자열 생성 (YYYYMMDD_HHMMSS 포맷)
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')

        # [10] 고유 타임스탬프를 포함하는 백업 테이블 물리적 이름 정의
        backup_table_name = f"equipment_backup_{timestamp_str}"

        # [11] 기존 레거시 equipment 테이블이 존재하는지 sqlite_master 시스템 카탈로그 조회
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='equipment';")

        # [12] 조회 결과 단일 행을 인출하여 레거시 테이블 존재 여부 불리언(Boolean) 값 계산
        has_legacy_table = cursor.fetchone() is not None

        # [13] 기존 레거시 테이블이 존재하는 경우 백업 테이블 복제 생성 진행
        if has_legacy_table:
            # 백업 시작 콘솔 안내 출력
            print(f"[1/5] 기존 equipment 테이블 백업 생성: {backup_table_name}")

            # 기존 equipment 테이블의 전체 스키마 및 레코드를 복제하여 신규 백업 테이블 생성 (CTAS 쿼리)
            cursor.execute(f"CREATE TABLE {backup_table_name} AS SELECT * FROM equipment;")

            # 백업 테이블에 적재된 레코드 총 건수 확인
            cursor.execute(f"SELECT COUNT(*) FROM {backup_table_name};")

            # 단일 건수 값 추출
            legacy_count = cursor.fetchone()[0]

            # 백업 완료 및 보존 건수 출력
            print(f"      -> 백업 완료 ({legacy_count}건 보존됨)")
        else:
            # 레거시 테이블이 없을 경우 백업 건너뜀 안내 출력 및 카운트 0 초기화
            print("[1/5] 기존 equipment 테이블이 없어 백업 생성을 건너뜁니다.")
            legacy_count = 0

        # ---------------------------------------------------------------------
        # 2단계: 신규 3-Tier 스키마 DDL 생성
        # ---------------------------------------------------------------------
        # [14] 신규 스키마 테이블 생성 시작 안내 출력
        print("[2/5] 신규 3-Tier 스키마 DDL 생성 중...")

        # [15] Tier 1 ~ N 가변 깊이 트리 노드 테이블 (lineup_nodes) DDL 실행
        #      - 계층형 모델 트리: parent_id(부모 노드), category_id(카테고리), manufacturer_id(제조사)
        #      - UNIQUE 제약: 동일 부모 노드 아래 동일 모델명 중복 방지
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lineup_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                category_id INTEGER NOT NULL,
                manufacturer_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                depth INTEGER NOT NULL DEFAULT 1,
                status TEXT DEFAULT 'APPROVED',
                requested_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES lineup_nodes(id),
                FOREIGN KEY (category_id) REFERENCES categories(CategoryId),
                FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(ManufacturerId),
                UNIQUE(parent_id, name)
            );
        ''')

        # [16] Tier N+1 세부 옵션/스펙 조합 테이블 (equipment_options) DDL 실행
        #      - 특정 라인업 노드에 종속된 하위 스펙 사양(CPU/RAM/색상 등)을 JSON 형식으로 저장
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipment_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lineup_node_id INTEGER NOT NULL,
                option_name TEXT NOT NULL,
                specs_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'APPROVED',
                requested_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lineup_node_id) REFERENCES lineup_nodes(id)
            );
        ''')

        # [17] Tier N+2 개별 실물 장비 인스턴스 테이블 (equipments) DDL 실행
        #      - option_id를 참조하며, 시리얼넘버, 구매일, 소유자(user_id), 공개여부(is_public), 임시저장(is_draft) 등 관리
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                option_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                serial_number TEXT UNIQUE,
                purchase_date TEXT,
                status TEXT DEFAULT 'ACTIVE',
                memo TEXT,
                user_id INTEGER,
                is_public INTEGER DEFAULT 0,
                is_draft INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (option_id) REFERENCES equipment_options(id)
            );
        ''')

        # [18] (안전 가드) 이미 이전 버전에서 is_draft 컬럼 없이 equipments 테이블이 생성된 경우 자동 보정
        cursor.execute("PRAGMA table_info(equipments);")

        # 테이블 내 존재하는 모든 컬럼명 리스트 추출
        columns = [row['name'] for row in cursor.fetchall()]

        # 'is_draft' 컬럼이 없으면 ALTER TABLE로 안전하게 추가 (데이터 유실 없음)
        if 'is_draft' not in columns:
            cursor.execute("ALTER TABLE equipments ADD COLUMN is_draft INTEGER DEFAULT 0;")

        # [19] 장비 변경 및 이관 이력을 추적하기 위한 감사 로그 테이블 (equipments_audit_log) DDL 실행
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipments_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_by INTEGER,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipments(id)
            );
        ''')

        # ---------------------------------------------------------------------
        # 3단계: 조인(JOIN) 및 조회 성능 최적화를 위한 외래키 B-Tree 인덱스 3종 생성
        # ---------------------------------------------------------------------
        # [20] 인덱스 생성 시작 안내 출력
        print("[3/5] 외래키 B-Tree 인덱스 3종 생성 중...")

        # lineup_nodes 부모 노드 조인 최적화 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lineup_nodes_parent_id ON lineup_nodes(parent_id);")

        # equipment_options 라인업 노드 외래키 조회 최적화 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipment_options_lineup_node_id ON equipment_options(lineup_node_id);")

        # equipments 옵션 외래키 조회 최적화 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipments_option_id ON equipments(option_id);")

        # 인덱스 생성 완료 로그 출력
        print("      -> 인덱스 생성 완료 (idx_lineup_nodes_parent_id, idx_equipment_options_lineup_node_id, idx_equipments_option_id)")

        # ---------------------------------------------------------------------
        # 4단계: 정방향 레거시 데이터 3-Tier 이관 (Up Migration)
        # ---------------------------------------------------------------------
        # [21] 기존 레거시 데이터가 존재하고 레코드가 1건 이상인 경우 데이터 변환 이관 수행
        if has_legacy_table and legacy_count > 0:
            print("[4/5] 기존 레거시 데이터 3-Tier 이관 시작...")

            # 기존 레거시 equipment 테이블의 모든 행 인출
            cursor.execute("SELECT * FROM equipment;")
            legacy_rows = cursor.fetchall()

            # 성공적으로 이관된 레코드 수를 카운트하기 위한 변수 초기화
            migrated_count = 0

            # 각 레거시 행을 순회하며 3-Tier 구조로 매핑 변환
            for row in legacy_rows:
                # 카테고리명 추출 (None 시 '미분류' 대체 및 좌우 공백 제거)
                cat_name = (row['Category'] or '미분류').strip()

                # 제조사명 추출 (None 시 '미지정' 대체 및 좌우 공백 제거)
                mfg_name = (row['Manufacturer'] or '미지정').strip()

                # 모델명 추출 (ModelName -> Name 순서로 폴백, 없을 시 '기본 모델')
                model_name = (row['ModelName'] or row['Name'] or '기본 모델').strip()

                # 장비 개별 명칭 추출
                eq_name = (row['Name'] or '장비').strip()

                # [시리얼넘버 무결성 가드]: 빈 문자열("")은 NULL로 변환하여 SQLite UNIQUE 제약 충돌 방지
                serial_no = row['SerialNumber']
                if serial_no:
                    serial_no = serial_no.strip()
                    if serial_no == "":
                        serial_no = None
                else:
                    serial_no = None

                # 구매일자, 메모, 소유자 ID 바인딩
                purchase_date = row['PurchaseDate']
                memo = row['Memo']
                user_id = row['UserId']

                # 공개 여부(IsPublic), 생성시각, 수정시각 안전 추출 (컬럼 미존재 시 기본값)
                is_public = row['IsPublic'] if 'IsPublic' in row.keys() else 0
                created_at = row['CreatedAt'] if 'CreatedAt' in row.keys() else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                updated_at = row['UpdatedAt'] if 'UpdatedAt' in row.keys() else created_at

                # 4-1. 카테고리(Category) 마스터 매핑 또는 신규 자동 등록
                cursor.execute("SELECT CategoryId FROM categories WHERE Name = ?;", (cat_name,))
                cat_row = cursor.fetchone()
                if cat_row:
                    cat_id = cat_row['CategoryId']
                else:
                    cursor.execute("INSERT INTO categories (Name, IsApproved) VALUES (?, 1);", (cat_name,))
                    cat_id = cursor.lastrowid

                # 4-2. 제조사(Manufacturer) 마스터 매핑 또는 신규 자동 등록
                cursor.execute("SELECT ManufacturerId FROM manufacturers WHERE Name = ?;", (mfg_name,))
                mfg_row = cursor.fetchone()
                if mfg_row:
                    mfg_id = mfg_row['ManufacturerId']
                else:
                    cursor.execute("INSERT INTO manufacturers (Name, IsApproved) VALUES (?, 1);", (mfg_name,))
                    mfg_id = cursor.lastrowid

                # 4-3. Lineup Node 매핑/생성 (루트 모델 노드: depth=1, parent_id=NULL)
                #      - [NULL 중복 허용 버그 방어]: SQLite의 UNIQUE 제약에서 NULL 중복 허용 한계를 극복하기 위해 백엔드 사전 SELECT 검증
                cursor.execute("""
                    SELECT id FROM lineup_nodes 
                    WHERE parent_id IS NULL AND category_id = ? AND manufacturer_id = ? AND name = ?;
                """, (cat_id, mfg_id, model_name))
                node_row = cursor.fetchone()
                if node_row:
                    node_id = node_row['id']
                else:
                    cursor.execute("""
                        INSERT INTO lineup_nodes (parent_id, category_id, manufacturer_id, name, depth, status)
                        VALUES (NULL, ?, ?, ?, 1, 'APPROVED');
                    """, (cat_id, mfg_id, model_name))
                    node_id = cursor.lastrowid

                # 4-4. Equipment Option (기본 사양 스펙 조합 생성)
                cursor.execute("""
                    SELECT id FROM equipment_options 
                    WHERE lineup_node_id = ? AND option_name = '기본 사양';
                """, (node_id,))
                opt_row = cursor.fetchone()
                if opt_row:
                    opt_id = opt_row['id']
                else:
                    cursor.execute("""
                        INSERT INTO equipment_options (lineup_node_id, option_name, specs_json, status)
                        VALUES (?, '기본 사양', '{}', 'APPROVED');
                    """, (node_id,))
                    opt_id = cursor.lastrowid

                # 4-5. Equipments 실물 인스턴스 인서트 (시리얼 중복 안전 방어)
                if serial_no is not None:
                    # 동일 시리얼을 가진 레코드가 이미 이관되었는지 검증
                    cursor.execute("SELECT id FROM equipments WHERE serial_number = ?;", (serial_no,))
                    existing_eq = cursor.fetchone()
                    if existing_eq:
                        # 중복 시 데이터 유실을 막기 위해 레거시 ID를 접미사로 붙여 고유화
                        serial_no = f"{serial_no}_dup_{row['EquipmentId']}"

                # equipments 테이블에 장비 실물 행 삽입
                cursor.execute("""
                    INSERT INTO equipments (option_id, name, serial_number, purchase_date, status, memo, user_id, is_public, is_draft, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?, 0, ?, ?);
                """, (opt_id, eq_name, serial_no, purchase_date, memo, user_id, is_public, created_at, updated_at))

                # 방금 삽입된 신규 장비 ID 취득
                new_eq_id = cursor.lastrowid

                # 4-6. 마이그레이션 감사 로그(Audit Log) 기록
                cursor.execute("""
                    INSERT INTO equipments_audit_log (equipment_id, action_type, new_value, changed_by, changed_at)
                    VALUES (?, 'MIGRATED', ?, ?, ?);
                """, (new_eq_id, json.dumps({'origin': 'legacy_migration', 'legacy_id': row['EquipmentId']}), user_id, created_at))

                # 이관 카운트 증가
                migrated_count += 1

            # 이관 완료 통계 출력
            print(f"      -> {migrated_count}건의 장비 데이터 3-Tier 이관 완료.")
        else:
            # 이관 대상 레코드가 없을 경우 안내 출력
            print("[4/5] 이관할 기존 장비 데이터가 없습니다.")

        # ---------------------------------------------------------------------
        # 5단계: 트랜잭션 최종 커밋
        # ---------------------------------------------------------------------
        # [22] 모든 DDL 및 DML 작업을 DB에 영구 반영 (COMMIT)
        conn.commit()

        # [23] 마이그레이션 완료 안내 메시지 출력
        print("[5/5] 마이그레이션 커밋 완료! (정상 종료)")
        return True

    except Exception as e:
        # [24] 예외 발생 시 모든 작업을 롤백하여 DB를 마이그레이션 시작 전 상태로 안전하게 복원
        conn.rollback()

        # 치명적 오류 안내 및 예외 세부 정보 출력
        print(f"[치명적 오류] 마이그레이션 실패 (롤백 수행됨): {e}")
        return False
    finally:
        # [25] 커넥션 리소스 누수를 방지하기 위해 DB 연결 종료
        conn.close()


# [26] 명령줄 직접 실행 엔트리포인트
if __name__ == '__main__':
    run_migration()
