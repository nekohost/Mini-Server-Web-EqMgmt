"""
=============================================================================
[제안-036] 가변 깊이 모델 트리 & 장비 아키텍처 정방향 DB 마이그레이션 스크립트
파일명: db_migration.py
작성일: 2026-08-19
관련 규정: Rule.md 제4조(DB 확장성 및 데이터 보존), 제5조(격리 개발 원칙)
=============================================================================
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = 'equipment.db'

def run_migration():
    """
    [역할]: 기존 1-Tier equipment 테이블을 3-Tier 계층 구조로 안전하게 마이그레이션합니다.
    [안전 장치]:
      1. DB Lock 방어 (busy_timeout 30초)
      2. 기존 데이터 백업 테이블 (equipment_backup_YYYYMMDD_HHMMSS) 선행 생성 (DROP 금지)
      3. 외래키 B-Tree 인덱스 3종 생성 (조인 성능 병목 방어)
      4. SQLite NULL 중복 허용 버그 방어를 위한 백엔드 2차 SELECT 검증
    """
    if not os.path.exists(DB_PATH):
        print(f"[오류] 데이터베이스 파일({DB_PATH})을 찾을 수 없습니다.")
        return False

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] DB 마이그레이션 시작: {DB_PATH}")
    
    # DB Lock 방어: 타임아웃 30초 설정
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # WAL 모드 및 busy_timeout 설정
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA busy_timeout = 30000;")

        # ---------------------------------------------------------------------
        # 1. 기존 equipment 테이블 영구 백업 (Rule.md 제4-2조 준수)
        # ---------------------------------------------------------------------
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_table_name = f"equipment_backup_{timestamp_str}"
        
        # 기존 테이블 존재 여부 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='equipment';")
        has_legacy_table = cursor.fetchone() is not None

        if has_legacy_table:
            print(f"[1/5] 기존 equipment 테이블 백업 생성: {backup_table_name}")
            cursor.execute(f"CREATE TABLE {backup_table_name} AS SELECT * FROM equipment;")
            cursor.execute(f"SELECT COUNT(*) FROM {backup_table_name};")
            legacy_count = cursor.fetchone()[0]
            print(f"      -> 백업 완료 ({legacy_count}건 보존됨)")
        else:
            print("[1/5] 기존 equipment 테이블이 없어 백업 생성을 건너뜁니다.")
            legacy_count = 0

        # ---------------------------------------------------------------------
        # 2. 신규 3-Tier 스키마 DDL 생성
        # ---------------------------------------------------------------------
        print("[2/5] 신규 3-Tier 스키마 DDL 생성 중...")

        # (기존 마스터 테이블: categories, manufacturers는 app.py에서 관리되며, 기존 구조를 따름)



        # 1 ~ N차 노드: lineup_nodes (가변 트리)
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

        # N+1차 옵션 조합: equipment_options
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

        # 장비 본체(인스턴스): equipments
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (option_id) REFERENCES equipment_options(id)
            );
        ''')

        # 감사 로그: equipments_audit_log
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
        # 3. 조인(JOIN) 성능 최적화를 위한 외래키 B-Tree 인덱스 생성
        # ---------------------------------------------------------------------
        print("[3/5] 외래키 B-Tree 인덱스 3종 생성 중...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lineup_nodes_parent_id ON lineup_nodes(parent_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipment_options_lineup_node_id ON equipment_options(lineup_node_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipments_option_id ON equipments(option_id);")
        print("      -> 인덱스 생성 완료 (idx_lineup_nodes_parent_id, idx_equipment_options_lineup_node_id, idx_equipments_option_id)")

        # ---------------------------------------------------------------------
        # 4. 정방향 데이터 마이그레이션 (Up Migration)
        # ---------------------------------------------------------------------
        if has_legacy_table and legacy_count > 0:
            print("[4/5] 기존 레거시 데이터 3-Tier 이관 시작...")
            cursor.execute("SELECT * FROM equipment;")
            legacy_rows = cursor.fetchall()

            migrated_count = 0
            for row in legacy_rows:
                cat_name = (row['Category'] or '미분류').strip()
                mfg_name = (row['Manufacturer'] or '미지정').strip()
                model_name = (row['ModelName'] or row['Name'] or '기본 모델').strip()
                eq_name = (row['Name'] or '장비').strip()
                serial_no = row['SerialNumber']
                purchase_date = row['PurchaseDate']
                memo = row['Memo']
                user_id = row['UserId']
                is_public = row['IsPublic'] if 'IsPublic' in row.keys() else 0
                created_at = row['CreatedAt'] if 'CreatedAt' in row.keys() else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                updated_at = row['UpdatedAt'] if 'UpdatedAt' in row.keys() else created_at

                # 4-1. Category 매핑/생성
                cursor.execute("SELECT CategoryId FROM categories WHERE Name = ?;", (cat_name,))
                cat_row = cursor.fetchone()
                if cat_row:
                    cat_id = cat_row['CategoryId']
                else:
                    cursor.execute("INSERT INTO categories (Name, IsApproved) VALUES (?, 1);", (cat_name,))
                    cat_id = cursor.lastrowid

                # 4-2. Manufacturer 매핑/생성
                cursor.execute("SELECT ManufacturerId FROM manufacturers WHERE Name = ?;", (mfg_name,))
                mfg_row = cursor.fetchone()
                if mfg_row:
                    mfg_id = mfg_row['ManufacturerId']
                else:
                    cursor.execute("INSERT INTO manufacturers (Name, IsApproved) VALUES (?, 1);", (mfg_name,))
                    mfg_id = cursor.lastrowid

                # 4-3. Lineup Node 매핑/생성 (루트 노드: depth=1, parent_id=NULL)
                # [NULL 중복 락 방어] SQLite의 NULL 중복 허용 한계를 극복하기 위해 백엔드 사전 조회
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

                # 4-4. Equipment Option (기본 스펙 조합 생성)
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

                # 4-5. Equipments 인스턴스 인서트 (시리얼 중복 방어)
                if serial_no:
                    cursor.execute("SELECT id FROM equipments WHERE serial_number = ?;", (serial_no,))
                    existing_eq = cursor.fetchone()
                    if existing_eq:
                        # 이미 이관된 시리얼인 경우 건너뜀
                        continue

                cursor.execute("""
                    INSERT INTO equipments (option_id, name, serial_number, purchase_date, status, memo, user_id, is_public, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?);
                """, (opt_id, eq_name, serial_no, purchase_date, memo, user_id, is_public, created_at, updated_at))
                
                new_eq_id = cursor.lastrowid
                
                # 감사 로그 생성
                cursor.execute("""
                    INSERT INTO equipments_audit_log (equipment_id, action_type, new_value, changed_by, changed_at)
                    VALUES (?, 'MIGRATED', ?, ?, ?);
                """, (new_eq_id, json.dumps({'origin': 'legacy_migration', 'legacy_id': row['EquipmentId']}), user_id, created_at))

                migrated_count += 1

            print(f"      -> {migrated_count}건의 장비 데이터 3-Tier 이관 완료.")
        else:
            print("[4/5] 이관할 기존 장비 데이터가 없습니다.")

        # ---------------------------------------------------------------------
        # 5. 트랜잭션 최종 커밋
        # ---------------------------------------------------------------------
        conn.commit()
        print(f"[5/5] 마이그레이션 커밋 완료! (정상 종료)")
        return True

    except Exception as e:
        conn.rollback()
        print(f"[치명적 오류] 마이그레이션 실패 (롤백 수행됨): {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    run_migration()
