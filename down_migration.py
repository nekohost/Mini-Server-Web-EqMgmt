"""
================================================================================
[파일명]: Staging/down_migration.py
[역할]: 3-Tier 계층형 구조(Lineup Node -> Option -> Instance)의 데이터를 비상 시 구버전 1-Tier equipment 단일 테이블로 안전하게 역방향 롤백(다운그레이드)하는 비상 복원 모듈
[의존성 관계]:
  - 외부 모듈: sqlite3, os, json, datetime
  - 대상 DB: equipment.db (SQLite3 WAL 모드)
  - 참조 테이블: equipments, equipment_options, lineup_nodes, categories, manufacturers
  - 생성 테이블: equipment_rollback_YYYYMMDD_HHMMSS
  - 정방향 스크립트: db_migration.py
[변경 시 영향도]:
  - 3-Tier의 N차 계층 구조와 JSON 스펙 데이터가 1-Tier의 단일 Memo 컬럼으로 압축 병합되므로 구조적 손실(Lossy)이 발생함
  - 비상 상황에서만 제한적으로 사용되어야 하며, 운영 코드 다운그레이드 시 데이터 보존의 최종 안전망 역할
================================================================================
"""

# [1] SQLite3 데이터베이스 연결 및 쿼리 처리를 위한 표준 내장 모듈 임포트
import sqlite3

# [2] DB 파일 유효성 검증 및 파일 시스템 접근을 위한 os 모듈 임포트
import os

# [3] JSON 직렬화 및 파싱 처리를 위한 내장 json 모듈 임포트
import json

# [4] 롤백 실행 시각 및 타임스탬프 기반 테이블 이름 생성을 위한 datetime 임포트
from datetime import datetime

# [5] SQLite3 데이터베이스 파일 상대 경로 상수 정의
DB_PATH = 'equipment.db'


