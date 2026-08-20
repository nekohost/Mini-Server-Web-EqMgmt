"""
=============================================================================
[제안-036] 가변 깊이 모델 트리 & 장비 아키텍처 역방향(Down) 롤백 스크립트
파일명: down_migration.py
작성일: 2026-08-19
관련 규정: Rule.md 제4조(DB 확장성 및 데이터 보존), 제5조(격리 개발 원칙)
=============================================================================
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = 'equipment.db'

def run_down_migration():
    """
    [역할]: 3-Tier 계층형 구조(equipments, equipment_options, lineup_nodes)의 데이터를 
           비상 시 구버전 1-Tier equipment 단일 테이블 형태로 안전하게 역방향 롤백(다운그레이드)합니다.
    [비가역성 경고 (Lossy Compression)]:
      - 3-Tier에서 세분화된 N차 분류 및 JSON 옵션 스펙은 1-Tier 단일 컬럼에 100% 매핑될 수 없습니다.
      - 따라서 N+1차 specs_json 정보는 Memo 컬럼에 "[옵션스펙 롤백 병합]: ..." 형태로 압축 보존됩니다.
    """
    if not os.path.exists(DB_PATH):
        print(f"[오류] 데이터베이스 파일({DB_PATH})을 찾을 수 없습니다.")
        return False

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚨 3-Tier -> 1-Tier 다운그레이드 롤백 시작: {DB_PATH}")
    print("[경고] 3-Tier의 N차 계층 구조 및 세부 JSON 옵션은 1-Tier Memo 컬럼으로 압축되어 정보의 구조적 손실이 발생합니다.")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA busy_timeout = 30000;")

        # 1. 3-Tier 테이블 존재 여부 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='equipments';")
        if cursor.fetchone() is None:
            print("[오류] 3-Tier 'equipments' 테이블이 존재하지 않아 롤백을 수행할 수 없습니다.")
            return False

        # 2. 롤백용 백업 테이블 생성 (선행 보존)
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        rollback_table_name = f"equipment_rollback_{timestamp_str}"
        print(f"[1/3] 롤백 복원 대상 테이블 생성: {rollback_table_name}")

        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {rollback_table_name} (
                EquipmentId INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Category TEXT,
                Manufacturer TEXT,
                ModelName TEXT,
                PurchaseDate TEXT,
                SerialNumber TEXT UNIQUE,
                Memo TEXT,
                UserId INTEGER,
                IsPublic INTEGER DEFAULT 0,
                CreatedAt TEXT,
                UpdatedAt TEXT
            );
        ''')

        # 3. 3-Tier 조인 쿼리를 통한 1-Tier 평탄화(Flattening) 추출
        print("[2/3] 3-Tier 계층 데이터 평탄화 및 압축 이관 중...")
        cursor.execute("""
            SELECT 
                e.id AS EquipmentId,
                e.name AS EquipmentName,
                e.serial_number AS SerialNumber,
                e.purchase_date AS PurchaseDate,
                e.memo AS Memo,
                e.user_id AS UserId,
                e.is_public AS IsPublic,
                e.created_at AS CreatedAt,
                e.updated_at AS UpdatedAt,
                opt.option_name AS OptionName,
                opt.specs_json AS SpecsJson,
                node.name AS ModelName,
                cat.name AS CategoryName,
                mfg.name AS ManufacturerName
            FROM equipments e
            JOIN equipment_options opt ON e.option_id = opt.id
            JOIN lineup_nodes node ON opt.lineup_node_id = node.id
            JOIN categories cat ON node.category_id = cat.CategoryId
            JOIN manufacturers mfg ON node.manufacturer_id = mfg.ManufacturerId;
        """)

        flattened_rows = cursor.fetchall()
        restored_count = 0

        for row in flattened_rows:
            # 옵션 및 스펙 정보를 압축하여 Memo에 첨부
            memo_parts = []
            if row['Memo']:
                memo_parts.append(row['Memo'])
            
            option_info = []
            if row['OptionName'] and row['OptionName'] != '기본 사양':
                option_info.append(f"옵션명: {row['OptionName']}")
            if row['SpecsJson'] and row['SpecsJson'] != '{}':
                option_info.append(f"스펙: {row['SpecsJson']}")
            
            if option_info:
                memo_parts.append(f"[3-Tier 롤백 병합] " + " | ".join(option_info))

            merged_memo = "\n".join(memo_parts) if memo_parts else None

            cursor.execute(f"""
                INSERT INTO {rollback_table_name} (
                    Name, Category, Manufacturer, ModelName, 
                    PurchaseDate, SerialNumber, Memo, UserId, IsPublic, CreatedAt, UpdatedAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                row['EquipmentName'],
                row['CategoryName'],
                row['ManufacturerName'],
                row['ModelName'],
                row['PurchaseDate'],
                row['SerialNumber'],
                merged_memo,
                row['UserId'],
                row['IsPublic'],
                row['CreatedAt'],
                row['UpdatedAt']
            ))
            restored_count += 1

        print(f"      -> {restored_count}건의 장비 데이터가 {rollback_table_name} 테이블로 안전하게 평탄화 복원되었습니다.")

        # 4. 트랜잭션 커밋
        conn.commit()
        print(f"[3/3] 롤백 프로세스 완료! (생성된 테이블: {rollback_table_name})")
        return True

    except Exception as e:
        conn.rollback()
        print(f"[치명적 오류] 롤백 실패 (트랜잭션 취소됨): {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    run_down_migration()