def run_down_migration():
    """
    [역할]: 3-Tier 계층형 구조의 데이터를 조인(JOIN)하여 1-Tier 단일 테이블(equipment_rollback_YYYYMMDD_HHMMSS)로 평탄화(Flattening) 복원합니다.
    [의존성 관계]:
      - SQLite 파일: equipment.db
      - 소스 테이블: equipments, equipment_options, lineup_nodes, categories, manufacturers
      - 타깃 테이블: equipment_rollback_YYYYMMDD_HHMMSS
    [변경 시 영향도]:
      - 기존 3-Tier 테이블을 DROP하지 않고 복원 전용 신규 백업 테이블을 생성하여 기존 데이터의 100% 안전 보존(Rule.md 제4-4조 준수)
    [비가역성 경고 (Lossy Compression)]:
      - N차 트리 노드와 JSON 옵션 스펙은 1-Tier 단일 컬럼에 1:1 매핑되지 않으므로 Memo 컬럼에 "[3-Tier 롤백 병합]: ..." 형태로 압축 보존됩니다.
    [반환값]:
      - bool: 롤백 성공 여부 (True: 성공, False: 실패)
    """
    # [1] 데이터베이스 파일 존재 유무 사전 검증
    if not os.path.exists(DB_PATH):
        # 파일이 없으면 에러 메시지를 콘솔에 출력하고 함수 조기 종료
        print(f"[오류] 데이터베이스 파일({DB_PATH})을 찾을 수 없습니다.")
        return False

    # [2] 롤백 시작 로그 및 비가역성 안내 경고 메시지 출력
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚨 3-Tier -> 1-Tier 다운그레이드 롤백 시작: {DB_PATH}")
    print("[경고] 3-Tier의 N차 계층 구조 및 세부 JSON 옵션은 1-Tier Memo 컬럼으로 압축되어 정보의 구조적 손실이 발생합니다.")

    # [3] SQLite3 DB 연결 수립 (동시성 락 방어를 위해 타임아웃 30초 지정)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)

    # [4] 컬럼명을 키로 사용하는 Row 객체로 결과 반환 설정
    conn.row_factory = sqlite3.Row

    # [5] SQL 쿼리 실행용 커서 객체 생성
    cursor = conn.cursor()

    # [6] 롤백 트랜잭션의 원자성(All-or-Nothing) 보장을 위한 try-except 블록
    try:
        # [7] 동시성 성능 향상을 위한 WAL 저널 모드 설정
        cursor.execute("PRAGMA journal_mode = WAL;")

        # [8] Busy 상태 대기 시간 30초 설정
        cursor.execute("PRAGMA busy_timeout = 30000;")

        # ---------------------------------------------------------------------
        # 1단계: 3-Tier 소스 테이블 존재 여부 확인
        # ---------------------------------------------------------------------
        # [9] 3-Tier의 핵심 테이블인 'equipments'가 sqlite_master 카탈로그에 존재하는지 조회
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='equipments';")

        # [10] 테이블이 존재하지 않는 경우 롤백 대상이 없으므로 중단
        if cursor.fetchone() is None:
            print("[오류] 3-Tier 'equipments' 테이블이 존재하지 않아 롤백을 수행할 수 없습니다.")
            return False

        # ---------------------------------------------------------------------
        # 2단계: 롤백 복원 대상 1-Tier 백업 테이블 생성 (선행 보존)
        # ---------------------------------------------------------------------
        # [11] 충돌 없는 고유 테이블명을 위한 타임스탬프 문자열 생성
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')

        # [12] 롤백 복원 테이블 물리적 명칭 정의
        rollback_table_name = f"equipment_rollback_{timestamp_str}"
        print(f"[1/3] 롤백 복원 대상 테이블 생성: {rollback_table_name}")

        # [13] 구버전 1-Tier 단일 장비 테이블 스키마 DDL 실행
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

        # ---------------------------------------------------------------------
        # 3단계: 3-Tier 4중 조인 쿼리를 통한 1-Tier 평탄화(Flattening) 추출 및 적재
        # ---------------------------------------------------------------------
        # [14] 데이터 평탄화 이관 시작 안내 출력
        print("[2/3] 3-Tier 계층 데이터 평탄화 및 압축 이관 중...")

        # [15] equipments -> equipment_options -> lineup_nodes -> categories & manufacturers 4중 JOIN 쿼리 실행
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

        # [16] 조인된 전체 평탄화 레코드 세트 취득
        flattened_rows = cursor.fetchall()

        # [17] 복원된 총 레코드 수 카운터 변수 초기화
        restored_count = 0

        # [18] 각 행을 순회하며 계층형 옵션/스펙 정보를 단일 Memo 컬럼으로 병합 가공
        for row in flattened_rows:
            # 메모 조각들을 보관할 리스트 초기화
            memo_parts = []

            # 기존 장비 자체의 메모가 존재하는 경우 우선 추가
            if row['Memo']:
                memo_parts.append(row['Memo'])

            # 3-Tier 세부 옵션 및 스펙 정보를 압축 텍스트로 가공
            option_info = []
            # 기본 사양이 아닌 커스텀 옵션명이 있는 경우 포함
            if row['OptionName'] and row['OptionName'] != '기본 사양':
                option_info.append(f"옵션명: {row['OptionName']}")

            # 빈 JSON('{}')이 아닌 세부 스펙 속성이 있는 경우 포함
            if row['SpecsJson'] and row['SpecsJson'] != '{}':
                option_info.append(f"스펙: {row['SpecsJson']}")

            # 옵션/스펙 정보가 존재할 경우 메모 블록에 식별 헤더와 함께 추가
            if option_info:
                memo_parts.append(f"[3-Tier 롤백 병합] " + " | ".join(option_info))

            # 줄바꿈 문자로 연결하여 최종 통합 메모 문자열 완성
            merged_memo = "\n".join(memo_parts) if memo_parts else None

            # [19] 1-Tier 롤백 복원 테이블에 평탄화된 단일 행 삽입 실행
            cursor.execute(f"""
                INSERT INTO {rollback_table_name} (
                    Name, Category, Manufacturer, ModelName, 
                    PurchaseDate, SerialNumber, Memo, UserId, IsPublic, CreatedAt, UpdatedAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                row['EquipmentName'],       # 장비명 바인딩
                row['CategoryName'],        # 조인된 카테고리명 바인딩
                row['ManufacturerName'],    # 조인된 제조사명 바인딩
                row['ModelName'],           # 조인된 모델명 바인딩
                row['PurchaseDate'],        # 구매일자 바인딩
                row['SerialNumber'],        # 시리얼넘버 바인딩
                merged_memo,                # 압축 병합된 메모 텍스트 바인딩
                row['UserId'],              # 소유자 ID 바인딩
                row['IsPublic'],            # 공개 여부 플래그 바인딩
                row['CreatedAt'],           # 생성시각 바인딩
                row['UpdatedAt']            # 수정시각 바인딩
            ))

            # 복원 건수 증가
            restored_count += 1

        # [20] 복원 결과 통계 로그 출력
        print(f"      -> {restored_count}건의 장비 데이터가 {rollback_table_name} 테이블로 안전하게 평탄화 복원되었습니다.")

        # ---------------------------------------------------------------------
        # 4단계: 트랜잭션 커밋
        # ---------------------------------------------------------------------
        # [21] 롤백 생성 작업을 DB에 영구 반영 (COMMIT)
        conn.commit()

        # [22] 완료 안내 메시지 출력
        print(f"[3/3] 롤백 프로세스 완료! (생성된 테이블: {rollback_table_name})")
        return True

    except Exception as e:
        # [23] 예외 발생 시 모든 작업을 롤백하여 DB 상태 원복
        conn.rollback()

        # 치명적 오류 메시지 출력
        print(f"[치명적 오류] 롤백 실패 (트랜잭션 취소됨): {e}")
        return False
    finally:
        # [24] 데이터베이스 연결 자원 반납
        conn.close()


# [25] 명령줄 직접 실행 엔트리포인트
if __name__ == '__main__':
    run_down_migration()
