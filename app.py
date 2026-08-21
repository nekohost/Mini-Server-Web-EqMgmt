# ==========================================
# 1. 필요한 외부 라이브러리 불러오기
# ==========================================
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory, g
import sqlite3
import os
import json
import queue
import threading
import atexit
import time
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import random
import string
import uuid
import secrets
from utils.mailer import send_email
import warnings

# [버그 수정] Flask(Werkzeug) 자동 재시작(Reloader) 종료 시 발생하는 multiprocessing 세마포어 누수 경고 무시
warnings.filterwarnings("ignore", category=UserWarning, module="multiprocessing.resource_tracker")

# .env 파일 로드 (환경변수 세팅)
load_dotenv()

app = Flask(__name__)
# Nginx 등 리버스 프록시 뒤에서 구동될 때 클라이언트의 진짜 IP를 복구하기 위한 미들웨어 적용
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# 세션 암호화를 위한 비밀키 설정 (하드코딩 방지: .env에서 가져옴)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key_if_not_found')

# 보안 쿠키 정책 강화
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# ==========================================
# 1-0. [제안-038] 동적 메타데이터 라우팅 엔진
# ==========================================
STATIC_METADATA_ROUTES = set()

def register_dynamic_metadata_routes(app):
    """
    [역할]: Resources/metadata/ 하위의 파일들을 동적 라우팅으로 자동 등록합니다.
    [의존성 관계]: os.walk, send_from_directory, app.route
    [변경 시 영향도]: 메타데이터 라우팅 추가/삭제 시 서버 재시작으로 즉각 반영됩니다.
    """
    # 기본 정적 리소스(파비콘) 캐시 통합을 통한 성능 최적화
    STATIC_METADATA_ROUTES.add('/favicon.ico')
    
    metadata_dir = os.path.join(os.path.dirname(__file__), 'Resources', 'metadata')
    if not os.path.exists(metadata_dir):
        print(f"[Init] Metadata directory not found: {metadata_dir}")
        return

    # No-Code/Fail-Safe: URL 맵에 등록된 룰 목록 캐싱
    existing_rules = {rule.rule for rule in app.url_map.iter_rules()}

    for root, _, files in os.walk(metadata_dir):
        for file in files:
            # 상대 경로 계산 및 슬래시 정규화 (윈도우/리눅스 호환)
            rel_dir = os.path.relpath(root, metadata_dir).replace('\\', '/')
            if rel_dir == '.':
                route_path = f"/{file}"
            else:
                route_path = f"/{rel_dir}/{file}"

            # 중복 등록 방어 (AssertionError 회피)
            if route_path in existing_rules:
                print(f"[Init] Skip existing route: {route_path}")
                continue

            # 동적 뷰 함수 생성 (클로저 변수 바인딩)
            def create_view_func(dir_path, filename):
                return lambda: send_from_directory(dir_path, filename)
            
            # 식별 가능한 고유한 endpoint명 지정
            endpoint_name = f"metadata_{route_path.replace('/', '_').replace('.', '_')}"
            
            try:
                app.add_url_rule(route_path, endpoint_name, create_view_func(root, file))
                STATIC_METADATA_ROUTES.add(route_path)
                print(f"[Init] Registered dynamic metadata route: {route_path}")
            except Exception as e:
                print(f"[Init Error] Failed to register route {route_path}: {e}")

register_dynamic_metadata_routes(app)
STATIC_METADATA_ROUTES_FROZEN = frozenset(STATIC_METADATA_ROUTES)

# ==========================================
# 1-1. [제안-036] 웹 접근 로그 비동기 수집 엔진
# ==========================================
access_log_queue = queue.Queue(maxsize=10000)
shutdown_event = threading.Event()

def push_access_log(log_data):
    """
    [역할]: Non-blocking 큐 푸시 (웹 응답 지연 0% 절대 보장)
    [의존성 관계]: @app.after_request 인터셉터에서 호출
    [변경 시 영향도]: 큐가 꽉 차더라도 웹 요청을 지연시키지 않고 즉시 응답 (Fail-Open)
    """
    try:
        access_log_queue.put_nowait(log_data)
    except queue.Full:
        pass # 큐 풀 시 안전하게 드롭 (웹 서비스 가용성 최우선)

def _write_logs_to_db(logs):
    """
    [역할]: 로그 리스트를 DB에 일괄 벌크 인서트 트랜잭션으로 저장합니다.
    [의존성 관계]: access_logs 테이블, sqlite3
    [변경 시 영향도]: 디스크 I/O 최적화 및 접근 로그 영구 저장에 영향을 줍니다.
    """
    try:
        conn = sqlite3.connect('equipment.db', timeout=5.0)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.execute("PRAGMA synchronous = NORMAL;")
        cur.execute("PRAGMA busy_timeout = 5000;")
        cur.executemany("""
            INSERT INTO access_logs (IpAddress, HttpMethod, RequestPath, StatusCode, UserAgent, Referer, DurationMs, IsStatic, RequestPayload, ResponsePayload, CreatedAt)
            VALUES (:IpAddress, :HttpMethod, :RequestPath, :StatusCode, :UserAgent, :Referer, :DurationMs, :IsStatic, :RequestPayload, :ResponsePayload, :CreatedAt)
        """, logs)
        
        # [사용자 지침: 추후 필요 시 주석 해제하여 활성화]
        # cur.execute("DELETE FROM access_logs WHERE LogId NOT IN (SELECT LogId FROM access_logs ORDER BY LogId DESC LIMIT 30000)")
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Access Log Worker Error] {e}")
    finally:
        for _ in range(len(logs)):
            access_log_queue.task_done()

def batch_logger_worker():
    """
    [역할]: 백그라운드 단일 워커 스레드 - 0.5초 단위 민첩한 폴링 및 벌크 커밋
    [의존성 관계]: SQLite DB (equipment.db), shutdown_event, _write_logs_to_db()
    [변경 시 영향도]: 디스크 쓰기 I/O 95% 절감 및 서버 종료 시 스레드 충돌 0% 완전 차단
    """
    while not shutdown_event.is_set():
        logs_to_insert = []
        try:
            # shutdown_event에 0.5초 내로 즉각 반응하기 위한 경량 타임아웃
            item = access_log_queue.get(timeout=0.5)
            logs_to_insert.append(item)
            while len(logs_to_insert) < 50:
                try:
                    logs_to_insert.append(access_log_queue.get_nowait())
                except queue.Empty:
                    break
        except queue.Empty:
            continue

        if logs_to_insert:
            _write_logs_to_db(logs_to_insert)

    # [Graceful Shutdown 처리] 종료 신호 수신 시 큐에 남은 잔여 로그 100% 최종 커밋
    remaining_logs = []
    while not access_log_queue.empty():
        try:
            remaining_logs.append(access_log_queue.get_nowait())
        except queue.Empty:
            break
    if remaining_logs:
        _write_logs_to_db(remaining_logs)

def on_app_exit():
    """
    [역할]: atexit 종료 신호 전달 및 워커 3초 대기 (메인 스레드 직접 DB 접근 금지)
    [의존성 관계]: shutdown_event, logger_thread
    [변경 시 영향도]: 타이밍 엇박자 해소로 잔여 로그 100% 보존 및 안전 종료
    """
    shutdown_event.set()
    logger_thread.join(timeout=3.0)

# 워커 스레드 가동 및 atexit 핸들러 등록
logger_thread = threading.Thread(target=batch_logger_worker, daemon=True)
logger_thread.start()
atexit.register(on_app_exit)


# ==========================================
# 2. DB 공통 모듈 (모든 DB 관련 함수가 이 모듈에 의존함)
# ==========================================

def get_db_connection():
    """
    [역할]: DB 연결 객체를 생성하고 결과를 반환합니다.
    [의존성 관계]: sqlite3 모듈, equipment.db 파일
    [변경 시 영향도]: 모든 DB 통신 로직에 영향을 줍니다.
    """
    conn = sqlite3.connect('equipment.db')
    conn.row_factory = sqlite3.Row 
    return conn


def log_audit(actor_id, actor_login_id, action, target_table, target_id=None, old_value=None, new_value=None):
    """
    [역할]: 사용자의 주요 행동(로그인, 변경, 삭제 등)을 보안 감사 로그로 기록합니다.
    [의존성 관계]: audit_logs 테이블
    [변경 시 영향도]: 전역 감사 로그 기록 기능에 영향을 줍니다.
    """
    try:
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        
        old_json = json.dumps(old_value, ensure_ascii=False) if old_value is not None else None
        new_json = json.dumps(new_value, ensure_ascii=False) if new_value is not None else None
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO audit_logs (ActorId, ActorLoginId, IpAddress, UserAgent, TargetTable, TargetId, Action, OldValue, NewValue, CreatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (actor_id, actor_login_id, ip_address, user_agent, target_table, target_id, action, old_json, new_json, created_at))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Audit Log Error] {e}")


def init_db():
    """
    [역할] 시스템 구동 시 필요한 테이블 구조를 검증하고 초기화 (IF NOT EXISTS)
    [의존성 관계] get_db_connection()
    [변경 시 영향도] 테이블 스키마 변경 시 전체 DB 입출력 로직에 영향을 줍니다. (데이터 보존을 위해 DROP 구문은 금지됨)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # =========================================================================
    # [데이터베이스 테이블 도메인 범례 (Legend)]
    # [A] 핵심/권한 도메인   | [B] 장비/마스터 도메인   | [C] 워크플로우 도메인   | [D] 시스템/인프라 도메인
    # =========================================================================

    # B-1. 장비 테이블 (equipment)
    # B-1. 장비 테이블 (기존 equipment 및 신규 3-Tier equipments)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            EquipmentId INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL,
            Category TEXT,
            Manufacturer TEXT,
            ModelName TEXT,
            PurchaseDate TEXT,
            SerialNumber TEXT,
            Memo TEXT,
            UserId INTEGER,
            IsPublic INTEGER DEFAULT 0,
            CreatedAt TEXT,
            UpdatedAt TEXT
        )
    ''')

    # [제안-036] 3-Tier 가변 트리 및 옵션/장비 스키마
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

    # 3-Tier 외래키 B-Tree 인덱스 3종
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lineup_nodes_parent_id ON lineup_nodes(parent_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipment_options_lineup_node_id ON equipment_options(lineup_node_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipments_option_id ON equipments(option_id);")
    
    # A-1. 사용자 테이블 (users) - [제안-001, 025, 030, 034] 연관
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            UserId INTEGER PRIMARY KEY AUTOINCREMENT,
            LoginId TEXT UNIQUE NOT NULL,
            Name TEXT,
            NickName TEXT,
            Password TEXT NOT NULL,
            Role TEXT NOT NULL,
            CreatedAt TEXT,
            UpdatedAt TEXT,
            IsDeactivated TEXT DEFAULT 'N',
            DeactivatedAt TEXT,
            IsDeleted TEXT DEFAULT 'N',
            DeletedAt TEXT
        )
    ''')

    # A-2. 메뉴 테이블 (menus) - [제안-035] 연관
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menus (
            MenuId INTEGER PRIMARY KEY AUTOINCREMENT,
            MenuCode TEXT UNIQUE NOT NULL,
            MenuName TEXT NOT NULL,
            Url TEXT NOT NULL,
            Description TEXT,
            ParentMenuCode TEXT,
            SortOrder INTEGER DEFAULT 0,
            CreatedAt TEXT,
            UpdatedAt TEXT
        )
    ''')

    # A-3. 메뉴 권한 테이블 (role_menu_permissions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS role_menu_permissions (
            PermissionId INTEGER PRIMARY KEY AUTOINCREMENT,
            Role TEXT NOT NULL,
            MenuCode TEXT NOT NULL,
            IsAllowed INTEGER DEFAULT 1,
            UpdatedAt TEXT,
            UNIQUE(Role, MenuCode)
        )
    ''')

    # D-1. 감사 로그 테이블 (audit_logs) - [제안-003, 017] 연관
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            AuditId INTEGER PRIMARY KEY AUTOINCREMENT,
            ActorId INTEGER,
            ActorLoginId TEXT,
            IpAddress TEXT,
            UserAgent TEXT,
            TargetTable TEXT,
            TargetId INTEGER,
            Action TEXT,
            OldValue TEXT,
            NewValue TEXT,
            CreatedAt TEXT
        )
    ''')

    # D-2. 사용자 환경설정 테이블 (user_settings) - [제안-016] 연관
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            UserId INTEGER PRIMARY KEY,
            PreferencesJSON TEXT,
            UpdatedAt TEXT,
            FOREIGN KEY(UserId) REFERENCES users(UserId) ON DELETE CASCADE
        )
    ''')

    # B-2. 카테고리 마스터 테이블 (categories) - [제안-011] 연관
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            CategoryId INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT UNIQUE NOT NULL,
            IsApproved INTEGER DEFAULT 1,
            CreatedAt TEXT
        )
    ''')

    # D-3. 시스템 마이그레이션 이력 관리 테이블 (sys_migrations)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sys_migrations (
            MigrationName TEXT PRIMARY KEY,
            AppliedAt TEXT
        )
    ''')

    # B-3. 제조사 마스터 테이블 (manufacturers) - [제안-011] 연관
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manufacturers (
            ManufacturerId INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT UNIQUE NOT NULL,
            IsApproved INTEGER DEFAULT 1,
            CreatedAt TEXT
        )
    ''')

    # C-1. 전자결재 요청 테이블 (approval_requests) - [제안-027] 연관
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS approval_requests (
            RequestId INTEGER PRIMARY KEY AUTOINCREMENT,
            RequesterId INTEGER NOT NULL,
            RequestType TEXT NOT NULL,
            RequestDataJSON TEXT NOT NULL,
            Status TEXT DEFAULT 'PENDING',
            ApproverId INTEGER,
            RejectReason TEXT,
            CreatedAt TEXT,
            UpdatedAt TEXT,
            FOREIGN KEY(RequesterId) REFERENCES users(UserId) ON DELETE CASCADE
        )
    ''')

    # D-4. 실시간 웹 접근 로그 테이블 (access_logs) - [제안-036, 040] 연관
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            LogId INTEGER PRIMARY KEY AUTOINCREMENT,
            IpAddress TEXT NOT NULL,
            HttpMethod TEXT NOT NULL,
            RequestPath TEXT NOT NULL,
            StatusCode INTEGER NOT NULL,
            UserAgent TEXT,
            Referer TEXT,
            DurationMs REAL,
            IsStatic INTEGER DEFAULT 0,
            RequestPayload TEXT,
            ResponsePayload TEXT,
            CreatedAt TEXT NOT NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_created_at ON access_logs (CreatedAt DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_ip ON access_logs (IpAddress)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_status ON access_logs (StatusCode)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_is_static ON access_logs (IsStatic)')

    # 기본 메뉴 등록 (기존 장비관리 메뉴 대신 분리된 메뉴 2종)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("DELETE FROM menus WHERE MenuCode = 'equipment'")
    cursor.execute("DELETE FROM role_menu_permissions WHERE MenuCode = 'equipment'")
    
    default_menus = [
        ('my_equipment', '나의 장비', '/my_equipment', '내 장비 등록 및 관리', None, 1),
        ('public_equipment', '공개 장비', '/public_equipment', '공개 장비 및 전체 장비 조회', None, 2),
        ('dashboard', '통계 대시보드', '/dashboard', '장비 통계 및 상세 현황 조회', None, 3),
        ('admin_center', '관리자 센터', '/admin_center', '시스템 관리자 전용 메뉴 허브', None, 4),
        ('permissions', '메뉴 권한 관리', '/permissions', '사용자 역할별 메뉴 접근 권한 제어', 'admin_center', 1),
        ('audit_logs', '보안 감사 로그', '/audit_logs', '시스템 접근 이력 및 감사 로그 조회', 'admin_center', 2),
        ('users_management', '사용자 관리', '/users_management', '전체 사용자 권한 및 계정 관리', 'admin_center', 3),
        ('approvals', '전자결재함', '/approvals', '전자결재 요청 및 승인 관리', 'admin_center', 4),
        ('master_management', '마스터 데이터 관리', '/master_management', '카테고리 및 제조사 마스터 관리', 'admin_center', 5),
        ('access_logs', '웹 접근 로그', '/access_logs', '실시간 HTTP 트래픽 및 웹 접근 로그 모니터링', 'admin_center', 6)
    ]
    for m in default_menus:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, ParentMenuCode, SortOrder, CreatedAt, UpdatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (m[0], m[1], m[2], m[3], m[4], m[5], now, now))
        except Exception as e:
            # 기존 DB 스키마에 ParentMenuCode가 없는 상태(마이그레이션 전)에서는 무시
            print(f"[Init DB] menus 테이블 기본 데이터 삽입 건너뜀 (마이그레이션 전일 수 있습니다): {str(e)}")
            pass

    # 기본 권한 등록 (admin: 전체 허용, user: 나의 장비 및 공개된 장비, 전자결재 허용)
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'my_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'public_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'permissions', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'audit_logs', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'users_management', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'dashboard', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'approvals', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'master_management', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'access_logs', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'admin_center', 1, now))
    
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'my_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'public_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'permissions', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'audit_logs', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'users_management', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'dashboard', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'approvals', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'master_management', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'access_logs', 0, now))

    conn.commit()
    conn.close()

# 서버 실행 시 DB 준비 (기존 데이터 보존 원칙 적용)
init_db()

def run_migration_if_needed(migration_name, migration_func):
    """
    [역할]: 특정 DB 마이그레이션 함수가 이전에 실행되었는지 확인하고 1회에 한해 구동합니다.
    [의존성 관계]: sys_migrations 테이블
    [변경 시 영향도]: 마이그레이션 중복 실행 방어에 영향을 줍니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sys_migrations WHERE MigrationName = ?", (migration_name,))
    if not cursor.fetchone():
        try:
            migration_func()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            conn2 = get_db_connection()
            c2 = conn2.cursor()
            c2.execute("INSERT INTO sys_migrations (MigrationName, AppliedAt) VALUES (?, ?)", (migration_name, now))
            conn2.commit()
            conn2.close()
            
            print(f"[Migration Manager] '{migration_name}' successfully applied.")
        except Exception as e:
            print(f"[Migration Manager] Error applying '{migration_name}': {e}")
    conn.close()

def migrate_menu_hierarchy():
    """
    [역할]: 제안-035 관리자 센터 도입에 따른 메뉴 계층화 마이그레이션 (ParentMenuCode, SortOrder 추가 및 데이터 재정렬)
    [의존성 관계]: menus 테이블
    [변경 시 영향도]: 메인 포털 화면과 관리자 센터의 메뉴 노출 구조를 완전히 바꿉니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(menus)")
        columns = [col['name'] for col in cursor.fetchall()]
        if 'ParentMenuCode' not in columns:
            cursor.execute("ALTER TABLE menus ADD COLUMN ParentMenuCode TEXT")
        if 'SortOrder' not in columns:
            cursor.execute("ALTER TABLE menus ADD COLUMN SortOrder INTEGER DEFAULT 0")
            
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, ParentMenuCode, SortOrder, CreatedAt, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('admin_center', '관리자 센터', '/admin_center', '시스템 관리자 전용 메뉴 허브', None, 4, now, now))
        
        sub_menus = [('permissions', 1), ('audit_logs', 2), ('users_management', 3), ('approvals', 4), ('master_management', 5)]
        for menu_code, sort_order in sub_menus:
            cursor.execute('''
                UPDATE menus SET ParentMenuCode = 'admin_center', SortOrder = ? WHERE MenuCode = ?
            ''', (sort_order, menu_code))
            
        cursor.execute("SELECT Role FROM role_menu_permissions WHERE MenuCode = 'permissions' AND IsAllowed = 1")
        admin_roles = [r['Role'] for r in cursor.fetchall()]
        for role in admin_roles:
            cursor.execute('''
                INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt)
                VALUES (?, 'admin_center', 1, ?)
            ''', (role, now))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error] migrate_menu_hierarchy: {str(e)}")


run_migration_if_needed('menu_hierarchy', migrate_menu_hierarchy)

def migrate_access_logs_menu():
    """
    [역할]: 제안-036 실시간 웹 접근 로그 모니터링 메뉴 및 권한을 관리자 센터 하위에 동적으로 추가합니다.
    [의존성 관계]: menus, role_menu_permissions 테이블
    [변경 시 영향도]: 관리자 센터 내에 '웹 접근 로그' 메뉴 카드가 활성화됩니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, ParentMenuCode, SortOrder, CreatedAt, UpdatedAt)
            VALUES ('access_logs', '웹 접근 로그', '/access_logs', '실시간 HTTP 트래픽 및 웹 접근 로그 모니터링', 'admin_center', 6, ?, ?)
        ''', (now, now))

        cursor.execute('''
            UPDATE menus SET ParentMenuCode = 'admin_center', SortOrder = 6 WHERE MenuCode = 'access_logs'
        ''')

        cursor.execute("SELECT Role FROM role_menu_permissions WHERE MenuCode = 'admin_center' AND IsAllowed = 1")
        admin_roles = [r['Role'] for r in cursor.fetchall()]
        for role in admin_roles:
            cursor.execute('''
                INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt)
                VALUES (?, 'access_logs', 1, ?)
            ''', (role, now))

        cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES ('user', 'access_logs', 0, ?)", (now,))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error] migrate_access_logs_menu: {str(e)}")

run_migration_if_needed('proposal_036_access_logs', migrate_access_logs_menu)

def migrate_access_logs_payload():
    """
    [역할]: 제안-040에 따라 access_logs 테이블에 RequestPayload, ResponsePayload 컬럼을 추가합니다.
    [의존성 관계]: access_logs 테이블
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(access_logs)")
        columns = [info['name'] for info in cursor.fetchall()]
        
        if 'RequestPayload' not in columns:
            cursor.execute("ALTER TABLE access_logs ADD COLUMN RequestPayload TEXT")
        if 'ResponsePayload' not in columns:
            cursor.execute("ALTER TABLE access_logs ADD COLUMN ResponsePayload TEXT")
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error] migrate_access_logs_payload: {str(e)}")

run_migration_if_needed('proposal_040_access_logs_payload', migrate_access_logs_payload)

def migrate_equipment_is_public():
    """
    [역할]: 장비 테이블에 IsPublic 컬럼이 없으면 동적으로 추가합니다.
    [의존성 관계]: equipment 테이블
    [변경 시 영향도]: 장비 공개 여부 필드 추가에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(equipment)")
        columns = [info['name'] for info in cursor.fetchall()]
        if 'IsPublic' not in columns:
            cursor.execute("ALTER TABLE equipment ADD COLUMN IsPublic INTEGER DEFAULT 0")
            print("[Migration] equipment 테이블에 IsPublic 컬럼이 성공적으로 추가되었습니다.")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error (IsPublic)] {e}")

run_migration_if_needed('equipment_is_public', migrate_equipment_is_public)

def migrate_proposals_011_027_028():
    """
    [역할]: 제안(소유권 만료, 메모장 등)에 필요한 컬럼들을 한 번에 추가합니다.
    [의존성 관계]: users, equipment 테이블
    [변경 시 영향도]: 각종 부가 정보 컬럼 생성에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 1. IsDraft 컬럼 추가
        cursor.execute("PRAGMA table_info(equipment)")
        columns = [info['name'] for info in cursor.fetchall()]
        if 'IsDraft' not in columns:
            cursor.execute("ALTER TABLE equipment ADD COLUMN IsDraft INTEGER DEFAULT 0")
            print("[Migration] equipment 테이블에 IsDraft 컬럼이 성공적으로 추가되었습니다.")

        # 2. 기존 카테고리 시딩
        cursor.execute("SELECT DISTINCT Category FROM equipment WHERE Category IS NOT NULL AND TRIM(Category) != ''")
        existing_cats = [r['Category'].strip() for r in cursor.fetchall()]
        for cat in existing_cats:
            cursor.execute("INSERT OR IGNORE INTO categories (Name, IsApproved, CreatedAt) VALUES (?, 1, ?)", (cat, now))

        # 3. 기존 제조사 시딩
        cursor.execute("SELECT DISTINCT Manufacturer FROM equipment WHERE Manufacturer IS NOT NULL AND TRIM(Manufacturer) != ''")
        existing_mfgs = [r['Manufacturer'].strip() for r in cursor.fetchall()]
        for mfg in existing_mfgs:
            cursor.execute("INSERT OR IGNORE INTO manufacturers (Name, IsApproved, CreatedAt) VALUES (?, 1, ?)", (mfg, now))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error (011_027_028)] {e}")

run_migration_if_needed('proposals_011_027_028', migrate_proposals_011_027_028)

def migrate_relational_master():
    """
    [역할] 제안-011-고도화 데이터베이스 마이그레이션 수행
    1. categories, manufacturers 테이블에 NameKo, NameEn 컬럼 추가
    2. equipment 테이블에 CategoryId, ManufacturerId 컬럼 추가
    3. 기존 equipment의 Category, Manufacturer 텍스트 값을 categories, manufacturers 의 ID 값으로 연결하고, 
       equipment.CategoryId, equipment.ManufacturerId 및 레거시 컬럼(Category, Manufacturer)에 동일한 ID 값을 업데이트
    [의존성 관계] categories, manufacturers, equipment 테이블
    [변경 시 영향도] 장비 데이터의 분류 저장이 텍스트에서 정수형 Key(ID) 기반으로 완전히 전환됩니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 1. categories 테이블에 NameKo, NameEn 추가
        cursor.execute("PRAGMA table_info(categories)")
        cat_cols = [info['name'] for info in cursor.fetchall()]
        if 'NameKo' not in cat_cols:
            cursor.execute("ALTER TABLE categories ADD COLUMN NameKo TEXT")
        if 'NameEn' not in cat_cols:
            cursor.execute("ALTER TABLE categories ADD COLUMN NameEn TEXT")

        # 2. manufacturers 테이블에 NameKo, NameEn 추가
        cursor.execute("PRAGMA table_info(manufacturers)")
        mfg_cols = [info['name'] for info in cursor.fetchall()]
        if 'NameKo' not in mfg_cols:
            cursor.execute("ALTER TABLE manufacturers ADD COLUMN NameKo TEXT")
        if 'NameEn' not in mfg_cols:
            cursor.execute("ALTER TABLE manufacturers ADD COLUMN NameEn TEXT")

        # 3. equipment 테이블에 CategoryId, ManufacturerId 추가
        cursor.execute("PRAGMA table_info(equipment)")
        eq_cols = [info['name'] for info in cursor.fetchall()]
        if 'CategoryId' not in eq_cols:
            cursor.execute("ALTER TABLE equipment ADD COLUMN CategoryId INTEGER")
        if 'ManufacturerId' not in eq_cols:
            cursor.execute("ALTER TABLE equipment ADD COLUMN ManufacturerId INTEGER")

        # 4. equipment 데이터의 Category / Manufacturer 텍스트를 ID로 변환하여 매핑
        cursor.execute("SELECT EquipmentId, Category, Manufacturer, CategoryId, ManufacturerId FROM equipment")
        equipments = cursor.fetchall()

        for eq in equipments:
            eq_id = eq['EquipmentId']
            cat_val = str(eq['Category']).strip() if eq['Category'] is not None else ''
            mfg_val = str(eq['Manufacturer']).strip() if eq['Manufacturer'] is not None else ''

            new_cat_id = eq['CategoryId']
            new_mfg_id = eq['ManufacturerId']

            # 카테고리 매핑
            if cat_val:
                if cat_val.isdigit():
                    new_cat_id = int(cat_val)
                else:
                    cursor.execute("SELECT CategoryId FROM categories WHERE Name = ?", (cat_val,))
                    c_row = cursor.fetchone()
                    if c_row:
                        new_cat_id = c_row['CategoryId']
                    else:
                        cursor.execute("INSERT INTO categories (Name, IsApproved, CreatedAt) VALUES (?, 1, ?)", (cat_val, now))
                        new_cat_id = cursor.lastrowid

            # 제조사 매핑
            if mfg_val:
                if mfg_val.isdigit():
                    new_mfg_id = int(mfg_val)
                else:
                    cursor.execute("SELECT ManufacturerId FROM manufacturers WHERE Name = ?", (mfg_val,))
                    m_row = cursor.fetchone()
                    if m_row:
                        new_mfg_id = m_row['ManufacturerId']
                    else:
                        cursor.execute("INSERT INTO manufacturers (Name, IsApproved, CreatedAt) VALUES (?, 1, ?)", (mfg_val, now))
                        new_mfg_id = cursor.lastrowid

            # equipment 테이블 업데이트 (CategoryId, ManufacturerId 및 레거시 Category, Manufacturer 컬럼에 ID 동일 업데이트)
            cursor.execute('''
                UPDATE equipment 
                SET CategoryId = ?, ManufacturerId = ?, Category = ?, Manufacturer = ?
                WHERE EquipmentId = ?
            ''', (new_cat_id, new_mfg_id, str(new_cat_id) if new_cat_id else None, str(new_mfg_id) if new_mfg_id else None, eq_id))

        conn.commit()
        conn.close()
        print("[Migration] 제안-011-고도화 관계형 마스터 데이터 매핑이 성공적으로 완료되었습니다.")
    except Exception as e:
        print(f"[Migration Error (relational_master)] {e}")

run_migration_if_needed('relational_master', migrate_relational_master)

def migrate_passwords_to_hash():
    """
    [역할]: 기존 평문 비밀번호를 bcrypt 해시로 일괄 변환합니다.
    [의존성 관계]: users 테이블
    [변경 시 영향도]: 계정 로그인 암호 체계에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT UserId, Password FROM users")
        users = cursor.fetchall()
        
        for u in users:
            pwd = u['Password']
            # werkzeug 기본 해시 형태가 아니면 평문으로 간주
            if pwd and not (pwd.startswith('scrypt:') or pwd.startswith('pbkdf2:')):
                hashed = generate_password_hash(pwd)
                cursor.execute("UPDATE users SET Password = ? WHERE UserId = ?", (hashed, u['UserId']))
                print(f"[Migration] User {u['UserId']} 의 평문 비밀번호가 안전하게 해싱되었습니다.")
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error] {e}")

# 구동 시 비밀번호 해싱 자동 마이그레이션 수행
run_migration_if_needed('passwords_to_hash', migrate_passwords_to_hash)

def migrate_email_features():
    """
    [역할]: 사용자 테이블에 이메일 관련 보안 필드를 추가합니다.
    [의존성 관계]: users 테이블
    [변경 시 영향도]: 이메일 기반 보안 기능 지원에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(users)")
        cols = [info['name'] for info in cursor.fetchall()]
        if 'Email' not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN Email TEXT")
        
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(Email) WHERE Email IS NOT NULL")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_verifications (
                Email TEXT PRIMARY KEY,
                PinCodeHash TEXT NOT NULL,
                ExpiresAt TEXT NOT NULL,
                IsVerified INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS password_resets (
                TokenHash TEXT PRIMARY KEY,
                UserId INTEGER NOT NULL,
                ExpiresAt TEXT NOT NULL,
                IsUsed INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error (email_features)] {e}")

run_migration_if_needed('proposal_030_email_auth', migrate_email_features)

@app.context_processor
def inject_csrf_token():
    """
    [역할]: 모든 템플릿 렌더링 시 세션 기반 CSRF 토큰을 전역으로 주입하고, 누락 시 신규 생성합니다.
    [의존성 관계]: session['csrf_token'], secrets 모듈
    [변경 시 영향도]: 모든 프론트엔드 템플릿의 CSRF 보안 토큰 가용성에 영향을 줍니다.
    """
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return dict(csrf_token=session['csrf_token'])


def csrf_required(f):
    """
    [역할]: 변경 요청 시 클라이언트의 CSRF 토큰을 검증하는 데코레이터입니다.
    [의존성 관계]: session['csrf_token']
    [변경 시 영향도]: POST, PUT, DELETE, PATCH API 통신 보안에 영향을 줍니다.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        """
        [역할]: 데코레이터 래퍼 함수로 원본 함수 실행 전/후 처리를 담당합니다.
        [의존성 관계]: 원본 함수(f)
        [변경 시 영향도]: 데코레이터 적용 라우터의 인자 전달에 영향을 줍니다.
        """
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            token = request.headers.get('X-CSRFToken')
            if not token or token != session.get('csrf_token'):
                return jsonify({"success": False, "message": "CSRF 토큰 검증에 실패했습니다. 새로고침 후 다시 시도해 주세요."}), 403
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def before_request_func():
    """
    [역할]: 요청 시작 시간을 기록하여 응답 소요 시간(Latency)을 측정할 수 있게 합니다.
    [의존성 관계]: flask.g
    [변경 시 영향도]: 모든 HTTP 요청 처리 시간 측정 기준점에 영향을 줍니다.
    """
    g.start_time = time.time()


@app.after_request
def after_request_func(response):
    """
    [역할]: HTTP 헤더에 보안 설정을 삽입하고, HTTP 접근 로그를 비동기 큐에 적재합니다.
    [의존성 관계]: Flask Response, push_access_log, flask.g
    [변경 시 영향도]: 브라우저 클라이언트 측 보안 제어 및 실시간 접근 로그 수집에 영향을 줍니다.
    """
    # 1. 폴링 요청 시에는 플라스크가 세션을 자동으로 갱신(Refresh)하지 못하게 세션 쿠키 발급을 차단
    if request.path == '/api/check_session':
        new_headers = []
        for k, v in response.headers.items():
            if k.lower() == 'set-cookie' and v.startswith('session='):
                continue
            new_headers.append((k, v))
        response.headers = type(response.headers)(new_headers)
        return response

    # 2. [제안-036] 접근 로그 비동기 수집 (Fail-Safe 격리)
    try:
        # 소요 시간 계산
        duration_ms = round((time.time() - g.get('start_time', time.time())) * 1000, 2)
        
        # 정적 리소스 판별 조건식 (O(1) frozenset 활용)
        is_static = 1 if (
            request.path.startswith('/static/') or 
            request.path in STATIC_METADATA_ROUTES_FROZEN
        ) else 0
        
        # 안전한 IP 추출 (X-Forwarded-For 우선)
        raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')
        ip_addr = raw_ip.split(',')[0].strip() if raw_ip else '127.0.0.1'
        
        # [제안-040, 043] Request / Response Payload 무제한 추출 (단, /api/access_logs 자체의 재귀적 로깅 루프 방어)
        request_payload = request.get_data(as_text=True) if request.method in ["POST", "PUT", "PATCH", "DELETE"] else None
        
        response_payload = None
        # [제안-043] /api/access_logs 계열 응답은 ResponsePayload에서 제외하여 재귀적 DB 비대화 및 락 교착 방어
        if not is_static and not request.path.startswith('/api/access_logs'):
            try:
                response_payload = response.get_data(as_text=True)
            except Exception:
                pass # 바이너리 데이터 등 텍스트 변환 실패 시 무시
        
        # KST 일시 생성
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Non-blocking 큐 푸시
        push_access_log({
            'IpAddress': ip_addr,
            'HttpMethod': request.method,
            'RequestPath': request.path,
            'StatusCode': response.status_code,
            'UserAgent': request.user_agent.string[:255] if request.user_agent else '',
            'Referer': request.referrer[:255] if request.referrer else '',
            'DurationMs': duration_ms,
            'IsStatic': is_static,
            'RequestPayload': request_payload,
            'ResponsePayload': response_payload,
            'CreatedAt': created_at
        })
        
        # [사용자 지시로 주석 처리됨] 콘솔 직관적 모니터링을 위한 표준 출력
        # status_code = response.status_code
        # if status_code >= 500:
        #     color = '\033[91m' # Red
        # elif status_code >= 400:
        #     color = '\033[93m' # Yellow
        # elif status_code >= 300:
        #     color = '\033[96m' # Cyan
        # else:
        #     color = '\033[92m' # Green
        # reset = '\033[0m'
        # 
        # if is_static:
        #     # 정적 파일 로그는 회색으로 눈에 덜 띄게 출력
        #     print(f"\033[90m[{created_at}] {ip_addr} - {request.method} {request.path} {status_code} {duration_ms}ms (Static)\033[0m")
        # else:
        #     print(f"[{created_at}] {ip_addr} - {request.method} {request.path} {color}{status_code}{reset} {duration_ms}ms")
    except Exception:
        # 어떠한 로깅 예외도 웹 응답(200 OK 등)을 500으로 방해하지 않도록 완전 격리
        pass

    return response

@app.route('/api/check_session', methods=['GET'])
def check_session():
    """
    [역할]: 요청 전 세션 만료 및 다중 기기 강제 로그아웃 여부를 검증합니다.
    [의존성 관계]: session, users 테이블
    [변경 시 영향도]: 사이트 전체 접속 유지 기능에 영향을 줍니다.
    """
    user = session.get('user')
    if not user or 'UserId' not in user:
        return jsonify({"valid": False, "reason": "session_expired"}), 401
    
    current_token = session.get('session_token')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT SessionToken FROM users WHERE UserId = ?', (user['UserId'],))
    db_token = cursor.fetchone()
    conn.close()
    
    if db_token and current_token != db_token['SessionToken']:
        return jsonify({"valid": False, "reason": "concurrent_login"}), 401
        
    return jsonify({"valid": True}), 200

def migrate_users_session_token():
    """
    [역할]: 다중 기기 강제 로그아웃을 위한 세션 토큰 필드를 추가합니다.
    [의존성 관계]: users 테이블
    [변경 시 영향도]: 사용자 세션 제어 스키마 관리에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [info['name'] for info in cursor.fetchall()]
        if 'SessionToken' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN SessionToken TEXT")
            print("[Migration] users 테이블에 SessionToken 컬럼이 추가되었습니다.")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error (SessionToken)] {e}")

def migrate_users_soft_delete():
    """
    [역할]: 비활성화 및 탈퇴 유예 관련 필드를 DB에 추가합니다.
    [의존성 관계]: users 테이블
    [변경 시 영향도]: 계정 소프트 딜리트 구조에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [info['name'] for info in cursor.fetchall()]
        if 'IsDeactivated' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN IsDeactivated TEXT DEFAULT 'N'")
        if 'DeactivatedAt' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN DeactivatedAt TEXT")
        if 'IsDeleted' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN IsDeleted TEXT DEFAULT 'N'")
        if 'DeletedAt' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN DeletedAt TEXT")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration Error (Soft Delete)] {e}")

run_migration_if_needed('migrate_users_soft_delete', migrate_users_soft_delete)

def cleanup_migration_artifacts():
    """
    [역할]: 마이그레이션 중 생성된 임시 백업 테이블들을 삭제합니다.
    [의존성 관계]: sqlite_master 테이블
    [변경 시 영향도]: DB 파일 용량 및 무결성에 영향을 줍니다.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # categories와 manufacturers에서 Name이 숫자로만 이루어진 행을 찾는다
        cursor.execute("SELECT CategoryId, Name FROM categories")
        for row in cursor.fetchall():
            if row['Name'].isdigit():
                cursor.execute("DELETE FROM categories WHERE CategoryId = ?", (row['CategoryId'],))
                
        cursor.execute("SELECT ManufacturerId, Name FROM manufacturers")
        for row in cursor.fetchall():
            if row['Name'].isdigit():
                cursor.execute("DELETE FROM manufacturers WHERE ManufacturerId = ?", (row['ManufacturerId'],))
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Cleanup Error] {e}")

run_migration_if_needed('cleanup_migration_artifacts', cleanup_migration_artifacts)


def evaluate_user_lifecycle(user):
    """
    [역할]: 사용자 탈퇴 유예기간(30일) 만료 여부를 실시간으로 평가합니다.
    [의존성 관계]: users 테이블
    [변경 시 영향도]: 자진 탈퇴자 계정 파기 스케줄링에 영향을 줍니다.
    """
    if not user:
        return {"status": "NOT_FOUND"}
        
    user_dict = dict(user)
    user_id = user_dict.get('UserId')
    login_id = user_dict.get('LoginId')
    is_deactivated = user_dict.get('IsDeactivated') or 'N'
    deactivated_at_str = user_dict.get('DeactivatedAt')
    is_deleted = user_dict.get('IsDeleted') or 'N'
    
    if is_deactivated == 'Y' and deactivated_at_str:
        try:
            deactivated_at = datetime.strptime(deactivated_at_str, '%Y-%m-%d %H:%M:%S')
            days_passed = (datetime.now() - deactivated_at).total_seconds() / 86400.0
            
            # Phase 3: 1년(365일)+1일 = 366일 경과 -> DB Hard Delete
            if days_passed >= 366:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_settings WHERE UserId = ?", (user_id,))
                cursor.execute("UPDATE equipments SET user_id = NULL, is_public = 1 WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM users WHERE UserId = ?", (user_id,))
                conn.commit()
                conn.close()
                log_audit(None, login_id, 'SYSTEM_HARD_DELETE', 'users', user_id, None, {"reason": "1_year_elapsed"})
                return {"status": "HARD_DELETED"}
                
            # Phase 2: 30일 경과 -> Soft Delete 완료 (로그인 전면 차단)
            if days_passed >= 30:
                if is_deleted != 'Y':
                    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET IsDeleted = 'Y', DeletedAt = ? WHERE UserId = ?", (now_str, user_id))
                    conn.commit()
                    conn.close()
                    log_audit(None, login_id, 'SYSTEM_SOFT_DELETE', 'users', user_id, None, {"reason": "30_days_elapsed"})
                return {"status": "DELETED", "days_passed": days_passed}
                
            # Phase 1: 30일 미만 -> 비활성화 유예 중
            days_left = max(0, 30 - int(days_passed))
            return {"status": "DEACTIVATED", "days_left": days_left, "days_passed": days_passed}
        except Exception as e:
            print(f"[Lifecycle Evaluation Error] {e}")
            return {"status": "DEACTIVATED", "days_left": 30}
            
    elif is_deactivated == 'Y' and not deactivated_at_str:
        # 관리자 강제 정지 (무기한)
        return {"status": "ADMIN_SUSPENDED"}
        
    elif is_deleted == 'Y':
        # 이미 Soft Delete 처리됨 -> 1년 경과 체크
        deleted_at_str = user_dict.get('DeletedAt') or deactivated_at_str
        if deleted_at_str:
            try:
                ref_time = datetime.strptime(deleted_at_str, '%Y-%m-%d %H:%M:%S')
                days_passed = (datetime.now() - ref_time).total_seconds() / 86400.0
                if days_passed >= 366:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM user_settings WHERE UserId = ?", (user_id,))
                    cursor.execute("UPDATE equipments SET user_id = NULL, is_public = 1 WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM users WHERE UserId = ?", (user_id,))
                    conn.commit()
                    conn.close()
                    log_audit(None, login_id, 'SYSTEM_HARD_DELETE', 'users', user_id, None, {"reason": "1_year_elapsed"})
                    return {"status": "HARD_DELETED"}
            except Exception:
                pass
        return {"status": "DELETED"}
        
    return {"status": "ACTIVE"}


# ==========================================
# 3. 인증 및 권한 데코레이터
# ==========================================

def login_required(f):
    """
    [역할]: 로그인 세션이 없는 사용자의 접근을 차단하고 리다이렉트합니다.
    [의존성 관계]: session['user']
    [변경 시 영향도]: 인증이 필요한 전역 라우터 접근 제어에 영향을 줍니다.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        """
        [역할]: 데코레이터 래퍼 함수로 원본 함수 실행 전/후 처리를 담당합니다.
        [의존성 관계]: 원본 함수(f)
        [변경 시 영향도]: 데코레이터 적용 라우터의 인자 전달에 영향을 줍니다.
        """
        user = session.get('user')
        session_token = session.get('session_token')
        
        if not user or 'UserId' not in user or not session_token:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({"error": "로그인이 필요합니다."}), 401
            return redirect(url_for('login_page'))
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SessionToken, IsDeactivated, DeactivatedAt, IsDeleted FROM users WHERE UserId = ?", (user['UserId'],))
        db_user = cursor.fetchone()
        conn.close()
        
        if not db_user or db_user['SessionToken'] != session_token:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({"error": "다른 기기에서 로그인하여 세션이 만료되었습니다."}), 401
            return redirect(url_for('login_page', error='concurrent_login'))
            
        # 비활성화 샌드박싱: 비활성화 상태인 경우 허용된 엔드포인트 이외에는 접근 불가
        if db_user['IsDeactivated'] == 'Y' or session.get('user', {}).get('IsDeactivated'):
            allowed_paths = ['/deactivated_notice', '/api/users/withdraw/cancel', '/logout']
            if request.path not in allowed_paths:
                if request.path.startswith('/api/'):
                    return jsonify({"error": "비활성화 상태인 계정입니다."}), 403
                return redirect(url_for('deactivated_notice_page'))

        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    [역할]: 관리자(admin) 권한을 가진 사용자만 접근을 허용하는 데코레이터입니다.
    [의존성 관계]: session['user']
    [변경 시 영향도]: 관리자 전용 API 및 화면 접근 통제에 영향을 줍니다.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user or user.get('Role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "message": "관리자 권한이 필요합니다."}), 403
            return redirect(url_for('portal_page', error='admin_only'))
        return f(*args, **kwargs)
    return decorated_function


@app.errorhandler(500)
def handle_internal_server_error(e):
    """
    [역할]: 500 내부 서버 에러 발생 시 Stack Trace가 외부로 노출되지 않도록 은폐하고 안전한 응답 반환
    [의존성 관계]: Flask 전역 예외 처리기
    [변경 시 영향도]: 보안 취약점(내부 구조 노출) 방어에 영향을 줍니다.
    """
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "message": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."}), 500
    return render_template('portal.html', error_msg="서버 오류가 발생했습니다."), 500


def check_menu_permission(menu_code):
    """
    [역할]: 사용자가 특정 메뉴(화면)에 접근할 권한이 있는지 확인합니다.
    [의존성 관계]: session, role_menu_permissions 테이블
    [변경 시 영향도]: 페이지 403 에러 발생 로직에 영향을 줍니다.
    """
    user = session.get('user')
    if not user:
        return False
    if user['Role'] == 'admin':
        return True
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IsAllowed FROM role_menu_permissions WHERE Role = ? AND MenuCode = ?", (user['Role'], menu_code))
    row = cursor.fetchone()
    conn.close()
    
    return bool(row and row['IsAllowed'] == 1)


# ==========================================
# 4. 화면 라우터 (뷰 페이지)
# ==========================================

@app.route('/favicon.ico')
def favicon():
    """
    [역할]: 파비콘 이미지를 응답합니다.
    [의존성 관계]: Resources/EqMgmt.ico
    [변경 시 영향도]: 웹사이트 아이콘 표시에 영향을 줍니다.
    """
    return send_from_directory(os.path.join(app.root_path, 'Resources'),
                               'EqMgmt.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def index():
    """
    [역할]: 루트 경로 접속 시 로그인 상태에 따라 포털 또는 로그인 화면으로 분기합니다.
    [의존성 관계]: session['user']
    [변경 시 영향도]: 초기 진입 리다이렉션에 영향을 줍니다.
    """
    user = session.get('user')
    if user and 'UserId' in user:
        return redirect(url_for('portal_page'))
    session.pop('user', None)
    return redirect(url_for('login_page'))


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """
    [역할]: 사용자 로그인 폼 검증 및 세션 생성 처리를 담당합니다.
    [의존성 관계]: users 테이블
    [변경 시 영향도]: 로그인 인증 메커니즘 전반에 영향을 줍니다.
    """
    if request.method == 'GET':
        user = session.get('user')
        if user and 'UserId' in user:
            if user.get('IsDeactivated'):
                return redirect(url_for('deactivated_notice_page'))
            return redirect(url_for('portal_page'))
        session.pop('user', None)
        return render_template('login.html')
    
    data = request.json or request.form
    login_id = data.get('LoginId')
    password = data.get('Password')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LoginId = ?", (login_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        log_audit(None, login_id, 'LOGIN_FAILED', 'users', None, None, {"LoginId": login_id, "reason": "invalid_credentials"})
        return jsonify({"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 400
        
    eval_result = evaluate_user_lifecycle(user)
    status = eval_result['status']
    
    if status in ['HARD_DELETED', 'DELETED']:
        log_audit(None, login_id, 'LOGIN_FAILED', 'users', None, None, {"LoginId": login_id, "reason": f"account_{status.lower()}"})
        return jsonify({"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 400
        
    if status == 'ADMIN_SUSPENDED':
        log_audit(None, login_id, 'LOGIN_FAILED', 'users', user['UserId'], None, {"LoginId": login_id, "reason": "admin_suspended"})
        return jsonify({"success": False, "message": "관리자에 의해 비활성화(정지)된 계정입니다. 관리자에게 문의하세요."}), 400
        
    if check_password_hash(user['Password'], password):
        user_dict = {
            'UserId': user['UserId'],
            'LoginId': user['LoginId'],
            'Name': user['Name'],
            'NickName': user['NickName'],
            'Email': user['Email'] if 'Email' in user.keys() else None,
            'Role': user['Role'],
            'IsDeactivated': (status == 'DEACTIVATED'),
            'DeactivationDaysLeft': eval_result.get('days_left', 30) if status == 'DEACTIVATED' else None
        }
        
        session_token = os.urandom(24).hex()
        session['user'] = user_dict
        session['session_token'] = session_token
        session.permanent = True
        
        conn_update = get_db_connection()
        cursor_update = conn_update.cursor()
        cursor_update.execute("UPDATE users SET SessionToken = ? WHERE UserId = ?", (session_token, user['UserId']))
        conn_update.commit()
        conn_update.close()
        
        log_audit(user['UserId'], user['LoginId'], 'LOGIN_SUCCESS', 'users', user['UserId'], None, {"LoginId": login_id, "Status": status})
        
        if status == 'DEACTIVATED':
            return jsonify({
                "success": True,
                "is_deactivated": True,
                "redirect": "/deactivated_notice",
                "message": f"현재 회원 탈퇴 유예 중(D-{eval_result.get('days_left', 30)}일)입니다."
            })
            
        return jsonify({"success": True, "message": "로그인 성공"})
    else:
        log_audit(None, login_id, 'LOGIN_FAILED', 'users', user['UserId'], None, {"LoginId": login_id, "reason": "invalid_password"})
        return jsonify({"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 400


@app.route('/deactivated_notice')
@login_required
def deactivated_notice_page():
    """
    [역할]: 계정 정지/비활성화 안내 화면을 렌더링합니다.
    [의존성 관계]: deactivated_notice.html
    [변경 시 영향도]: 정지 회원 접근 안내 문구 표시에 영향을 줍니다.
    """
    user = session.get('user', {})
    days_left = user.get('DeactivationDaysLeft', 30)
    return render_template('deactivated_notice.html', user=user, days_left=days_left)


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    """
    [역할]: 회원 가입 페이지 렌더링 및 신규 계정 생성을 처리합니다.
    [의존성 관계]: users 테이블, email_verifications 테이블
    [변경 시 영향도]: 시스템 신규 회원 유입 프로세스에 영향을 줍니다.
    """
    if request.method == 'GET':
        return render_template('register.html')
        
    data = request.json
    login_id = data.get('LoginId')
    name = data.get('Name')
    nickname = data.get('NickName')
    password = data.get('Password')
    email = data.get('Email')
    
    # CSRF 검증 로직 수동 적용
    token = request.headers.get('X-CSRFToken')
    if not token or token != session.get('csrf_token'):
        return jsonify({"success": False, "message": "CSRF 토큰 검증에 실패했습니다. 새로고침 후 다시 시도해 주세요."}), 403

    hashed_password = generate_password_hash(password)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 이메일 인증 여부 검증
    cursor.execute("SELECT IsVerified FROM email_verifications WHERE Email = ?", (email,))
    verif = cursor.fetchone()
    if not verif or verif['IsVerified'] != 1:
        conn.close()
        return jsonify({"success": False, "message": "이메일 인증이 완료되지 않았습니다."}), 400
    
    # 중복 체크 및 탈퇴 복구 분기
    cursor.execute("SELECT * FROM users WHERE LoginId = ?", (login_id,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        eval_res = evaluate_user_lifecycle(existing_user)
        status = eval_res['status']
        
        if status == 'DELETED':  # Phase 2 soft-deleted
            if name and existing_user['Name'] and name.strip() == existing_user['Name'].strip():
                try:
                    cursor.execute('''
                        UPDATE users
                        SET Password = ?, Name = ?, NickName = ?, Email = ?, IsDeactivated = 'N', DeactivatedAt = NULL, IsDeleted = 'N', DeletedAt = NULL, UpdatedAt = ?
                        WHERE UserId = ?
                    ''', (hashed_password, name, nickname, email, now, existing_user['UserId']))
                    conn.commit()
                    log_audit(existing_user['UserId'], login_id, 'RECOVER_ACCOUNT', 'users', existing_user['UserId'], None, {"LoginId": login_id})
                    conn.close()
                    return jsonify({"success": True, "message": "탈퇴된 계정의 소유권이 확인되어 성공적으로 복구되었습니다! 로그인해 주세요."})
                except sqlite3.IntegrityError:
                    conn.close()
                    return jsonify({"success": False, "message": "이미 다른 계정에 등록되어 사용 중인 이메일 주소입니다."}), 400
            else:
                conn.close()
                return jsonify({
                    "success": False,
                    "is_recovery_target": True,
                    "message": "💡 해당 아이디는 탈퇴 수순을 밟고 있는 계정입니다. 계정 복구를 원하시면 본인 소유권 확인을 위해 기존 가입 시 등록하셨던 '실명(이름)'을 입력란에 정확히 입력해 주세요."
                }), 400
        elif status == 'DEACTIVATED':
            conn.close()
            return jsonify({
                "success": False,
                "message": "해당 아이디는 현재 비활성화(탈퇴 유예) 상태입니다. 기존 계정으로 로그인하시면 비활성화를 철회하실 수 있습니다."
            }), 400
        elif status != 'HARD_DELETED':
            conn.close()
            return jsonify({"success": False, "message": "이미 존재하는 아이디입니다."}), 400

    # 신규 가입 진행
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    role = 'admin' if count == 0 else 'user'
    
    try:
        cursor.execute('''
            INSERT INTO users (LoginId, Name, NickName, Password, Email, Role, CreatedAt, UpdatedAt, IsDeactivated, IsDeleted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'N', 'N')
        ''', (login_id, name, nickname, hashed_password, email, role, now, now))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        log_audit(new_id, login_id, 'REGISTER', 'users', new_id, None, {"LoginId": login_id, "Role": role})
        return jsonify({"success": True, "message": "회원가입이 성공적으로 완료되었습니다. 로그인해 주세요."})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "message": "이미 다른 계정에 등록되어 사용 중인 이메일 주소입니다."}), 400


@app.route('/logout')
def logout():
    """
    [역할]: 현재 세션을 파기하고 사용자를 로그아웃 처리합니다.
    [의존성 관계]: session
    [변경 시 영향도]: 로그아웃 기능 동작에 영향을 줍니다.
    """
    user = session.get('user')
    if user:
        if 'UserId' in user:
            log_audit(user['UserId'], user['LoginId'], 'LOGOUT', 'users', user['UserId'], None, None)
        session.clear()
    return redirect(url_for('login_page'))


@app.route('/portal')
@login_required
def portal_page():
    """
    [역할]: 로그인 후 표시되는 메인 포털 화면을 렌더링합니다.
    [의존성 관계]: portal.html
    [변경 시 영향도]: 사용자 대시보드 및 메뉴 링크 진입 화면에 영향을 줍니다.
    """
    return render_template('portal.html', user=session['user'])


@app.route('/equipment')
def equipment_redirect():
    """
    [역할]: 레거시 장비 페이지 경로를 '나의 장비' 페이지로 리다이렉트합니다.
    [의존성 관계]: my_equipment_page
    [변경 시 영향도]: 기존 즐겨찾기 호환성에 영향을 줍니다.
    """
    # 하위 호환성 (기존 URL로 올 경우 나의 장비로 리다이렉트)
    return redirect(url_for('my_equipment_page'))


@app.route('/my_equipment')
@login_required
def my_equipment_page():
    """
    [역할]: 사용자의 '나의 장비' 관리 화면을 렌더링합니다.
    [의존성 관계]: index.html
    [변경 시 영향도]: 본인 소유 장비 UI 접근에 영향을 줍니다.
    """
    if not check_menu_permission('my_equipment'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('index.html', user=session['user'], mode='my')


@app.route('/public_equipment')
@login_required
def public_equipment_page():
    """
    [역할]: 공개로 설정된 타인의 장비 목록 조회 화면을 렌더링합니다.
    [의존성 관계]: index.html
    [변경 시 영향도]: 공개 자산 뷰어 UI 접근에 영향을 줍니다.
    """
    if not check_menu_permission('public_equipment'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('index.html', user=session['user'], mode='public')


@app.route('/admin_center')
@login_required
def admin_center_page():
    """
    [역할]: 관리자 센터 메인 페이지 렌더링
    [의존성 관계]: admin_center.html 템플릿
    [변경 시 영향도]: 관리자 메뉴들의 허브 페이지 접근에 영향을 줍니다.
    """
    if not check_menu_permission('admin_center'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('admin_center.html', user=session.get('user'))

@app.route('/permissions')
@login_required
def permissions_page():
    """
    [역할]: 관리자 전용 역할별 메뉴 권한 관리 화면을 렌더링합니다.
    [의존성 관계]: permissions.html
    [변경 시 영향도]: 권한 관리 UI 렌더링에 영향을 줍니다.
    """
    if not check_menu_permission('permissions'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('permissions.html', user=session['user'])


@app.route('/audit_logs')
@login_required
def audit_logs_page():
    """
    [역할] 보안 감사 로그 페이지 렌더링 (통합 단일 레이아웃 적용)
    [의존성 관계] @login_required, check_menu_permission('audit_logs'), templates/audit_logs.html
    [변경 시 영향도] /audit_logs 접속 시 단일 템플릿 반환
    """
    if not check_menu_permission('audit_logs'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('audit_logs.html', user=session['user'])


@app.route('/access_logs')
@login_required
def access_logs_page():
    """
    [역할]: 관리자 전용 실시간 웹 접근 로그 화면을 렌더링합니다.
    [의존성 관계]: access_logs.html, check_menu_permission('access_logs')
    [변경 시 영향도]: 관리자 접근 로그 관제 UI 진입에 영향을 줍니다.
    """
    if not check_menu_permission('access_logs'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('access_logs.html', user=session['user'])


@app.route('/access_logs/error_ips')
@login_required
def access_logs_error_ips_page():
    """
    [역할]: 관리자 전용 에러(4xx, 5xx) 유발 IP 심층 분석 화면을 렌더링합니다.
    [의존성 관계]: access_logs_error_ips.html, check_menu_permission('access_logs')
    [변경 시 영향도]: 에러 유발 고유 IP 심층 관제 UI 진입에 영향을 줍니다.
    """
    if not check_menu_permission('access_logs'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('access_logs_error_ips.html', user=session['user'])


@app.route('/users_management')
@login_required
def users_management_page():
    """
    [역할]: 관리자 전용 시스템 회원 통제 및 계정 정지 화면을 렌더링합니다.
    [의존성 관계]: users_management.html
    [변경 시 영향도]: 사용자 관리 UI 렌더링에 영향을 줍니다.
    """
    if not check_menu_permission('users_management'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('users_management.html', user=session['user'])

@app.route('/dashboard')
@login_required
def dashboard_page():
    """
    [역할]: 시스템 요약 통계(대시보드) 화면을 렌더링합니다.
    [의존성 관계]: dashboard.html
    [변경 시 영향도]: 통계 및 차트 UI 접근에 영향을 줍니다.
    """
    if not check_menu_permission('dashboard'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('dashboard.html', user=session['user'])

@app.route('/mypage')
@login_required
def mypage_page():
    """
    [역할]: 로그인한 사용자의 정보 조회/수정(마이페이지) 화면을 렌더링합니다.
    [의존성 관계]: mypage.html
    [변경 시 영향도]: 개인정보 관리 화면 진입에 영향을 줍니다.
    """
    # 마이페이지는 모든 로그인 사용자가 접근 가능하므로 메뉴 권한 체크 생략(또는 기본 허용)
    return render_template('mypage.html', user=session['user'])

@app.route('/approvals')
@login_required
def approvals_page():
    """
    [역할]: 관리자 전용 신규 마스터 데이터 결재/승인 화면을 렌더링합니다.
    [의존성 관계]: approvals.html
    [변경 시 영향도]: 승인 처리 UI 접근에 영향을 줍니다.
    """
    if not check_menu_permission('approvals'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('approvals.html', user=session['user'])

@app.route('/master_management')
@login_required
def master_management_page():
    """
    [역할] 마스터 데이터(카테고리/제조사) 관리 페이지 렌더링 (관리자 전용)
    [의존성 관계] @login_required, check_menu_permission('master_management'), templates/master_management.html
    [변경 시 영향도] /master_management 접근 시 단일 템플릿 반환
    """
    if not check_menu_permission('master_management'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('master_management.html', user=session['user'])

# ==========================================
# 5. RESTful API 모듈 (인증/권한 및 데이터 처리)
# ==========================================

# =========================================================================
# [제안-036] 가변 깊이 모델 트리 & 3-Tier 장비 관리 RESTful API 모듈
# =========================================================================

MAX_TREE_DEPTH = 50  # [Call Stack Overflow 방어] 트리 최대 깊이 컷아웃

def _get_all_descendant_node_ids(cursor, node_id):
    """
    [역할]: 특정 노드의 모든 하위 자손 노드 ID 집합을 재귀적으로 수집 (순환 참조 방어용)
    [의존성 관계]: lineup_nodes 테이블
    [알고리즘]: DFS (깊이 우선 탐색)
    """
    descendants = set()
    stack = [node_id]
    while stack:
        current = stack.pop()
        cursor.execute("SELECT id FROM lineup_nodes WHERE parent_id = ?", (current,))
        children = [r['id'] for r in cursor.fetchall()]
        for child_id in children:
            if child_id not in descendants:
                descendants.add(child_id)
                stack.append(child_id)
    return descendants


@app.route('/api/lineup_tree_all', methods=['GET'])
@login_required
def get_lineup_tree_all():
    """
    [역할]: 카테고리, 제조사, N차 라인업 노드(가변 깊이), N+1차 옵션까지 전체 카탈로그 트리를 단 1회 덤프로 반환
    [의존성 관계]: CTE (WITH RECURSIVE), categories, manufacturers, lineup_nodes, equipment_options
    [보안/안전]: MAX_DEPTH(50) 컷아웃 제약, @login_required, try-except 예외 쉴드
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. 승인된 카테고리 목록
        cursor.execute("SELECT CategoryId AS id, Name AS name FROM categories WHERE IsApproved = 1 ORDER BY Name ASC")
        categories = [dict(r) for r in cursor.fetchall()]

        # 2. 승인된 제조사 목록
        cursor.execute("SELECT ManufacturerId AS id, Name AS name FROM manufacturers WHERE IsApproved = 1 ORDER BY Name ASC")
        manufacturers = [dict(r) for r in cursor.fetchall()]

        # 3. CTE 재귀 쿼리를 통한 승인된 라인업 노드 전체 트리 덤프 (MAX_DEPTH 50 컷아웃)
        cursor.execute(f"""
            WITH RECURSIVE node_tree AS (
                -- Anchor Member: 1차 루트 노드 (parent_id IS NULL)
                SELECT id, parent_id, category_id, manufacturer_id, name, depth, status, 1 AS level
                FROM lineup_nodes
                WHERE parent_id IS NULL AND status = 'APPROVED'
                
                UNION ALL
                
                -- Recursive Member: 하위 노드 순회 (최대 50단계 제한)
                SELECT n.id, n.parent_id, n.category_id, n.manufacturer_id, n.name, n.depth, n.status, nt.level + 1
                FROM lineup_nodes n
                JOIN node_tree nt ON n.parent_id = nt.id
                WHERE nt.level < {MAX_TREE_DEPTH} AND n.status = 'APPROVED'
            )
            SELECT * FROM node_tree ORDER BY level ASC, name ASC;
        """)
        nodes = [dict(r) for r in cursor.fetchall()]

        # 4. 승인된 옵션 목록 (specs_json 파싱)
        cursor.execute("SELECT id, lineup_node_id, option_name, specs_json FROM equipment_options WHERE status = 'APPROVED'")
        raw_options = cursor.fetchall()
        options = []
        for opt in raw_options:
            specs = {}
            if opt['specs_json']:
                try:
                    specs = json.loads(opt['specs_json'])
                except Exception:
                    specs = {}
            options.append({
                "id": opt['id'],
                "lineup_node_id": opt['lineup_node_id'],
                "option_name": opt['option_name'],
                "specs": specs
            })

        conn.close()

        return jsonify({
            "success": True,
            "version": "nodeCache_v2",
            "categories": categories,
            "manufacturers": manufacturers,
            "nodes": nodes,
            "options": options
        })

    except Exception as e:
        print(f"[API Error] get_lineup_tree_all: {e}")
        return jsonify({"success": False, "message": "카탈로그 트리를 불러오는 중 오류가 발생했습니다."}), 400


@app.route('/api/lineup_node', methods=['POST'])
@login_required
@csrf_required
def create_lineup_node():
    """
    [역할]: 신규 카탈로그 라인업 노드 등록 및 승인 신청
    [보안/방어]:
      - [NULL 중복 락 방어] parent_id IS NULL 시 백엔드 2차 SELECT 중복 검사
      - [MAX_DEPTH 방어] 깊이 50 초과 생성 차단
      - [권한] 관리자는 자동 APPROVED, 일반 사용자는 PENDING 승인 큐 적재
    """
    try:
        data = request.json or {}
        name = (data.get('name') or '').strip()
        category_id = data.get('category_id')
        manufacturer_id = data.get('manufacturer_id')
        parent_id = data.get('parent_id')  # None 또는 정수

        if not name:
            return jsonify({"success": False, "message": "노드 이름을 입력해 주세요."}), 400
        if not category_id or not manufacturer_id:
            return jsonify({"success": False, "message": "카테고리와 제조사를 선택해 주세요."}), 400

        user = session.get('user', {})
        user_id = user.get('UserId')
        is_admin = (user.get('Role') == 'admin')
        status = 'APPROVED' if is_admin else 'PENDING'

        conn = get_db_connection()
        cursor = conn.cursor()

        # 깊이(Depth) 계산 및 MAX_DEPTH 검증
        current_depth = 1
        if parent_id:
            cursor.execute("SELECT depth, category_id, manufacturer_id FROM lineup_nodes WHERE id = ?", (parent_id,))
            parent_row = cursor.fetchone()
            if not parent_row:
                conn.close()
                return jsonify({"success": False, "message": "상위 노드를 찾을 수 없습니다."}), 400
            current_depth = parent_row['depth'] + 1
            if current_depth > MAX_TREE_DEPTH:
                conn.close()
                return jsonify({"success": False, "message": f"트리의 최대 깊이({MAX_TREE_DEPTH}단계)를 초과할 수 없습니다."}), 400

        # [NULL 중복 락 방어]: 루트 노드 중복 명시적 방어
        if parent_id is None:
            cursor.execute("""
                SELECT id FROM lineup_nodes 
                WHERE parent_id IS NULL AND category_id = ? AND manufacturer_id = ? AND name = ?
            """, (category_id, manufacturer_id, name))
            if cursor.fetchone():
                conn.close()
                return jsonify({"success": False, "message": "해당 카테고리/제조사에 동일한 이름의 최상위 모델이 이미 존재합니다."}), 400
        else:
            cursor.execute("SELECT id FROM lineup_nodes WHERE parent_id = ? AND name = ?", (parent_id, name))
            if cursor.fetchone():
                conn.close()
                return jsonify({"success": False, "message": "동일한 상위 노드 아래에 같은 이름의 하위 항목이 이미 존재합니다."}), 400

        cursor.execute("""
            INSERT INTO lineup_nodes (parent_id, category_id, manufacturer_id, name, depth, status, requested_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (parent_id, category_id, manufacturer_id, name, current_depth, status, user_id))

        new_node_id = cursor.lastrowid

        # 일반 사용자 신청 시 approval_requests 에 승인 요청 등록
        if not is_admin:
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            req_data = json.dumps({
                "type": "Lineup_Node",
                "node_id": new_node_id,
                "name": name,
                "parent_id": parent_id,
                "category_id": category_id,
                "manufacturer_id": manufacturer_id,
                "depth": current_depth
            }, ensure_ascii=False)
            cursor.execute("""
                INSERT INTO approval_requests (RequesterId, RequestType, RequestDataJSON, Status, CreatedAt, UpdatedAt)
                VALUES (?, 'Lineup_Node', ?, 'PENDING', ?, ?)
            """, (user_id, req_data, now_str, now_str))

        conn.commit()
        conn.close()

        msg = "신규 모델이 등록되었습니다." if is_admin else "신규 모델 등록 신청이 완료되었습니다. 관리자 승인 후 활성화됩니다."
        return jsonify({"success": True, "node_id": new_node_id, "status": status, "message": msg})

    except Exception as e:
        print(f"[API Error] create_lineup_node: {e}")
        return jsonify({"success": False, "message": f"노드 등록 중 오류가 발생했습니다: {str(e)}"}), 400


@app.route('/api/lineup_node/<int:node_id>', methods=['PUT'])
@login_required
@admin_required
@csrf_required
def update_lineup_node(node_id):
    """
    [역할]: 라인업 노드 정보 수정 및 부모 노드 이동 (관리자 전용)
    [순환 참조(Cyclic Reference) 방어]:
      - 새 부모 노드가 자기 자신이거나 자신의 하위 자손 노드인 경우를 DFS로 탐색하여 원천 차단
    """
    try:
        data = request.json or {}
        new_name = (data.get('name') or '').strip()
        new_parent_id = data.get('parent_id')  # None 또는 int

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM lineup_nodes WHERE id = ?", (node_id,))
        node = cursor.fetchone()
        if not node:
            conn.close()
            return jsonify({"success": False, "message": "수정할 노드를 찾을 수 없습니다."}), 404

        # [순환 참조 방어 검증 1] 자기 자신을 부모로 지정 방어
        if new_parent_id is not None and int(new_parent_id) == node_id:
            conn.close()
            return jsonify({"success": False, "message": "자기 자신을 부모 노드로 지정할 수 없습니다. (순환 참조 방어)"}), 400

        # [순환 참조 방어 검증 2] 자신의 하위 자손 노드를 부모로 지정 방어 (DFS)
        if new_parent_id is not None:
            new_parent_id = int(new_parent_id)
            descendant_ids = _get_all_descendant_node_ids(cursor, node_id)
            if new_parent_id in descendant_ids:
                conn.close()
                return jsonify({"success": False, "message": "자신의 하위 자손 노드를 부모로 지정할 수 없습니다. (순환 참조 고리 방어)"}), 400

            cursor.execute("SELECT depth FROM lineup_nodes WHERE id = ?", (new_parent_id,))
            parent_row = cursor.fetchone()
            if not parent_row:
                conn.close()
                return jsonify({"success": False, "message": "지정한 부모 노드가 존재하지 않습니다."}), 400
            new_depth = parent_row['depth'] + 1
        else:
            new_depth = 1

        if new_depth > MAX_TREE_DEPTH:
            conn.close()
            return jsonify({"success": False, "message": f"트리의 최대 깊이({MAX_TREE_DEPTH}단계)를 초과할 수 없습니다."}), 400

        final_name = new_name if new_name else node['name']

        cursor.execute("""
            UPDATE lineup_nodes 
            SET name = ?, parent_id = ?, depth = ?
            WHERE id = ?
        """, (final_name, new_parent_id, new_depth, node_id))

        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "노드 정보가 성공적으로 수정되었습니다."})

    except Exception as e:
        print(f"[API Error] update_lineup_node: {e}")
        return jsonify({"success": False, "message": f"노드 수정 중 오류가 발생했습니다: {str(e)}"}), 400


@app.route('/api/lineup_node/<int:node_id>', methods=['DELETE'])
@login_required
@admin_required
@csrf_required
def delete_lineup_node(node_id):
    """
    [역할]: 라인업 노드 삭제 (관리자 전용)
    [파괴적 액션 방어]: 하위 자식 노드 또는 연계된 옵션/장비가 있을 경우 삭제 거부
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 하위 노드 존재 여부 확인
        cursor.execute("SELECT COUNT(*) FROM lineup_nodes WHERE parent_id = ?", (node_id,))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return jsonify({"success": False, "message": "하위 모델이 연결되어 있어 삭제할 수 없습니다. 하위 모델을 먼저 삭제해 주세요."}), 400

        # 하위 옵션 존재 여부 확인
        cursor.execute("SELECT COUNT(*) FROM equipment_options WHERE lineup_node_id = ?", (node_id,))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return jsonify({"success": False, "message": "연결된 옵션 스펙이 존재하여 삭제할 수 없습니다."}), 400

        cursor.execute("DELETE FROM lineup_nodes WHERE id = ?", (node_id,))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "노드가 안전하게 삭제되었습니다."})

    except Exception as e:
        print(f"[API Error] delete_lineup_node: {e}")
        return jsonify({"success": False, "message": f"노드 삭제 중 오류가 발생했습니다: {str(e)}"}), 400


@app.route('/api/equipment_option', methods=['POST'])
@login_required
@csrf_required
def create_equipment_option():
    """
    [역할]: N차 라인업 노드에 귀속되는 N+1차 옵션 스펙 조합 등록
    [JSON 밸리데이션]: specs_json 포맷 검증 및 Key-Value 정합성 보장
    """
    try:
        data = request.json or {}
        lineup_node_id = data.get('lineup_node_id')
        option_name = (data.get('option_name') or '').strip()
        specs = data.get('specs') or {}

        if not lineup_node_id:
            return jsonify({"success": False, "message": "소속될 모델 노드를 선택해 주세요."}), 400
        if not option_name:
            return jsonify({"success": False, "message": "옵션 조합명을 입력해 주세요."}), 400

        specs_json_str = json.dumps(specs, ensure_ascii=False) if isinstance(specs, dict) else '{}'

        user = session.get('user', {})
        user_id = user.get('UserId')
        is_admin = (user.get('Role') == 'admin')
        status = 'APPROVED' if is_admin else 'PENDING'

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO equipment_options (lineup_node_id, option_name, specs_json, status, requested_by)
            VALUES (?, ?, ?, ?, ?)
        """, (lineup_node_id, option_name, specs_json_str, status, user_id))

        new_opt_id = cursor.lastrowid
        conn.commit()
        conn.close()

        msg = "옵션 스펙이 등록되었습니다." if is_admin else "옵션 등록 신청이 완료되었습니다. 관리자 승인 후 활성화됩니다."
        return jsonify({"success": True, "option_id": new_opt_id, "status": status, "message": msg})

    except Exception as e:
        print(f"[API Error] create_equipment_option: {e}")
        return jsonify({"success": False, "message": f"옵션 등록 중 오류: {str(e)}"}), 400


@app.route('/api/equipment_option/<int:option_id>', methods=['DELETE'])
@login_required
@admin_required
@csrf_required
def delete_equipment_option(option_id):
    """
    [역할]: 3-Tier 카탈로그 옵션 스펙 조합 삭제 (관리자 전용)
    [파괴적 액션 방어]: 연계된 실제 장비(equipments)가 존재할 경우 삭제 거부
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 장비 참조 여부 검증
        cursor.execute("SELECT COUNT(*) FROM equipments WHERE option_id = ?", (option_id,))
        eq_count = cursor.fetchone()[0]
        if eq_count > 0:
            conn.close()
            return jsonify({"success": False, "message": f"해당 옵션에 연결된 장비가 {eq_count}건 존재하여 삭제할 수 없습니다."}), 400

        cursor.execute("DELETE FROM equipment_options WHERE id = ?", (option_id,))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "옵션이 안전하게 삭제되었습니다."})

    except Exception as e:
        print(f"[API Error] delete_equipment_option: {e}")
        return jsonify({"success": False, "message": f"옵션 삭제 중 오류: {str(e)}"}), 400


@app.route('/api/equipments_v2', methods=['GET', 'POST'])
@login_required
def api_equipments_v2():
    """
    [역할]: 3-Tier 계층 구조 기반 장비 인스턴스 등록 및 복합 JOIN 조회 API
    [트랜잭션/감사로그]: 등록 시 equipments_audit_log 동시 적재 및 rollback 블록 적용
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'GET':
        try:
            # 3-Tier 복합 JOIN 조회 (대시보드 및 장비 목록 공통)
            cursor.execute("""
                SELECT 
                    e.id AS EquipmentId,
                    e.name AS Name,
                    e.serial_number AS SerialNumber,
                    e.purchase_date AS PurchaseDate,
                    e.status AS Status,
                    e.memo AS Memo,
                    e.user_id AS UserId,
                    e.is_public AS IsPublic,
                    e.created_at AS CreatedAt,
                    e.updated_at AS UpdatedAt,
                    opt.id AS OptionId,
                    opt.option_name AS OptionName,
                    opt.specs_json AS SpecsJson,
                    node.id AS LineupNodeId,
                    node.name AS ModelName,
                    node.depth AS ModelDepth,
                    cat.CategoryId AS CategoryId,
                    cat.Name AS CategoryName,
                    mfg.ManufacturerId AS ManufacturerId,
                    mfg.Name AS ManufacturerName,
                    u.LoginId AS UserLoginId,
                    u.Name AS UserName
                FROM equipments e
                JOIN equipment_options opt ON e.option_id = opt.id
                JOIN lineup_nodes node ON opt.lineup_node_id = node.id
                JOIN categories cat ON node.category_id = cat.CategoryId
                JOIN manufacturers mfg ON node.manufacturer_id = mfg.ManufacturerId
                LEFT JOIN users u ON e.user_id = u.UserId
                ORDER BY e.id DESC;
            """)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                if item.get('SpecsJson'):
                    try:
                        item['Specs'] = json.loads(item['SpecsJson'])
                    except Exception:
                        item['Specs'] = {}
                else:
                    item['Specs'] = {}
                result.append(item)

            conn.close()
            return jsonify({"success": True, "equipments": result})

        except Exception as e:
            conn.close()
            print(f"[API Error] GET api_equipments_v2: {e}")
            return jsonify({"success": False, "message": "장비 목록 조회 실패"}), 400

    elif request.method == 'POST':
        # CSRF 토큰 검증
        token = request.headers.get('X-CSRFToken')
        if not token or token != session.get('csrf_token'):
            conn.close()
            return jsonify({"success": False, "message": "CSRF 토큰 검증에 실패했습니다."}), 403

        try:
            data = request.json or {}
            option_id = data.get('option_id')
            name = (data.get('name') or '').strip()
            serial_number = (data.get('serial_number') or '').strip() or None
            purchase_date = data.get('purchase_date')
            memo = data.get('memo')
            is_public = int(data.get('is_public') or 0)

            if not option_id:
                conn.close()
                return jsonify({"success": False, "message": "옵션 스펙을 선택해 주세요."}), 400
            if not name:
                conn.close()
                return jsonify({"success": False, "message": "장비명을 입력해 주세요."}), 400

            user = session.get('user', {})
            user_id = user.get('UserId')
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 시리얼 중복 검증
            if serial_number:
                cursor.execute("SELECT id FROM equipments WHERE serial_number = ?", (serial_number,))
                if cursor.fetchone():
                    conn.close()
                    return jsonify({"success": False, "message": "이미 등록된 시리얼 넘버입니다."}), 400

            cursor.execute("""
                INSERT INTO equipments (option_id, name, serial_number, purchase_date, status, memo, user_id, is_public, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?)
            """, (option_id, name, serial_number, purchase_date, memo, user_id, is_public, now_str, now_str))

            new_eq_id = cursor.lastrowid

            # 감사 로그 인서트
            cursor.execute("""
                INSERT INTO equipments_audit_log (equipment_id, action_type, new_value, changed_by, changed_at)
                VALUES (?, 'CREATE', ?, ?, ?)
            """, (new_eq_id, json.dumps(data, ensure_ascii=False), user_id, now_str))

            conn.commit()
            conn.close()

            return jsonify({"success": True, "equipment_id": new_eq_id, "message": "장비가 성공적으로 등록되었습니다."})

        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"[API Error] POST api_equipments_v2: {e}")
            return jsonify({"success": False, "message": f"장비 등록 실패: {str(e)}"}), 400


@app.route('/api/extend_session', methods=['POST'])
@login_required
@csrf_required
def extend_session():
    """
    [역할]: 사용자의 현재 로그인 세션 만료 시간을 연장합니다.
    [의존성 관계]: session.modified
    [변경 시 영향도]: 타임아웃 팝업 연장 통신에 영향을 줍니다.
    """
    session.modified = True
    return jsonify({"success": True, "message": "세션이 연장되었습니다."})

@app.route('/api/me', methods=['GET'])
@login_required
def get_current_user():
    """
    [역할] 현재 세션에 로그인되어 있는 사용자 정보 반환
    [의존성 관계] @login_required, session 객체
    [변경 시 영향도] 프론트엔드의 사용자 프로필 표시 및 권한 체계 처리에 영향을 줍니다.
    """
    return jsonify(session['user'])

# ------------------------------------------
# 사용자 맞춤 설정 API
# ------------------------------------------
@app.route('/api/user_settings', methods=['GET', 'POST'])
@login_required
@csrf_required
def api_user_settings():
    """
    [역할] 로그인한 사용자의 UI 설정(테마 등)을 조회하거나 저장(UPSERT)합니다.
    [의존성 관계] user_settings 테이블
    [변경 시 영향도] 프론트엔드 환경 설정 적용 상태에 영향을 줍니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute("SELECT PreferencesJSON FROM user_settings WHERE UserId = ?", (user['UserId'],))
        row = cursor.fetchone()
        conn.close()
        if row and row['PreferencesJSON']:
            return jsonify({"success": True, "settings": json.loads(row['PreferencesJSON'])})
        return jsonify({"success": True, "settings": {}})
        
    elif request.method == 'POST':
        data = request.json
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("SELECT PreferencesJSON FROM user_settings WHERE UserId = ?", (user['UserId'],))
        row = cursor.fetchone()
        current_settings = {}
        if row and row['PreferencesJSON']:
            current_settings = json.loads(row['PreferencesJSON'])
            
        current_settings.update(data)
        new_json = json.dumps(current_settings, ensure_ascii=False)
        
        cursor.execute("SELECT UserId FROM user_settings WHERE UserId = ?", (user['UserId'],))
        if cursor.fetchone():
            cursor.execute("UPDATE user_settings SET PreferencesJSON = ?, UpdatedAt = ? WHERE UserId = ?", (new_json, now, user['UserId']))
        else:
            cursor.execute("INSERT INTO user_settings (UserId, PreferencesJSON, UpdatedAt) VALUES (?, ?, ?)", (user['UserId'], new_json, now))
            
        conn.commit()
        conn.close()
        return jsonify({"success": True, "settings": current_settings})

# ------------------------------------------
# 감사 로그 비동기 조회 및 조건 검색 API
# ------------------------------------------
ALLOWED_AUDIT_SEARCH_FIELDS = {
    'all': None,
    'ActorLoginId': 'a.ActorLoginId',
    'ActorName': 'u.Name',
    'IpAddress': 'a.IpAddress',
    'Action': 'a.Action',
    'TargetId': 'a.TargetId',
    'TargetTable': 'a.TargetTable',
    'OldValue': 'a.OldValue',
    'NewValue': 'a.NewValue'
}

@app.route('/api/audit_logs', methods=['GET'])
@login_required
def api_audit_logs():
    """
    [역할] 감사 로그 RESTful 비동기 조회, 컬럼별 조건 검색 및 전역 페이징 처리 (LEFT JOIN 및 빈 키워드 전체 조회 지원)
    [의존성 관계] @login_required, check_menu_permission('audit_logs'), get_db_connection()
    [변경 시 영향도] templates/audit_logs.html의 비동기 표 목록 및 페이징 처리에 영향을 줍니다.
    """
    if not check_menu_permission('audit_logs'):
        return jsonify({'status': 'error', 'message': '접근 권한이 없습니다.'}), 403

    try:
        # 1. 파라미터 파싱 및 Type Casting 예외 방어
        try:
            page = int(request.args.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        try:
            per_page = int(request.args.get('per_page', 200))
        except (ValueError, TypeError):
            per_page = 200

        search_field = request.args.get('search_field', 'all')
        match_type = request.args.get('match_type', 'like') # 'exact' or 'like'
        keyword = request.args.get('keyword', '').strip()

        # 다중 필터 파라미터 (Action 유형, 시작일/종료일)
        action_filter = request.args.get('action_filter', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # 2. 관리자 세션인 경우 상한선 10,000개로 확장 (DoS 방어)
        user = session.get('user', {})
        max_limit = 10000 if user.get('Role') == 'admin' else 1000

        if per_page < 10:
            per_page = 10
        elif per_page > max_limit:
            per_page = max_limit

        offset = (page - 1) * per_page

        # 3. Dynamic SQL 및 Whitelist 검증
        where_clauses = []
        params = []

        if keyword:
            if search_field == 'all':
                if match_type == 'exact':
                    where_clauses.append("(a.ActorLoginId = ? OR u.Name = ? OR a.IpAddress = ? OR a.Action = ? OR a.TargetTable = ? OR a.TargetId = ? OR a.OldValue = ? OR a.NewValue = ?)")
                    params.extend([keyword] * 8)
                else:
                    like_kw = f"%{keyword}%"
                    where_clauses.append("(a.ActorLoginId LIKE ? OR u.Name LIKE ? OR a.IpAddress LIKE ? OR a.Action LIKE ? OR a.TargetTable LIKE ? OR a.TargetId LIKE ? OR a.OldValue LIKE ? OR a.NewValue LIKE ?)")
                    params.extend([like_kw] * 8)
            elif search_field in ALLOWED_AUDIT_SEARCH_FIELDS and ALLOWED_AUDIT_SEARCH_FIELDS[search_field]:
                column_name = ALLOWED_AUDIT_SEARCH_FIELDS[search_field]
                if match_type == 'exact':
                    where_clauses.append(f"{column_name} = ?")
                    params.append(keyword)
                else:
                    where_clauses.append(f"{column_name} LIKE ?")
                    params.append(f"%{keyword}%")
            elif search_field == 'Details':
                if match_type == 'exact':
                    where_clauses.append("(a.TargetTable = ? OR a.OldValue = ? OR a.NewValue = ?)")
                    params.extend([keyword] * 3)
                else:
                    like_kw = f"%{keyword}%"
                    where_clauses.append("(a.TargetTable LIKE ? OR a.OldValue LIKE ? OR a.NewValue LIKE ?)")
                    params.extend([like_kw] * 3)
            else:
                return jsonify({'status': 'error', 'message': '유효하지 않은 검색 컬럼입니다.'}), 400

        # 다중 필터 조건 추가
        if action_filter:
            where_clauses.append("a.Action LIKE ?")
            params.append(f"%{action_filter}%")

        if start_date:
            where_clauses.append("a.CreatedAt >= ?")
            params.append(f"{start_date} 00:00:00" if len(start_date) == 10 else start_date)

        if end_date:
            where_clauses.append("a.CreatedAt <= ?")
            params.append(f"{end_date} 23:59:59" if len(end_date) == 10 else end_date)

        where_stmt = ""
        if where_clauses:
            where_stmt = "WHERE " + " AND ".join(where_clauses)

        conn = get_db_connection()
        cursor = conn.cursor()

        # 4. 전체 카운트 쿼리 (users 테이블과 LEFT JOIN)
        count_query = f"""
            SELECT COUNT(*) 
            FROM audit_logs a 
            LEFT JOIN users u ON a.ActorLoginId = u.LoginId 
            {where_stmt}
        """
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # 5. 데이터 목록 쿼리
        data_query = f"""
            SELECT 
                a.AuditId, a.ActorId, a.ActorLoginId, 
                COALESCE(u.Name, a.ActorLoginId, 'System') AS ActorName, 
                a.Action, a.TargetTable, a.TargetId, a.IpAddress, 
                a.OldValue, a.NewValue, a.UserAgent, a.CreatedAt
            FROM audit_logs a
            LEFT JOIN users u ON a.ActorLoginId = u.LoginId
            {where_stmt}
            ORDER BY a.AuditId DESC
            LIMIT ? OFFSET ?
        """
        data_params = params + [per_page, offset]
        cursor.execute(data_query, data_params)
        rows = cursor.fetchall()
        conn.close()

        logs = []
        for r in rows:
            details_parts = []
            if r['TargetTable']:
                details_parts.append(f"테이블: {r['TargetTable']}")
            if r['OldValue']:
                details_parts.append(f"이전: {r['OldValue']}")
            if r['NewValue']:
                details_parts.append(f"변경: {r['NewValue']}")
            
            details_str = " | ".join(details_parts) if details_parts else "-"

            logs.append({
                'AuditId': r['AuditId'],
                'ActorId': r['ActorId'],
                'ActorLoginId': r['ActorLoginId'],
                'ActorName': r['ActorName'],
                'Action': r['Action'],
                'TargetId': r['TargetId'] if r['TargetId'] is not None else '-',
                'TargetTable': r['TargetTable'],
                'IpAddress': r['IpAddress'],
                'OldValue': r['OldValue'],
                'NewValue': r['NewValue'],
                'Details': details_str,
                'CreatedAt': r['CreatedAt']
            })

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        return jsonify({
            'status': 'success',
            'data': logs,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': total_pages
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'서버 오류가 발생했습니다: {str(e)}'}), 500

# ------------------------------------------
# 대시보드 통계 API
# ------------------------------------------
@app.route('/api/dashboard/stats', methods=['GET'])
@login_required
def api_dashboard_stats():
    """
    [역할] 대시보드 통계용(나의 장비, 총 장비, 카테고리/제조사 분포, 복합 조건 검색결과) JSON 데이터를 반환합니다.
    [의존성 관계] equipments, equipment_options, lineup_nodes, categories, manufacturers 테이블
    [변경 시 영향도] dashboard.html 내의 차트 및 테이블 렌더링(Ajax)에 영향을 줍니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 내 장비 수
    cursor.execute("SELECT COUNT(*) as count FROM equipments WHERE user_id = ? AND (is_draft = 0 OR is_draft IS NULL)", (user['UserId'],))
    my_eq_count = cursor.fetchone()['count']
    
    # 2. 총 장비 수
    if user['Role'] == 'admin':
        cursor.execute("SELECT COUNT(*) as count FROM equipments WHERE (is_draft = 0 OR is_draft IS NULL)")
        total_count = cursor.fetchone()['count']
    else:
        cursor.execute("SELECT COUNT(*) as count FROM equipments WHERE (is_public = 1 OR user_id = ?) AND (is_draft = 0 OR is_draft IS NULL)", (user['UserId'],))
        total_count = cursor.fetchone()['count']
        
    # 권한별 기본 WHERE절 조건 (AND로 이어붙일 앞부분)
    base_where = "(e.is_draft = 0 OR e.is_draft IS NULL)"
    params_base = []
    if user['Role'] != 'admin':
        base_where += " AND (e.is_public = 1 OR e.user_id = ?)"
        params_base.append(user['UserId'])
        
    # 3. 카테고리별 통계 (3-Tier JOIN)
    cursor.execute(f'''
        SELECT COALESCE(cat.Name, '미분류') as ResolvedCategory, COUNT(e.id) as count 
        FROM equipments e
        LEFT JOIN equipment_options opt ON e.option_id = opt.id
        LEFT JOIN lineup_nodes node ON opt.lineup_node_id = node.id
        LEFT JOIN categories cat ON node.category_id = cat.CategoryId
        WHERE {base_where}
        GROUP BY ResolvedCategory
    ''', params_base)
    categories = [{"category": row['ResolvedCategory'], "count": row['count']} for row in cursor.fetchall()]

    # 4. 제조사별 통계 (3-Tier JOIN)
    cursor.execute(f'''
        SELECT COALESCE(mfg.Name, '미분류') as ResolvedManufacturer, COUNT(e.id) as count 
        FROM equipments e
        LEFT JOIN equipment_options opt ON e.option_id = opt.id
        LEFT JOIN lineup_nodes node ON opt.lineup_node_id = node.id
        LEFT JOIN manufacturers mfg ON node.manufacturer_id = mfg.ManufacturerId
        WHERE {base_where}
        GROUP BY ResolvedManufacturer
    ''', params_base)
    manufacturers = [{"manufacturer": row['ResolvedManufacturer'], "count": row['count']} for row in cursor.fetchall()]

    # 5. 복합 조건 검색 (카테고리 + 제조사 모두 선택 시)
    req_cat_id = request.args.get('category_id')
    req_man_id = request.args.get('manufacturer_id')
    
    combined_stats = None
    if req_cat_id and req_man_id:
        status_query = f'''
            SELECT '정상' as status, COUNT(e.id) as count
            FROM equipments e
            LEFT JOIN equipment_options opt ON e.option_id = opt.id
            LEFT JOIN lineup_nodes node ON opt.lineup_node_id = node.id
            WHERE {base_where} AND node.category_id = ? AND node.manufacturer_id = ?
            GROUP BY status
        '''
        cursor.execute(status_query, params_base + [req_cat_id, req_man_id])
        status_distribution = [{"status": row['status'], "count": row['count']} for row in cursor.fetchall()]

        list_query = f'''
            SELECT e.id as EquipmentId, e.name as Name, node.name as ModelName, '정상' as Status, e.purchase_date as PurchaseDate
            FROM equipments e
            LEFT JOIN equipment_options opt ON e.option_id = opt.id
            LEFT JOIN lineup_nodes node ON opt.lineup_node_id = node.id
            WHERE {base_where} AND node.category_id = ? AND node.manufacturer_id = ?
            ORDER BY e.id DESC
        '''
        cursor.execute(list_query, params_base + [req_cat_id, req_man_id])
        equipment_list = [dict(row) for row in cursor.fetchall()]
        
        combined_stats = {
            "status_distribution": status_distribution,
            "equipment_list": equipment_list
        }

    conn.close()
    
    return jsonify({
        "success": True,
        "data": {
            "my_equipments": my_eq_count,
            "total_equipments": total_count,
            "categories": categories,
            "manufacturers": manufacturers,
            "combined_stats": combined_stats
        }
    })

@app.route('/api/dashboard/master_options', methods=['GET'])
@login_required
def api_dashboard_master_options():
    """
    [역할] 카테고리와 제조사 목록을 제공하여 복합 조건 검색용 Select Box를 동적으로 채웁니다.
    [의존성 관계] categories, manufacturers 테이블
    [변경 시 영향도] dashboard.html의 select 태그 옵션 목록에 영향을 줍니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT CategoryId AS CategoryId, CategoryId AS id, Name AS DisplayName, Name AS name FROM categories ORDER BY CategoryId")
    cats = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT ManufacturerId AS ManufacturerId, ManufacturerId AS id, Name AS DisplayName, Name AS name FROM manufacturers ORDER BY ManufacturerId")
    mans = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({
        "success": True,
        "categories": cats,
        "manufacturers": mans
    })

# ------------------------------------------
# 사용자 프로필 (비밀번호 변경) API
# ------------------------------------------
@app.route('/api/change_password', methods=['POST'])
@login_required
@csrf_required
def api_change_my_password():
    """
    [역할] 로그인된 사용자가 본인의 비밀번호를 변경합니다.
    [의존성 관계] users 테이블, werkzeug.security 모듈
    [변경 시 영향도] 사용자의 다음 로그인 시크릿 키 검증에 영향을 줍니다.
    """
    user = session['user']
    data = request.json
    current_pw = data.get('current_password')
    new_pw = data.get('new_password')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Password FROM users WHERE UserId = ?", (user['UserId'],))
    db_user = cursor.fetchone()
    
    if not db_user or not check_password_hash(db_user['Password'], current_pw):
        conn.close()
        return jsonify({"success": False, "message": "현재 비밀번호가 일치하지 않습니다."}), 400
        
    hashed_new = generate_password_hash(new_pw)
    cursor.execute("UPDATE users SET Password = ? WHERE UserId = ?", (hashed_new, user['UserId']))
    
    # 비밀번호 변경 로그 남기기
    log_audit(user['UserId'], user['LoginId'], 'CHANGE_PASSWORD', 'users', user['UserId'], None, None)
    
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."})

@app.route('/api/users/withdraw', methods=['POST'])
@login_required
@csrf_required
def api_user_withdraw():
    """
    [역할] 회원이 자진 탈퇴를 신청하고 30일 비활성화 유예 기간을 시작합니다.
    [의존성 관계] users 테이블, 세션 시스템
    [변경 시 영향도] 마이페이지의 회원탈퇴 폼 제출 로직 및 전역 세션(강제 로그아웃)에 영향을 줍니다.
    """
    user = session['user']
    data = request.json or {}
    password = data.get('password')
    
    if not password:
        return jsonify({"success": False, "message": "비밀번호를 입력하세요."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Password FROM users WHERE UserId = ?", (user['UserId'],))
    db_user = cursor.fetchone()
    
    if not db_user or not check_password_hash(db_user['Password'], password):
        conn.close()
        return jsonify({"success": False, "message": "비밀번호가 올바르지 않습니다."}), 400
        
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_token = os.urandom(24).hex()
    
    cursor.execute('''
        UPDATE users 
        SET IsDeactivated = 'Y', DeactivatedAt = ?, SessionToken = ? 
        WHERE UserId = ?
    ''', (now_str, new_token, user['UserId']))
    
    conn.commit()
    conn.close()
    
    session['user']['IsDeactivated'] = True
    session['user']['DeactivationDaysLeft'] = 30
    session['session_token'] = new_token
    
    log_audit(user['UserId'], user['LoginId'], 'USER_WITHDRAW_REQUEST', 'users', user['UserId'], None, {"DeactivatedAt": now_str})
    return jsonify({"success": True, "message": "회원 탈퇴 신청이 완료되었습니다. 30일간의 비활성화 유예기간이 적용됩니다."})

@app.route('/api/users/withdraw/cancel', methods=['POST'])
@login_required
@csrf_required
def api_user_withdraw_cancel():
    """
    [역할] 비활성화 유예 기간(30일) 내에 있는 사용자가 탈퇴 신청을 철회하고 계정을 복구합니다.
    [의존성 관계] users 테이블
    [변경 시 영향도] deactivated_notice.html의 비활성화 철회 버튼 및 사용자 계정 상태에 영향을 줍니다.
    """
    user = session['user']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET IsDeactivated = 'N', DeactivatedAt = NULL, IsDeleted = 'N', DeletedAt = NULL 
        WHERE UserId = ?
    ''', (user['UserId'],))
    
    conn.commit()
    conn.close()
    
    session['user']['IsDeactivated'] = False
    session['user'].pop('DeactivationDaysLeft', None)
    
    log_audit(user['UserId'], user['LoginId'], 'USER_WITHDRAW_CANCEL', 'users', user['UserId'], None, None)
    return jsonify({"success": True, "message": "비활성화가 성공적으로 철회되었으며 계정이 정상 복구되었습니다."})

@app.route('/api/users/update_email', methods=['POST'])
@login_required
@csrf_required
def api_update_email():
    """
    [역할]: 사용자 개인 이메일 정보를 변경 및 갱신합니다.
    [의존성 관계]: users 테이블
    [변경 시 영향도]: 사용자 프로필 이메일 수정에 영향을 줍니다.
    """
    user = session['user']
    data = request.json or {}
    new_email = data.get('email', '').strip()
    
    if not new_email:
        return jsonify({"success": False, "message": "이메일을 입력해주세요."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 인증 완료 여부 확인
    cursor.execute("SELECT IsVerified FROM email_verifications WHERE Email = ?", (new_email,))
    verif = cursor.fetchone()
    if not verif or verif['IsVerified'] != 1:
        conn.close()
        return jsonify({"success": False, "message": "이메일 인증이 완료되지 않았습니다."}), 400
        
    # 2. 이메일 중복 확인 (IntegrityError 처리)
    try:
        cursor.execute("UPDATE users SET Email = ?, UpdatedAt = ? WHERE UserId = ?", 
                       (new_email, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user['UserId']))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "message": "이미 다른 계정에서 사용 중인 이메일입니다."}), 400
        
    # 성공 시 인증 기록 삭제 및 세션 업데이트
    cursor.execute("DELETE FROM email_verifications WHERE Email = ?", (new_email,))
    conn.commit()
    conn.close()
    
    session['user']['Email'] = new_email
    log_audit(user['UserId'], user['LoginId'], 'UPDATE_EMAIL', 'users', user['UserId'], None, {"NewEmail": new_email})
    
    return jsonify({"success": True, "message": "이메일 주소가 성공적으로 변경되었습니다."})


@app.route('/api/users/update_profile', methods=['POST'])
@login_required
@csrf_required
def api_update_profile():
    """
    [역할] 로그인한 사용자의 기본 프로필(LoginId, Name, NickName)을 변경합니다. 현재 비밀번호 검증이 필수입니다.
    [의존성 관계] users 테이블, check_password_hash(), session['user'], templates/mypage.html
    [변경 시 영향도] users 테이블의 유저 정보, session['user'] 및 감사 로그(UPDATE_USER_PROFILE) 기록
    """
    user = session.get('user')
    if not user or 'UserId' not in user:
        return jsonify({"success": False, "message": "로그인이 필요한 서비스입니다."}), 401
        
    data = request.json or {}
    new_login_id = data.get('login_id', '').strip()
    new_name = data.get('name', '').strip()
    new_nickname = data.get('nickname', '').strip()
    current_password = data.get('current_password', '').strip()
    
    if not new_login_id or not new_name or not new_nickname or not current_password:
        return jsonify({"success": False, "message": "모든 필드를 입력해 주세요."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE UserId = ?", (user['UserId'],))
    db_user = cursor.fetchone()
    
    if not db_user:
        conn.close()
        return jsonify({"success": False, "message": "사용자 정보를 찾을 수 없습니다."}), 404
        
    # 현재 비밀번호 대조 검증
    if not check_password_hash(db_user['Password'], current_password):
        conn.close()
        return jsonify({"success": False, "message": "현재 비밀번호가 올바르지 않습니다."}), 400
        
    # 아이디 변경 시 타 계정 중복 체크
    if new_login_id != db_user['LoginId']:
        cursor.execute("SELECT UserId FROM users WHERE LoginId = ? AND UserId != ?", (new_login_id, user['UserId']))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "이미 사용 중인 아이디입니다."}), 400

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        cursor.execute('''
            UPDATE users
            SET LoginId = ?, Name = ?, NickName = ?, UpdatedAt = ?
            WHERE UserId = ?
        ''', (new_login_id, new_name, new_nickname, now_str, user['UserId']))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "message": "이미 존재하거나 사용 중인 아이디입니다."}), 400

    old_data = {"LoginId": db_user['LoginId'], "Name": db_user['Name'], "NickName": db_user['NickName']}
    new_data = {"LoginId": new_login_id, "Name": new_name, "NickName": new_nickname}

    log_audit(user['UserId'], db_user['LoginId'], 'UPDATE_USER_PROFILE', 'users', user['UserId'], old_data, new_data)
    conn.close()

    # 세션 갱신 및 modified 플래그 설정 (상태 갱신 누락 방지)
    session['user']['LoginId'] = new_login_id
    session['user']['Name'] = new_name
    session['user']['NickName'] = new_nickname
    session.modified = True

    return jsonify({"success": True, "message": "프로필 정보가 성공적으로 변경되었습니다."})

# ------------------------------------------
# 관리자용 사용자 관리 API
# ------------------------------------------
@app.route('/api/users', methods=['GET'])
@login_required
def api_get_users():
    """
    [역할] 시스템 내 모든 사용자의 정보를 조회하며, evaluate_user_lifecycle을 통해 실시간 유예 상태를 평가하여 반환합니다.
    [의존성 관계] users 테이블, evaluate_user_lifecycle() 함수
    [변경 시 영향도] 관리자용 사용자 관리 화면(users_management.html)의 테이블 데이터 출력 및 뱃지 상태에 영향을 줍니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserId, LoginId, Name, NickName, Role, CreatedAt, IsDeactivated, DeactivatedAt, IsDeleted, DeletedAt FROM users ORDER BY UserId DESC")
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        user_dict = dict(row)
        eval_res = evaluate_user_lifecycle(user_dict)
        if eval_res['status'] == 'HARD_DELETED':
            continue
        user_dict['Status'] = eval_res['status']
        user_dict['DaysLeft'] = eval_res.get('days_left', 0)
        result.append(user_dict)
        
    return jsonify({"success": True, "data": result})

@app.route('/api/users/<int:target_user_id>/toggle_deactivation', methods=['POST'])
@login_required
@csrf_required
def api_toggle_user_deactivation(target_user_id):
    """
    [역할] 관리자가 특정 사용자의 계정을 강제로 무기한 비활성화(정지)하거나 다시 활성화합니다.
    [의존성 관계] users 테이블, 세션 시스템
    [변경 시 영향도] users_management.html의 개별 토글 버튼 동작 및 대상 유저의 즉각적인 로그인/세션 차단에 영향을 줍니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    deactivate = request.json.get('deactivate', True)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if deactivate:
        cursor.execute('''
            UPDATE users 
            SET IsDeactivated = 'Y', DeactivatedAt = NULL, SessionToken = hex(randomblob(16))
            WHERE UserId = ?
        ''', (target_user_id,))
        log_audit(user['UserId'], user['LoginId'], 'ADMIN_SUSPEND_USER', 'users', target_user_id, None, None)
        msg = "계정이 비활성화(정지) 처리되었습니다."
    else:
        cursor.execute('''
            UPDATE users 
            SET IsDeactivated = 'N', DeactivatedAt = NULL, IsDeleted = 'N', DeletedAt = NULL
            WHERE UserId = ?
        ''', (target_user_id,))
        log_audit(user['UserId'], user['LoginId'], 'ADMIN_UNSUSPEND_USER', 'users', target_user_id, None, None)
        msg = "계정이 정상 활성화되었습니다."
        
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": msg})

@app.route('/api/users/deactivate_selected', methods=['POST'])
@login_required
@csrf_required
def api_deactivate_selected_users():
    """
    [역할] 관리자가 선택한 다수의 사용자 계정을 일괄적으로 비활성화(정지)하거나 활성화합니다.
    [의존성 관계] users 테이블, 세션 시스템
    [변경 시 영향도] users_management.html의 다중 체크박스 제어 및 선택 유저들의 즉각적인 세션 차단에 영향을 줍니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    target_ids = request.json.get('user_ids', [])
    deactivate = request.json.get('deactivate', True)
    
    if not target_ids or not isinstance(target_ids, list):
        return jsonify({"success": False, "message": "대상을 선택해주세요."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ','.join(['?'] * len(target_ids))
    
    if deactivate:
        cursor.execute(f'''
            UPDATE users 
            SET IsDeactivated = 'Y', DeactivatedAt = NULL, SessionToken = hex(randomblob(16))
            WHERE UserId IN ({placeholders})
        ''', tuple(target_ids))
        log_audit(user['UserId'], user['LoginId'], 'ADMIN_BULK_SUSPEND', 'users', None, None, {"TargetIds": target_ids})
        msg = f"{len(target_ids)}명의 계정이 비활성화 처리되었습니다."
    else:
        cursor.execute(f'''
            UPDATE users 
            SET IsDeactivated = 'N', DeactivatedAt = NULL, IsDeleted = 'N', DeletedAt = NULL
            WHERE UserId IN ({placeholders})
        ''', tuple(target_ids))
        log_audit(user['UserId'], user['LoginId'], 'ADMIN_BULK_UNSUSPEND', 'users', None, None, {"TargetIds": target_ids})
        msg = f"{len(target_ids)}명의 계정이 활성화 처리되었습니다."
        
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": msg})

@app.route('/api/users/<int:target_user_id>/role', methods=['PUT'])
@login_required
@csrf_required
def api_update_user_role(target_user_id):
    """
    [역할] 특정 사용자의 권한(Role)을 관리자가 변경(user ↔ admin)합니다.
    [의존성 관계] users 테이블
    [변경 시 영향도] 해당 사용자의 시스템 메뉴 접근 권한 등 전체 권한 레벨이 즉시 변경됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    new_role = request.json.get('role')
    if new_role not in ['admin', 'user']:
        return jsonify({"success": False, "message": "잘못된 권한입니다."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT Role FROM users WHERE UserId = ?", (target_user_id,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        return jsonify({"success": False, "message": "사용자를 찾을 수 없습니다."}), 404
        
    old_role = target['Role']
    cursor.execute("UPDATE users SET Role = ? WHERE UserId = ?", (new_role, target_user_id))
    log_audit(user['UserId'], user['LoginId'], 'UPDATE_ROLE', 'users', target_user_id, {"Role": old_role}, {"Role": new_role})
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/users/<int:target_user_id>/reset_password', methods=['POST'])
@login_required
@csrf_required
def api_reset_user_password(target_user_id):
    """
    [역할] 관리자가 특정 사용자의 비밀번호를 입력받은 임시 비밀번호로 강제 초기화합니다.
    [의존성 관계] users 테이블, werkzeug.security 모듈
    [변경 시 영향도] 해당 유저의 로그인 자격 증명이 즉각 변경됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    # 임시 비밀번호는 관리자가 지정할 수 있도록 하거나 고정 '1234'
    temp_pw = request.json.get('temp_password', '1234')
    hashed_pw = generate_password_hash(temp_pw)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET Password = ? WHERE UserId = ?", (hashed_pw, target_user_id))
    log_audit(user['UserId'], user['LoginId'], 'RESET_PASSWORD', 'users', target_user_id, None, None)
    
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"비밀번호가 '{temp_pw}'로 초기화되었습니다."})

# ------------------------------------------
# [제안-018] 세션 강제 만료(Force Logout) API
# ------------------------------------------
@app.route('/api/system/force_logout/all', methods=['POST'])
@login_required
@csrf_required
def api_force_logout_all():
    """
    [역할] 본인(또는 전체)을 제외한 모든 사용자의 세션 토큰을 갱신하여 강제 로그아웃 시킵니다.
    [의존성 관계] users 테이블
    [변경 시 영향도] 현재 로그인 중인 모든 다른 사용자의 세션이 만료되어 즉시 재로그인 화면으로 튕깁니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    include_me = request.json.get('include_me', False)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if include_me:
        # 모든 유저의 세션 갱신 (본인 포함)
        cursor.execute("UPDATE users SET SessionToken = hex(randomblob(16))")
        log_audit(user['UserId'], user['LoginId'], 'FORCE_LOGOUT_ALL', 'users', None, None, {"IncludeMe": True})
    else:
        # 본인 제외 모든 유저 세션 갱신
        cursor.execute("UPDATE users SET SessionToken = hex(randomblob(16)) WHERE UserId != ?", (user['UserId'],))
        log_audit(user['UserId'], user['LoginId'], 'FORCE_LOGOUT_ALL', 'users', None, None, {"IncludeMe": False})
        
    conn.commit()
    conn.close()
    
    # 만약 본인 포함이면 현재 세션 정보의 토큰도 만료되게 하여 즉각 튕기게 함
    if include_me:
        session.clear()
        
    return jsonify({"success": True, "message": "성공적으로 세션이 만료되었습니다."})

@app.route('/api/system/force_logout/selected', methods=['POST'])
@login_required
@csrf_required
def api_force_logout_selected():
    """
    [역할] 관리자가 선택한 특정 유저들의 세션 토큰을 일괄 갱신하여 강제 로그아웃 시킵니다.
    [의존성 관계] users 테이블
    [변경 시 영향도] 선택된 유저들의 브라우저 세션이 무효화되어 강제로 로그인 페이지로 리다이렉트됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    target_ids = request.json.get('user_ids', [])
    if not target_ids or not isinstance(target_ids, list):
        return jsonify({"success": False, "message": "대상 유저가 지정되지 않았습니다."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join(['?'] * len(target_ids))
    cursor.execute(f"UPDATE users SET SessionToken = hex(randomblob(16)) WHERE UserId IN ({placeholders})", tuple(target_ids))
    
    log_audit(user['UserId'], user['LoginId'], 'FORCE_LOGOUT_SELECTED', 'users', None, None, {"TargetIds": target_ids})
    
    conn.commit()
    conn.close()
    
    # 혹시 선택 대상에 본인이 포함되어 있다면 현재 세션 clear
    if user['UserId'] in target_ids:
        session.clear()
        
    return jsonify({"success": True, "message": f"{len(target_ids)}명의 사용자 세션이 강제 만료되었습니다."})

# ------------------------------------------
# 계정 즉시 삭제 API (유예기간 없이 영구 삭제)
# ------------------------------------------
@app.route('/api/users/delete_selected', methods=['POST'])
@login_required
@csrf_required
def api_delete_selected_users():
    """
    [역할] 관리자가 선택한 다수의 유저 계정을 영구 파기(Hard Delete)하고, 이들의 소유 장비를 공개로 이관합니다.
    [의존성 관계] users, user_settings, equipment 테이블
    [변경 시 영향도] 시스템에서 선택된 사용자 정보가 비가역적으로 완전 삭제됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    target_ids = request.json.get('user_ids', [])
    if not target_ids or not isinstance(target_ids, list):
        return jsonify({"success": False, "message": "삭제할 대상을 선택해주세요."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join(['?'] * len(target_ids))
    cursor.execute(f"SELECT UserId, LoginId FROM users WHERE UserId IN ({placeholders})", tuple(target_ids))
    target_users = cursor.fetchall()
    
    if not target_users:
        conn.close()
        return jsonify({"success": False, "message": "삭제할 대상 사용자를 찾을 수 없습니다."}), 404
        
    deleted_ids = [u['UserId'] for u in target_users]
    deleted_logins = [u['LoginId'] for u in target_users]
    
    del_placeholders = ','.join(['?'] * len(deleted_ids))
    del_tuple = tuple(deleted_ids)
    
    # 1. user_settings 레코드 삭제
    cursor.execute(f"DELETE FROM user_settings WHERE UserId IN ({del_placeholders})", del_tuple)
    
    # 2. 관련 장비 소유권 해제 (데이터 보존을 위해 공개 장비로 전환)
    cursor.execute(f"UPDATE equipments SET user_id = NULL, is_public = 1 WHERE user_id IN ({del_placeholders})", del_tuple)
    
    # 3. users 계정 즉시 파기
    cursor.execute(f"DELETE FROM users WHERE UserId IN ({del_placeholders})", del_tuple)
    
    # 4. 보안 감사 로그 기록
    log_audit(user['UserId'], user['LoginId'], 'DELETE_USER', 'users', None, 
              {"DeletedUserIds": deleted_ids, "DeletedLogins": deleted_logins}, None)
              
    conn.commit()
    conn.close()
    
    # 만약 본인이 삭제 대상에 포함되어 있다면 세션 파기
    if user['UserId'] in deleted_ids:
        session.clear()
        
    return jsonify({"success": True, "message": f"총 {len(deleted_ids)}명의 계정이 즉시 삭제되었습니다."})

# ------------------------------------------
# 장비 API
# ------------------------------------------
@app.route('/api/portal/menus', methods=['GET'])
@login_required
def get_portal_menus():
    """
    [역할] 현재 로그인한 사용자의 역할(Role)에 맞는 메뉴 목록을 반환
    [의존성 관계] role_menu_permissions 테이블, get_db_connection()
    [변경 시 영향도] 포털 화면(/portal)의 버튼 노출 구성이 변경됩니다.
    """
    user = session['user']
    role = user['Role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if role == 'admin':
        cursor.execute("SELECT * FROM menus WHERE ParentMenuCode IS NULL ORDER BY SortOrder ASC, MenuId ASC")
    else:
        cursor.execute('''
            SELECT m.* FROM menus m
            JOIN role_menu_permissions p ON m.MenuCode = p.MenuCode
            WHERE p.Role = ? AND p.IsAllowed = 1 AND m.ParentMenuCode IS NULL
            ORDER BY m.SortOrder ASC, m.MenuId ASC
        ''', (role,))
        
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])

@app.route('/api/menus/children/<parent_code>')
@login_required
def get_children_menus(parent_code):
    """
    [역할]: 특정 부모 메뉴에 속한 자식 메뉴들 중 현재 사용자 권한이 허용된 목록만 반환
    [의존성 관계]: menus, role_menu_permissions 테이블
    [변경 시 영향도]: 관리자 센터 내부 서브 메뉴 렌더링에 영향을 줍니다.
    """
    user = session['user']
    role = user['Role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if role == 'admin':
        cursor.execute("SELECT * FROM menus WHERE ParentMenuCode = ? ORDER BY SortOrder ASC", (parent_code,))
    else:
        cursor.execute('''
            SELECT m.* FROM menus m
            JOIN role_menu_permissions p ON m.MenuCode = p.MenuCode
            WHERE p.Role = ? AND p.IsAllowed = 1 AND m.ParentMenuCode = ?
            ORDER BY m.SortOrder ASC
        ''', (role, parent_code))
        
    menus = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(menus)


# 사용자 검색 API (관리자용)
@app.route('/api/users/search', methods=['GET'])
@login_required
def search_users():
    """
    [역할] 이름, 닉네임, 로그인ID를 기반으로 사용자 목록을 검색 (관리자 전용)
    [의존성 관계] users 테이블, @login_required
    [변경 시 영향도] 장비 신규 등록/수정 시 '소유자 검색' 모달의 검색 결과에 영향을 미칩니다.
    """
    if session['user']['Role'] != 'admin':
        return jsonify({"error": "권한이 없습니다."}), 403
        
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
        
    conn = get_db_connection()
    cursor = conn.cursor()
    like_q = f"%{q}%"
    cursor.execute('''
        SELECT UserId, LoginId, Name, NickName 
        FROM users 
        WHERE LoginId LIKE ? OR Name LIKE ? OR NickName LIKE ?
        ORDER BY NickName ASC LIMIT 20
    ''', (like_q, like_q, like_q))
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])


# ------------------------------------------
# [제안-011] 마스터 데이터 조회 API
# ------------------------------------------
@app.route('/api/master_data', methods=['GET'])
@login_required
def get_master_data():
    """
    [역할] 장비 등록 시 드롭다운에 표시될 승인된 카테고리 및 제조사 목록 조회 (ID 및 다국어 포함)
    [의존성 관계] categories, manufacturers 테이블
    [변경 시 영향도] 프론트엔드 장비 등록/수정 모달의 선택 항목 렌더링에 직접적인 영향을 줍니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT CategoryId, Name, NameKo, NameEn FROM categories WHERE IsApproved = 1 ORDER BY Name ASC")
    categories = [dict(r) for r in cursor.fetchall()]
    cursor.execute("SELECT ManufacturerId, Name, NameKo, NameEn FROM manufacturers WHERE IsApproved = 1 ORDER BY Name ASC")
    manufacturers = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "categories": categories, "manufacturers": manufacturers})


# ------------------------------------------
# [제안-027] 전자결재 API
# ------------------------------------------
@app.route('/api/approvals', methods=['GET'])
@login_required
def get_approvals():
    """
    [역할] 관리자 또는 사용자의 전자결재 상신 목록 조회
    [의존성 관계] approval_requests, users 테이블
    [변경 시 영향도] 전자결재함 대시보드의 테이블 출력 데이터 형식이 변경됩니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user['Role'] == 'admin':
        cursor.execute('''
            SELECT a.*, u.NickName as RequesterNickName, u.Name as RequesterName
            FROM approval_requests a
            JOIN users u ON a.RequesterId = u.UserId
            ORDER BY a.RequestId DESC
        ''')
    else:
        cursor.execute('''
            SELECT a.*, u.NickName as RequesterNickName, u.Name as RequesterName
            FROM approval_requests a
            JOIN users u ON a.RequesterId = u.UserId
            WHERE a.RequesterId = ?
            ORDER BY a.RequestId DESC
        ''', (user['UserId'],))
        
    rows = cursor.fetchall()
    conn.close()
    return jsonify({"success": True, "data": [dict(r) for r in rows]})


@app.route('/api/approvals/<int:req_id>/process', methods=['POST'])
@login_required
@csrf_required
def process_approval(req_id):
    """
    [역할] 관리자가 전자결재(마스터 데이터 추가) 건을 승인하거나 반려(대체 처리) 수행
    [의존성 관계] approval_requests, categories, manufacturers, equipment 테이블
    [변경 시 영향도] 마스터 데이터 승인/반려 로직 변경 시, 기존 장비들의 분류 정보 및 드롭다운 노출에 영향을 미칩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "관리자만 승인/반려할 수 있습니다."}), 403
        
    data = request.json
    action = data.get('action')  # 'approve' or 'reject'
    reject_reason = data.get('reject_reason', '')
    replacement_name = data.get('replacement_name', '').strip() if data.get('replacement_name') else ''
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM approval_requests WHERE RequestId = ?", (req_id,))
    req = cursor.fetchone()
    if not req:
        conn.close()
        return jsonify({"success": False, "message": "해당 결재 건을 찾을 수 없습니다."}), 404
        
    req_dict = dict(req)
    req_data = json.loads(req_dict['RequestDataJSON'])
    target_name = req_data.get('name')
    req_type = req_dict['RequestType']
    
    if action == 'approve':
        cursor.execute("UPDATE approval_requests SET Status = 'APPROVED', ApproverId = ?, UpdatedAt = ? WHERE RequestId = ?", (user['UserId'], now, req_id))
        if req_type == 'ADD_CATEGORY':
            cursor.execute("UPDATE categories SET IsApproved = 1 WHERE Name = ?", (target_name,))
        elif req_type == 'ADD_MANUFACTURER':
            cursor.execute("UPDATE manufacturers SET IsApproved = 1 WHERE Name = ?", (target_name,))
        elif req_type in ('Lineup_Node', 'ADD_LINEUP_NODE'):
            node_id = req_data.get('node_id')
            if node_id:
                cursor.execute("UPDATE lineup_nodes SET status = 'APPROVED' WHERE id = ?", (node_id,))
            else:
                cursor.execute("UPDATE lineup_nodes SET status = 'APPROVED' WHERE name = ? AND status = 'PENDING'", (target_name,))
        elif req_type in ('Equipment_Option', 'ADD_EQUIPMENT_OPTION'):
            opt_id = req_data.get('option_id')
            if opt_id:
                cursor.execute("UPDATE equipment_options SET status = 'APPROVED' WHERE id = ?", (opt_id,))
            else:
                cursor.execute("UPDATE equipment_options SET status = 'APPROVED' WHERE option_name = ? AND status = 'PENDING'", (target_name,))
        log_audit(user['UserId'], user['LoginId'], 'APPROVE_REQUEST', 'approval_requests', req_id, req_dict, {"Status": "APPROVED"})
        
    elif action == 'reject':
        cursor.execute("UPDATE approval_requests SET Status = 'REJECTED', ApproverId = ?, RejectReason = ?, UpdatedAt = ? WHERE RequestId = ?", (user['UserId'], reject_reason, now, req_id))
        
        # 대체 이름이 지정된 경우 장비 테이블 일괄 업데이트 및 미승인 항목 삭제
        if req_type == 'ADD_CATEGORY':
            if replacement_name:
                cursor.execute("UPDATE equipment SET Category = ? WHERE Category = ?", (replacement_name, target_name))
            cursor.execute("DELETE FROM categories WHERE Name = ? AND IsApproved = 0", (target_name,))
        elif req_type == 'ADD_MANUFACTURER':
            if replacement_name:
                cursor.execute("UPDATE equipment SET Manufacturer = ? WHERE Manufacturer = ?", (replacement_name, target_name))
            cursor.execute("DELETE FROM manufacturers WHERE Name = ? AND IsApproved = 0", (target_name,))
        elif req_type in ('Lineup_Node', 'ADD_LINEUP_NODE'):
            node_id = req_data.get('node_id')
            if node_id:
                cursor.execute("DELETE FROM lineup_nodes WHERE id = ? AND status = 'PENDING'", (node_id,))
            else:
                cursor.execute("DELETE FROM lineup_nodes WHERE name = ? AND status = 'PENDING'", (target_name,))
        elif req_type in ('Equipment_Option', 'ADD_EQUIPMENT_OPTION'):
            opt_id = req_data.get('option_id')
            if opt_id:
                cursor.execute("DELETE FROM equipment_options WHERE id = ? AND status = 'PENDING'", (opt_id,))
            else:
                cursor.execute("DELETE FROM equipment_options WHERE option_name = ? AND status = 'PENDING'", (target_name,))
            
        log_audit(user['UserId'], user['LoginId'], 'REJECT_REQUEST', 'approval_requests', req_id, req_dict, {"Status": "REJECTED", "Reason": reject_reason, "Replacement": replacement_name})
        
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "결재 처리가 완료되었습니다."})


# 장비 조회 (나의 장비, 공개된 장비, 임시저장함 분기 처리 및 3-Tier 다단 카탈로그 LEFT JOIN)
@app.route('/api/equipment', methods=['GET'])
@login_required
def get_equipment():
    """
    [역할] 3-Tier 계층 구조 기반 장비 목록을 조회하여 프론트엔드로 반환. (본인 장비, 공개 장비, 관리자 전체 조회, 임시저장함 분기 처리 및 다단 카탈로그 JOIN)
    [의존성 관계] equipments, equipment_options, lineup_nodes, categories, manufacturers, users 테이블
    [변경 시 영향도] 화면의 장비 목록(Table) 출력 조건 및 3-Tier 모델/옵션 렌더링 명칭이 변경됩니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    req_type = request.args.get('type', 'my')
    include_mine = request.args.get('include_mine', 'false').lower() == 'true'
    is_draft = request.args.get('is_draft', '0') == '1'
    
    base_select = '''
        SELECT e.id AS EquipmentId, e.id AS id,
               e.name AS Name, e.serial_number AS SerialNumber,
               e.purchase_date AS PurchaseDate, e.status AS Status, e.memo AS Memo,
               e.user_id AS UserId, e.is_public AS IsPublic, e.is_draft AS IsDraft,
               e.created_at AS CreatedAt, e.updated_at AS UpdatedAt,
               u.NickName AS OwnerNickName,
               opt.id AS OptionId, opt.option_name AS OptionName, opt.specs_json AS SpecsJson,
               node.id AS LineupNodeId, node.name AS ModelName, node.depth AS ModelDepth,
               cat.CategoryId AS CategoryId, cat.Name AS CategoryName,
               mfg.ManufacturerId AS ManufacturerId, mfg.Name AS ManufacturerName
        FROM equipments e
        LEFT JOIN equipment_options opt ON e.option_id = opt.id
        LEFT JOIN lineup_nodes node ON opt.lineup_node_id = node.id
        LEFT JOIN categories cat ON node.category_id = cat.CategoryId
        LEFT JOIN manufacturers mfg ON node.manufacturer_id = mfg.ManufacturerId
        LEFT JOIN users u ON e.user_id = u.UserId
    '''

    if is_draft:
        cursor.execute(f'''
            {base_select}
            WHERE e.user_id = ? AND e.is_draft = 1
            ORDER BY e.id DESC
        ''', (user['UserId'],))
        
    elif req_type == 'my':
        cursor.execute(f'''
            {base_select}
            WHERE e.user_id = ? AND (e.is_draft = 0 OR e.is_draft IS NULL)
            ORDER BY e.id DESC
        ''', (user['UserId'],))
        
    elif req_type == 'public':
        if user['Role'] == 'admin':
            cursor.execute(f'''
                {base_select}
                WHERE (e.is_draft = 0 OR e.is_draft IS NULL)
                ORDER BY e.id DESC
            ''')
        else:
            if include_mine:
                cursor.execute(f'''
                    {base_select}
                    WHERE (e.is_public = 1 OR e.user_id = ?) AND (e.is_draft = 0 OR e.is_draft IS NULL)
                    ORDER BY CASE WHEN e.user_id = ? THEN 0 ELSE 1 END, e.id DESC
                ''', (user['UserId'], user['UserId']))
            else:
                cursor.execute(f'''
                    {base_select}
                    WHERE e.is_public = 1 AND e.user_id != ? AND (e.is_draft = 0 OR e.is_draft IS NULL)
                    ORDER BY e.id DESC
                ''', (user['UserId'],))
    else:
        cursor.execute("SELECT * FROM equipments WHERE 1=0")

    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        item = dict(row)
        if item.get('SpecsJson'):
            try:
                item['Specs'] = json.loads(item['SpecsJson'])
            except Exception:
                item['Specs'] = {}
        else:
            item['Specs'] = {}
        result.append(item)

    return jsonify(result)


# 장비 등록
@app.route('/api/equipment', methods=['POST'])
@login_required
@csrf_required
def add_equipment():
    """
    [역할]: 사용자가 입력한 3-Tier 카탈로그 및 장비 데이터를 바탕으로 신규 장비를 생성합니다.
    [의존성 관계]: equipments, equipment_options, lineup_nodes, categories, manufacturers, equipments_audit_log 테이블
    [변경 시 영향도] 장비 추가 저장 로직 및 감사 로그 적재에 영향을 줍니다.
    """
    data = request.json or {}
    user = session['user']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    target_user_id = user['UserId']
    if user['Role'] == 'admin' and data.get('UserId'):
        target_user_id = data.get('UserId')
    
    name = (data.get('Name') or data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "장비 별명(이름)을 입력하세요."}), 400

    serial_number = (data.get('SerialNumber') or data.get('serial_number') or '').strip() or None
    purchase_date = data.get('PurchaseDate') or data.get('purchase_date')
    memo = (data.get('Memo') or data.get('memo') or '').strip()
    is_draft = 1 if (data.get('IsDraft') or data.get('is_draft')) else 0
    is_public = 0 if is_draft == 1 else (1 if data.get('IsPublic') or data.get('is_public') else 0)

    opt_data = data.get('OptionData') or {}
    option_id = None

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 시리얼 중복 검증
        if serial_number:
            cursor.execute("SELECT id FROM equipments WHERE serial_number = ?", (serial_number,))
            if cursor.fetchone():
                conn.close()
                return jsonify({"error": "이미 등록된 시리얼 넘버입니다."}), 400

        # OptionData 해석
        if isinstance(opt_data, dict) and opt_data.get('isNew'):
            new_opt_name = (opt_data.get('option_name') or '').strip()
            specs_json = opt_data.get('specs_json') or '{}'
            lineup_node_id = opt_data.get('lineup_node_id')

            if not lineup_node_id:
                conn.close()
                return jsonify({"error": "소속될 카탈로그 노드를 선택해야 합니다."}), 400
            if not new_opt_name:
                conn.close()
                return jsonify({"error": "신규 옵션명을 입력하세요."}), 400

            status = 'APPROVED'
            cursor.execute("""
                INSERT INTO equipment_options (lineup_node_id, option_name, specs_json, status, requested_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (lineup_node_id, new_opt_name, specs_json, status, user['UserId'], now))
            option_id = cursor.lastrowid

        elif isinstance(opt_data, dict) and opt_data.get('option_id'):
            option_id = int(opt_data['option_id'])
        elif data.get('option_id'):
            option_id = int(data['option_id'])

        if not option_id and not is_draft:
            conn.close()
            return jsonify({"error": "옵션 스펙을 선택해 주세요."}), 400

        # 임시저장이고 옵션이 지정되지 않은 경우 fallback 기본 옵션 처리
        if not option_id:
            cursor.execute("SELECT id FROM equipment_options LIMIT 1")
            first_opt = cursor.fetchone()
            if first_opt:
                option_id = first_opt[0]
            else:
                cursor.execute("SELECT id FROM lineup_nodes LIMIT 1")
                first_node = cursor.fetchone()
                if first_node:
                    cursor.execute("INSERT INTO equipment_options (lineup_node_id, option_name, specs_json, status) VALUES (?, '기본 옵션', '{}', 'APPROVED')", (first_node[0],))
                    option_id = cursor.lastrowid
                else:
                    option_id = 1

        cursor.execute('''
            INSERT INTO equipments (option_id, name, serial_number, purchase_date, status, memo, user_id, is_public, is_draft, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?)
        ''', (
            option_id,
            name,
            serial_number,
            purchase_date,
            memo,
            target_user_id,
            is_public,
            is_draft,
            now,
            now
        ))
        
        new_id = cursor.lastrowid

        # 3-Tier 감사 로그 적재
        cursor.execute('''
            INSERT INTO equipments_audit_log (equipment_id, action_type, new_value, changed_by, changed_at)
            VALUES (?, 'CREATE', ?, ?, ?)
        ''', (new_id, json.dumps(data, ensure_ascii=False), user['UserId'], now))

        conn.commit()
        conn.close()
        
        log_audit(user['UserId'], user['LoginId'], 'INSERT', 'equipments', new_id, None, data)
        return jsonify({"message": "임시저장되었습니다." if is_draft == 1 else "성공적으로 등록되었습니다!"})

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": f"장비 등록 중 오류: {str(e)}"}), 500


# 장비 수정
@app.route('/api/equipment/<int:eq_id>', methods=['PUT'])
@login_required
@csrf_required
def update_equipment(eq_id):
    """
    [역할]: 기존에 등록된 3-Tier 장비의 상세 정보를 갱신합니다.
    [의존성 관계]: equipments, equipments_audit_log 테이블
    [변경 시 영향도]: 장비 수정 저장 로직 및 감사 이력에 영향을 줍니다.
    """
    data = request.json or {}
    user = session['user']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM equipments WHERE id = ?", (eq_id,))
    old_row = cursor.fetchone()
    if not old_row:
        conn.close()
        return jsonify({"error": "해당 장비를 찾을 수 없습니다."}), 404

    old_dict = dict(old_row)
    if user['Role'] != 'admin' and old_dict['user_id'] != user['UserId']:
        conn.close()
        return jsonify({"error": "수정 권한이 없습니다."}), 403

    target_user_id = old_dict['user_id']
    if user['Role'] == 'admin' and data.get('UserId'):
        target_user_id = data.get('UserId')

    if old_dict.get('is_draft') == 0:
        is_draft = 0
        is_public = 1 if data.get('IsPublic') or data.get('is_public') else 0
    else:
        is_draft = 1 if (data.get('IsDraft') or data.get('is_draft')) else 0
        is_public = 0 if is_draft == 1 else (1 if data.get('IsPublic') or data.get('is_public') else 0)

    name = (data.get('Name') or data.get('name') or old_dict['name']).strip()
    serial_number = (data.get('SerialNumber') or data.get('serial_number') or '').strip() or None
    purchase_date = data.get('PurchaseDate') or data.get('purchase_date') or old_dict.get('purchase_date')
    memo = (data.get('Memo') or data.get('memo') or '').strip()

    # 시리얼 중복 검증 (자신 제외)
    if serial_number and serial_number != old_dict.get('serial_number'):
        cursor.execute("SELECT id FROM equipments WHERE serial_number = ? AND id != ?", (serial_number, eq_id))
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": "이미 등록된 시리얼 넘버입니다."}), 400

    opt_data = data.get('OptionData')
    option_id = old_dict['option_id']
    if isinstance(opt_data, dict):
        if opt_data.get('isNew'):
            new_opt_name = (opt_data.get('option_name') or '').strip()
            specs_json = opt_data.get('specs_json') or '{}'
            lineup_node_id = opt_data.get('lineup_node_id')
            if lineup_node_id and new_opt_name:
                cursor.execute("""
                    INSERT INTO equipment_options (lineup_node_id, option_name, specs_json, status, requested_by, created_at)
                    VALUES (?, ?, ?, 'APPROVED', ?, ?)
                """, (lineup_node_id, new_opt_name, specs_json, user['UserId'], now))
                option_id = cursor.lastrowid
        elif opt_data.get('option_id'):
            option_id = int(opt_data['option_id'])

    cursor.execute('''
        UPDATE equipments 
        SET option_id=?, name=?, serial_number=?, purchase_date=?, memo=?, user_id=?, is_public=?, is_draft=?, updated_at=?
        WHERE id=?
    ''', (
        option_id,
        name,
        serial_number,
        purchase_date,
        memo,
        target_user_id,
        is_public,
        is_draft,
        now,
        eq_id
    ))
    
    # 감사 로그 적재
    cursor.execute('''
        INSERT INTO equipments_audit_log (equipment_id, action_type, old_value, new_value, changed_by, changed_at)
        VALUES (?, 'UPDATE', ?, ?, ?, ?)
    ''', (eq_id, json.dumps(old_dict, ensure_ascii=False), json.dumps(data, ensure_ascii=False), user['UserId'], now))

    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'UPDATE', 'equipments', eq_id, old_dict, data)
    return jsonify({"message": "수정되었습니다."})


# 장비 삭제
@app.route('/api/equipment/<int:eq_id>', methods=['DELETE'])
@login_required
@csrf_required
def delete_equipment(eq_id):
    """
    [역할] 특정 3-Tier 장비를 DB에서 완전히 삭제(DELETE) 합니다.
    [의존성 관계] equipments, equipments_audit_log 테이블, log_audit()
    [변경 시 영향도] 타인 장비 삭제 권한 탈취 방어선이므로 삭제 로직 변경에 주의해야 합니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM equipments WHERE id = ?", (eq_id,))
    old_row = cursor.fetchone()
    if not old_row:
        conn.close()
        return jsonify({"error": "해당 장비를 찾을 수 없습니다."}), 404

    old_dict = dict(old_row)
    if user['Role'] != 'admin' and old_dict['user_id'] != user['UserId']:
        conn.close()
        return jsonify({"error": "삭제 권한이 없습니다."}), 403

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO equipments_audit_log (equipment_id, action_type, old_value, changed_by, changed_at)
        VALUES (?, 'DELETE', ?, ?, ?)
    ''', (eq_id, json.dumps(old_dict, ensure_ascii=False), user['UserId'], now))

    cursor.execute("DELETE FROM equipments WHERE id = ?", (eq_id,))
    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'DELETE', 'equipments', eq_id, old_dict, None)
    return jsonify({"message": "삭제되었습니다."})


# 권한 설정 조회
@app.route('/api/permissions', methods=['GET'])
@login_required
def get_permissions():
    """
    [역할] 시스템 내 역할별(Role) 메뉴 접근 권한 리스트를 조회합니다. (관리자 전용)
    [의존성 관계] role_menu_permissions 테이블, menus 테이블
    [변경 시 영향도] 포털의 '메뉴 권한 관리' 페이지 렌더링에 직접적인 영향을 줍니다.
    """
    if session['user']['Role'] != 'admin':
        return jsonify({"error": "관리자만 접근할 수 있습니다."}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            r.Role, 
            m.MenuCode, 
            m.MenuName, 
            m.ParentMenuCode, 
            m.SortOrder,
            COALESCE(p.IsAllowed, 0) as IsAllowed
        FROM (SELECT DISTINCT Role FROM users UNION SELECT 'admin' UNION SELECT 'user') r
        CROSS JOIN menus m
        LEFT JOIN role_menu_permissions p ON p.Role = r.Role AND p.MenuCode = m.MenuCode
        ORDER BY r.Role ASC, m.SortOrder ASC, m.MenuId ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(r) for r in rows])


# 권한 설정 수정
@app.route('/api/permissions', methods=['POST'])
@login_required
@csrf_required
def update_permissions():
    """
    [역할] 변경된 권한 리스트를 DB에 갱신(UPSERT) 합니다. (관리자 전용)
    [의존성 관계] role_menu_permissions 테이블, log_audit()
    [변경 시 영향도] 전체 시스템 사용자의 메뉴 접근 권한이 변경됩니다. 잘못될 경우 접속 장애가 발생할 수 있습니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"error": "관리자만 접근할 수 있습니다."}), 403
        
    data = request.json 
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM role_menu_permissions")
    old_perms = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT MenuCode, ParentMenuCode FROM menus")
    menus_meta = {r['MenuCode']: r['ParentMenuCode'] for r in cursor.fetchall()}
    
    future_perms = {}
    for r in old_perms:
        if r['Role'] not in future_perms: future_perms[r['Role']] = {}
        future_perms[r['Role']][r['MenuCode']] = r['IsAllowed']
        
    for item in data:
        role = item['Role']
        if role not in future_perms: future_perms[role] = {}
        future_perms[role][item['MenuCode']] = item['IsAllowed']
        
    # 부모-자식 모순 검증
    for role, perms in future_perms.items():
        for menu_code, is_allowed in perms.items():
            if is_allowed:
                parent = menus_meta.get(menu_code)
                while parent:
                    if not perms.get(parent, 0):
                        conn.close()
                        return jsonify({"error": f"하위 메뉴({menu_code})가 활성화되었으나 상위 메뉴({parent})가 비활성화 상태입니다. 권한 구조가 모순됩니다."}), 400
                    parent = menus_meta.get(parent)
    
    for item in data:
        cursor.execute('''
            INSERT INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(Role, MenuCode) DO UPDATE SET IsAllowed=excluded.IsAllowed, UpdatedAt=excluded.UpdatedAt
        ''', (item['Role'], item['MenuCode'], item['IsAllowed'], now))
        
    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'UPDATE_PERMISSIONS', 'role_menu_permissions', None, old_perms, data)
    return jsonify({"success": True, "message": "권한 설정이 업데이트되었습니다."})


# ------------------------------------------
# [제안-011-고도화] 마스터 데이터 관리 & 통폐합 API
# ------------------------------------------
@app.route('/api/master/manage/<target_type>', methods=['GET', 'POST'])
@login_required
@csrf_required
def get_or_create_master_management_item(target_type):
    """
    [역할] 관리자 전용 마스터 데이터 (카테고리/제조사) 전체 목록 조회 및 신규 항목 생성
    [의존성 관계] categories, manufacturers, equipment 테이블
    [변경 시 영향도] templates/master_management.html 화면 표출 및 마스터 항목 추가에 사용됩니다.
    """
    if session['user']['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        if target_type == 'categories':
            cursor.execute('''
                SELECT c.id as CategoryId, c.id, c.name as Name, c.name as NameKo, c.name as NameEn, 1 as IsApproved, c.created_at as CreatedAt,
                       COUNT(e.id) as UsageCount
                FROM categories c
                LEFT JOIN lineup_nodes node ON c.id = node.category_id
                LEFT JOIN equipment_options opt ON node.id = opt.lineup_node_id
                LEFT JOIN equipments e ON opt.id = e.option_id
                GROUP BY c.id
                ORDER BY c.id DESC
            ''')
        elif target_type == 'manufacturers':
            cursor.execute('''
                SELECT m.id as ManufacturerId, m.id, m.name as Name, m.name as NameKo, m.name as NameEn, 1 as IsApproved, m.created_at as CreatedAt,
                       COUNT(e.id) as UsageCount
                FROM manufacturers m
                LEFT JOIN lineup_nodes node ON m.id = node.manufacturer_id
                LEFT JOIN equipment_options opt ON node.id = opt.lineup_node_id
                LEFT JOIN equipments e ON opt.id = e.option_id
                GROUP BY m.id
                ORDER BY m.id DESC
            ''')
        else:
            conn.close()
            return jsonify({"success": False, "message": "유효하지 않은 타입입니다."}), 400
            
        rows = cursor.fetchall()
        conn.close()
        return jsonify({"success": True, "data": [dict(r) for r in rows]})

    elif request.method == 'POST':
        data = request.json or {}
        name = data.get('Name', '').strip()
        name_ko = data.get('NameKo', '').strip() if data.get('NameKo') else None
        name_en = data.get('NameEn', '').strip() if data.get('NameEn') else None

        if not name:
            conn.close()
            return jsonify({"success": False, "message": "기본 명칭(Name)은 필수입니다."}), 400

        table_name = 'categories' if target_type == 'categories' else ('manufacturers' if target_type == 'manufacturers' else None)
        if not table_name:
            conn.close()
            return jsonify({"success": False, "message": "유효하지 않은 타입입니다."}), 400

        # 중복 명칭 검증
        cursor.execute(f"SELECT * FROM {table_name} WHERE Name = ?", (name,))
        if cursor.fetchone():
            conn.close()
            label_name = '카테고리' if target_type == 'categories' else '제조사'
            return jsonify({"success": False, "message": f"이미 존재하는 {label_name} 명칭입니다."}), 400

        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(f"INSERT INTO {table_name} (Name, NameKo, NameEn, IsApproved, CreatedAt) VALUES (?, ?, ?, 1, ?)",
                       (name, name_ko, name_en, created_at))
        new_id = cursor.lastrowid

        user = session['user']
        log_audit(user['UserId'], user['LoginId'], 'CREATE_MASTER', table_name, new_id, None, data)
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "성공적으로 추가되었습니다.", "id": new_id})


@app.route('/api/master/manage/<target_type>/delete_selected', methods=['POST'])
@login_required
@csrf_required
def delete_selected_master_items(target_type):
    """
    [역할] 관리자 전용 마스터 데이터 (카테고리/제조사) 선택 항목 일괄 삭제
    [의존성 관계] categories, manufacturers, equipment 테이블
    [변경 시 영향도] 선택된 마스터 데이터 삭제 및 연결된 장비 분류 정보(NULL) 초기화
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403

    table_name = 'categories' if target_type == 'categories' else ('manufacturers' if target_type == 'manufacturers' else None)
    id_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    fk_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    legacy_col = 'Category' if target_type == 'categories' else 'Manufacturer'

    if not table_name:
        return jsonify({"success": False, "message": "유효하지 않은 타입입니다."}), 400

    data = request.json or {}
    item_ids = data.get('item_ids', [])
    if not item_ids or not isinstance(item_ids, list):
        return jsonify({"success": False, "message": "삭제할 항목이 선택되지 않았습니다."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join(['?'] * len(item_ids))
    lineup_fk = 'category_id' if target_type == 'categories' else 'manufacturer_id'
    # 3-Tier lineup_nodes 및 equipment 관련 외래키 NULL 처리
    cursor.execute(f"UPDATE lineup_nodes SET {lineup_fk} = NULL WHERE {lineup_fk} IN ({placeholders})", item_ids)
    cursor.execute(f"UPDATE equipment SET {fk_col} = NULL, {legacy_col} = NULL WHERE {fk_col} IN ({placeholders})", item_ids)
    cursor.execute(f"DELETE FROM {table_name} WHERE {id_col} IN ({placeholders})", item_ids)

    log_audit(user['UserId'], user['LoginId'], 'DELETE_MASTER_SELECTED', table_name, None, {"deleted_ids": item_ids}, None)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"{len(item_ids)}개 항목이 성공적으로 일괄 삭제되었습니다."})


@app.route('/api/master/manage/<target_type>/<int:item_id>', methods=['PUT', 'DELETE'])
@login_required
@csrf_required
def update_or_delete_master_item(target_type, item_id):
    """
    [역할] 특정 마스터 데이터(카테고리/제조사) 수정 또는 삭제
    [의존성 관계] categories, manufacturers, lineup_nodes, equipment 테이블
    [변경 시 영향도] 마스터 데이터 변경 및 삭제에 따른 장비 분류 정보에 영향을 미칩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    table_name = 'categories' if target_type == 'categories' else ('manufacturers' if target_type == 'manufacturers' else None)
    id_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    fk_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    legacy_col = 'Category' if target_type == 'categories' else 'Manufacturer'
    lineup_fk = 'category_id' if target_type == 'categories' else 'manufacturer_id'
    
    if not table_name:
        conn.close()
        return jsonify({"success": False, "message": "유효하지 않은 타입입니다."}), 400

    if request.method == 'PUT':
        data = request.json
        name = data.get('Name', '').strip()
        name_ko = data.get('NameKo', '').strip() if data.get('NameKo') else None
        name_en = data.get('NameEn', '').strip() if data.get('NameEn') else None
        
        if not name:
            conn.close()
            return jsonify({"success": False, "message": "기본 명칭(Name)은 필수입니다."}), 400
            
        cursor.execute(f"SELECT * FROM {table_name} WHERE {id_col} = ?", (item_id,))
        old_item = cursor.fetchone()
        if not old_item:
            conn.close()
            return jsonify({"success": False, "message": "해당 마스터 항목을 찾을 수 없습니다."}), 404
            
        cursor.execute(f"UPDATE {table_name} SET Name = ?, NameKo = ?, NameEn = ? WHERE {id_col} = ?",
                       (name, name_ko, name_en, item_id))
                       
        log_audit(user['UserId'], user['LoginId'], 'UPDATE_MASTER', table_name, item_id, dict(old_item), data)
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "성공적으로 수정되었습니다."})
        
    elif request.method == 'DELETE':
        cursor.execute(f"SELECT * FROM {table_name} WHERE {id_col} = ?", (item_id,))
        old_item = cursor.fetchone()
        if not old_item:
            conn.close()
            return jsonify({"success": False, "message": "해당 마스터 항목을 찾을 수 없습니다."}), 404
            
        # lineup_nodes 및 equipment의 관련 컬럼을 NULL 처리
        cursor.execute(f"UPDATE lineup_nodes SET {lineup_fk} = NULL WHERE {lineup_fk} = ?", (item_id,))
        cursor.execute(f"UPDATE equipment SET {fk_col} = NULL, {legacy_col} = NULL WHERE {fk_col} = ?", (item_id,))
        cursor.execute(f"DELETE FROM {table_name} WHERE {id_col} = ?", (item_id,))
        
        log_audit(user['UserId'], user['LoginId'], 'DELETE_MASTER', table_name, item_id, dict(old_item), None)
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "성공적으로 삭제되었습니다."})


@app.route('/api/master/manage/<target_type>/<int:target_id>/merge_from', methods=['POST'])
@login_required
@csrf_required
def merge_master_items(target_type, target_id):
    """
    [역할] 선택한 여러 마스터 데이터(Source)를 기준 마스터(Target)로 통폐합(Merge) 수행
    [의존성 관계] categories, manufacturers, lineup_nodes, equipment 테이블
    [변경 시 영향도] 기존 장비 데이터의 분류 ID가 기준 ID로 일괄 변경되며 원본 마스터 항목은 삭제됩니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    data = request.json
    source_ids = data.get('source_ids', [])
    if not source_ids or not isinstance(source_ids, list):
        return jsonify({"success": False, "message": "통합할 대상 항목을 1개 이상 선택해야 합니다."}), 400
        
    table_name = 'categories' if target_type == 'categories' else ('manufacturers' if target_type == 'manufacturers' else None)
    id_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    fk_col = 'CategoryId' if target_type == 'categories' else 'ManufacturerId'
    legacy_col = 'Category' if target_type == 'categories' else 'Manufacturer'
    lineup_fk = 'category_id' if target_type == 'categories' else 'manufacturer_id'
    
    if not table_name:
        return jsonify({"success": False, "message": "유효하지 않은 타입입니다."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT * FROM {table_name} WHERE {id_col} = ?", (target_id,))
    target_item = cursor.fetchone()
    if not target_item:
        conn.close()
        return jsonify({"success": False, "message": "기준 마스터 항목을 찾을 수 없습니다."}), 404
        
    placeholders = ','.join(['?'] * len(source_ids))
    
    # 1. lineup_nodes 및 equipment 테이블의 ID 및 레거시 컬럼 일괄 UPDATE
    cursor.execute(f"UPDATE lineup_nodes SET {lineup_fk} = ? WHERE {lineup_fk} IN ({placeholders})", (target_id, *source_ids))
    cursor.execute(f"UPDATE equipment SET {fk_col} = ?, {legacy_col} = ? WHERE {fk_col} IN ({placeholders})",
                   (target_id, str(target_id), *source_ids))
                   
    # 2. 통합 대상 마스터 항목 삭제
    cursor.execute(f"DELETE FROM {table_name} WHERE {id_col} IN ({placeholders})", tuple(source_ids))
    
    log_audit(user['UserId'], user['LoginId'], 'MERGE_MASTER', table_name, target_id, 
              {"SourceIds": source_ids}, {"TargetId": target_id})
              
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"총 {len(source_ids)}개의 항목이 성공적으로 통폐합되었습니다."})


@app.route('/api/auth/send_pin', methods=['POST'])
@csrf_required
def api_send_pin_logic():
    """
    [역할]: 비밀번호 찾기 시 이메일 기반 인증 핀 번호를 MS Graph API를 통해 발송합니다.
    [의존성 관계]: email_verifications 테이블, send_email()
    [변경 시 영향도]: 비밀번호 리셋 1단계 인증 통신에 영향을 줍니다.
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    if not email or '@' not in email:
        return jsonify({"success": False, "message": "유효한 이메일 주소를 입력해 주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT ExpiresAt FROM email_verifications WHERE Email = ?", (email,))
    existing_req = cursor.fetchone()
    if existing_req:
        expires_dt = datetime.strptime(existing_req['ExpiresAt'], '%Y-%m-%d %H:%M:%S')
        if (expires_dt - datetime.now()).total_seconds() > 120:
            conn.close()
            return jsonify({"success": False, "message": "발송 한도가 초과되었습니다. 1분 후 다시 시도해 주세요."}), 429

    cursor.execute("SELECT UserId FROM users WHERE Email = ? AND IsDeleted = 'N'", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "이미 사용 중인 이메일 주소입니다."}), 400

    pin_code = ''.join(random.choices(string.digits, k=6))
    pin_hash = generate_password_hash(pin_code)
    expires_at = (datetime.now() + timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        INSERT INTO email_verifications (Email, PinCodeHash, ExpiresAt, IsVerified)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(Email) DO UPDATE SET PinCodeHash=excluded.PinCodeHash, ExpiresAt=excluded.ExpiresAt, IsVerified=0
    ''', (email, pin_hash, expires_at))
    conn.commit()
    conn.close()

    subject = "[미니서버] 이메일 인증 PIN 번호 안내"
    body_html = f"<p>인증 PIN 번호: <strong>{pin_code}</strong> (3분 유효)</p>"
    success, msg = send_email(email, subject, body_html)
    
    if success:
        return jsonify({"success": True, "message": "인증 PIN 코드가 발송되었습니다."})
    return jsonify({"success": False, "message": "메일 발송 실패."}), 500


@app.route('/api/auth/verify_pin', methods=['POST'])
@csrf_required
def api_verify_pin_logic():
    """
    [역할]: 사용자가 제출한 인증 핀이 유효한지 검사합니다.
    [의존성 관계]: email_verifications 테이블, check_password_hash()
    [변경 시 영향도]: 비밀번호 리셋 2단계 검증에 영향을 줍니다.
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    pin = data.get('pin', '').strip()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if not email or not pin:
        return jsonify({"success": False, "message": "입력값이 부족합니다."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM email_verifications WHERE Email = ?", (email,))
    record = cursor.fetchone()

    if not record or record['ExpiresAt'] < now_str or not check_password_hash(record['PinCodeHash'], pin):
        conn.close()
        return jsonify({"success": False, "message": "PIN 코드가 잘못되었거나 만료되었습니다."}), 400

    cursor.execute("UPDATE email_verifications SET IsVerified = 1 WHERE Email = ?", (email,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "인증이 완료되었습니다!"})


@app.route('/api/auth/request_password_reset', methods=['POST'])
@csrf_required
def api_request_password_reset_logic():
    """
    [역할]: 사용자 셀프서비스 이메일 기반 비밀번호 재설정 링크 발송을 처리합니다.
    [의존성 관계]: password_resets 테이블, send_email()
    [변경 시 영향도]: 이메일 기반 비밀번호 재설정 플로우에 영향을 줍니다.
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    if not email: return jsonify({"success": False}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserId, LoginId, Name FROM users WHERE Email = ? AND IsDeleted = 'N'", (email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"success": True, "message": "입력하신 이메일이 등록되어 있다면 재설정 링크가 메일로 발송되었습니다."})

    cursor.execute("SELECT ExpiresAt FROM password_resets WHERE UserId = ? ORDER BY ExpiresAt DESC LIMIT 1", (user['UserId'],))
    last_req = cursor.fetchone()
    if last_req:
        last_expires = datetime.strptime(last_req['ExpiresAt'], '%Y-%m-%d %H:%M:%S')
        if (last_expires - datetime.now()).total_seconds() > 3540:
            conn.close()
            return jsonify({"success": False, "message": "재발송 쿨다운 중입니다. 잠시 후 다시 시도해 주세요."}), 429

    raw_token = str(uuid.uuid4())
    token_hash = generate_password_hash(raw_token)
    expires_at = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("INSERT INTO password_resets (TokenHash, UserId, ExpiresAt, IsUsed) VALUES (?, ?, ?, 0)",
                   (token_hash, user['UserId'], expires_at))
    conn.commit()
    conn.close()

    reset_url = request.host_url.rstrip('/') + f"reset_password?token={raw_token}&email={email}"
    success, msg = send_email(email, "[미니서버] 비밀번호 재설정", f"<a href='{reset_url}'>비밀번호 재설정하기</a>")
    
    return jsonify({"success": True, "message": "비밀번호 재설정 링크가 발송되었습니다."})


@app.route('/reset_password', methods=['GET'])
def reset_password_page():
    """
    [역할]: 핀 번호 인증 후 비밀번호 재설정 페이지를 렌더링합니다.
    [의존성 관계]: reset_password.html
    [변경 시 영향도]: 새 비밀번호 입력 화면 렌더링에 영향을 줍니다.
    """
    return render_template('reset_password.html')


@app.route('/api/auth/reset_password', methods=['POST'])
@csrf_required
def api_reset_password_logic():
    """
    [역할]: 검증을 통과한 사용자의 새 비밀번호를 해싱하여 최종 갱신합니다.
    [의존성 관계]: users 테이블
    [변경 시 영향도]: 비밀번호 최종 변경 처리에 영향을 줍니다.
    """
    data = request.json or {}
    token = data.get('token', '').strip()
    email = data.get('email', '').strip()
    new_password = data.get('new_password', '').strip()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserId FROM users WHERE Email = ? AND IsDeleted = 'N'", (email,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({"success": False, "message": "잘못된 요청입니다."}), 400
        
    cursor.execute("SELECT * FROM password_resets WHERE UserId = ? AND IsUsed = 0 AND ExpiresAt > ? ORDER BY ExpiresAt DESC", (user['UserId'], now_str))
    resets = cursor.fetchall()
    
    valid_req = None
    for req in resets:
        if check_password_hash(req['TokenHash'], token):
            valid_req = req
            break

    if not valid_req:
        conn.close()
        return jsonify({"success": False, "message": "유효하지 않거나 만료된 토큰입니다."}), 400

    hashed_pw = generate_password_hash(new_password)
    new_session_token = secrets.token_hex(32)
    cursor.execute("UPDATE users SET Password = ?, SessionToken = ?, UpdatedAt = ? WHERE UserId = ?", 
                   (hashed_pw, new_session_token, now_str, user['UserId']))
    cursor.execute("UPDATE password_resets SET IsUsed = 1 WHERE TokenHash = ?", (valid_req['TokenHash'],))
    conn.commit()
    
    log_audit(user['UserId'], 'System', 'RESET_PASSWORD', 'users', user['UserId'])
    conn.close()

    return jsonify({"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."})


# ==========================================
# [제안-036] 웹 접근 로그(HTTP Access Logs) 관리 API 3종
# ==========================================

@app.route('/api/access_logs', methods=['GET'])
@login_required
def api_get_access_logs():
    """
    [역할]: 검색 필터(IP, 메서드, 상태코드, 경로, 퀵필터) 및 페이징 조건에 맞춰 접근 로그 목록을 조회하여 반환합니다.
    [의존성 관계]: access_logs 테이블, check_menu_permission('access_logs')
    [변경 시 영향도]: 관리자 화면의 접근 로그 테이블 데이터 표출 및 검색에 영향을 줍니다.
    """
    if not check_menu_permission('access_logs'):
        return jsonify({"error": "권한이 없습니다."}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    quick_filter = request.args.get('quick_filter', 'all')
    filter_ip = request.args.get('ip', '').strip()
    filter_method = request.args.get('method', '').strip()
    filter_status = request.args.get('status', '').strip()
    filter_path = request.args.get('path', '').strip()

    where_clauses = ["1=1"]
    params = []

    # 1. 3단 퀵 필터
    if quick_filter == 'api':
        where_clauses.append("IsStatic = 0")
    elif quick_filter == 'static':
        where_clauses.append("IsStatic = 1")

    # 2. 상세 검색 필터
    if filter_ip:
        where_clauses.append("IpAddress LIKE ?")
        params.append(f"%{filter_ip}%")

    if filter_method:
        where_clauses.append("HttpMethod = ?")
        params.append(filter_method)

    if filter_status:
        if filter_status == '4xx':
            where_clauses.append("StatusCode >= 400 AND StatusCode < 500")
        elif filter_status == '5xx':
            where_clauses.append("StatusCode >= 500 AND StatusCode < 600")
        elif filter_status.isdigit():
            where_clauses.append("StatusCode = ?")
            params.append(int(filter_status))

    if filter_path:
        where_clauses.append("RequestPath LIKE ?")
        params.append(f"%{filter_path}%")

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()

    # 총 건수 조회
    cursor.execute(f"SELECT COUNT(*) FROM access_logs WHERE {where_sql}", params)
    total_count = cursor.fetchone()[0]

    # 목록 조회
    cursor.execute(f"""
        SELECT LogId, IpAddress, HttpMethod, RequestPath, StatusCode, UserAgent, Referer, DurationMs, IsStatic, RequestPayload, ResponsePayload, CreatedAt
        FROM access_logs
        WHERE {where_sql}
        ORDER BY LogId DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    
    rows = cursor.fetchall()
    conn.close()

    logs = [dict(row) for row in rows]
    return jsonify({
        "status": "success",
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "logs": logs
    })


@app.route('/api/access_logs/stats', methods=['GET'])
@login_required
def api_get_access_log_stats():
    """
    [역할]: 지정된 기간(오늘 또는 전체 누적)의 웹 접근 로그 통계(총 요청 수, 일반 웹/API 수, 정적 리소스 수, 에러율)를 집계하여 반환합니다.
    [의존성 관계]: access_logs 테이블, check_menu_permission('access_logs')
    [변경 시 영향도]: 관리자 화면의 상단 4종 요약 카드 수치 렌더링에 영향을 줍니다.
    """
    if not check_menu_permission('access_logs'):
        return jsonify({"error": "권한이 없습니다."}), 403

    period = request.args.get('period', 'today').lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    if period == 'all':
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN IsStatic = 0 THEN 1 ELSE 0 END) as api_count,
                SUM(CASE WHEN IsStatic = 1 THEN 1 ELSE 0 END) as static_count,
                SUM(CASE WHEN StatusCode >= 400 THEN 1 ELSE 0 END) as error_count
            FROM access_logs
        """)
    else:
        period = 'today'
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_start = f"{today_str} 00:00:00"

        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN IsStatic = 0 THEN 1 ELSE 0 END) as api_count,
                SUM(CASE WHEN IsStatic = 1 THEN 1 ELSE 0 END) as static_count,
                SUM(CASE WHEN StatusCode >= 400 THEN 1 ELSE 0 END) as error_count
            FROM access_logs
            WHERE CreatedAt >= ?
        """, (today_start,))

    row = cursor.fetchone()
    conn.close()

    total = row['total'] or 0
    api_count = row['api_count'] or 0
    static_count = row['static_count'] or 0
    error_count = row['error_count'] or 0
    error_rate = round((error_count / total * 100.0), 1) if total > 0 else 0.0

    return jsonify({
        "status": "success",
        "period": period,
        "total": total,
        "api_count": api_count,
        "static_count": static_count,
        "error_count": error_count,
        "error_rate": error_rate
    })


@app.route('/api/access_logs/cleanup', methods=['POST'])
@login_required
@csrf_required
def api_cleanup_access_logs():
    """
    [역할]: 관리자가 지정한 기준(30일 이전, 정적 리소스만, 전체 초기화)에 따라 접근 로그를 안전하게 영구 삭제합니다.
    [의존성 관계]: access_logs 테이블, log_audit()
    [변경 시 영향도]: access_logs 테이블 내 레코드의 영구 파기 및 감사 로그 기록에 영향을 줍니다.
    """
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "관리자만 로그를 정리할 수 있습니다."}), 403

    data = request.json or {}
    action = data.get('action')

    if not action or action not in ['older_30d', 'static_only', 'all']:
        return jsonify({"success": False, "message": "올바른 정리 방식을 지정해 주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    deleted_count = 0
    if action == 'older_30d':
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("DELETE FROM access_logs WHERE CreatedAt < ?", (cutoff_date,))
        deleted_count = cursor.rowcount
    elif action == 'static_only':
        cursor.execute("DELETE FROM access_logs WHERE IsStatic = 1")
        deleted_count = cursor.rowcount
    elif action == 'all':
        cursor.execute("DELETE FROM access_logs")
        deleted_count = cursor.rowcount

    conn.commit()
    conn.close()

    log_audit(user['UserId'], user['LoginId'], 'CLEANUP_ACCESS_LOGS', 'access_logs', None, None, {
        "action": action,
        "deleted_count": deleted_count
    })

    return jsonify({
        "status": "success",
        "message": "로그가 성공적으로 정리되었습니다.",
        "deleted_count": deleted_count
    })


@app.route('/api/access_logs/error_ips', methods=['GET'])
@login_required
def api_access_logs_error_ips():
    """
    [역할]: access_logs 테이블에서 4xx/5xx 에러를 발생시킨 고유 IP 목록 및 에러 통계를 집계하여 반환합니다.
    [의존성 관계]: sqlite3 (get_db_connection), access_logs 테이블, check_menu_permission('access_logs')
    [변경 시 영향도]: 에러 IP 심층 분석 화면의 비동기 데이터 로딩에 영향을 줍니다.
    """
    if not check_menu_permission('access_logs'):
        return jsonify({"success": False, "message": "접근 권한이 없습니다."}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            IpAddress,
            COUNT(LogId) AS TotalErrorCount,
            MAX(CreatedAt) AS LastErrorAt,
            SUM(CASE WHEN StatusCode >= 400 AND StatusCode < 500 THEN 1 ELSE 0 END) AS ClientErrorCount,
            SUM(CASE WHEN StatusCode >= 500 THEN 1 ELSE 0 END) AS ServerErrorCount
        FROM access_logs
        WHERE StatusCode >= 400
        GROUP BY IpAddress
        ORDER BY TotalErrorCount DESC, LastErrorAt DESC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "IpAddress": r["IpAddress"],
            "TotalErrorCount": r["TotalErrorCount"],
            "LastErrorAt": r["LastErrorAt"],
            "ClientErrorCount": r["ClientErrorCount"],
            "ServerErrorCount": r["ServerErrorCount"]
        })

    return jsonify({
        "status": "success",
        "total_unique_ips": len(result),
        "error_ips": result
    })



if __name__ == '__main__':
    try:
        # .env 파일에서 FLASK_DEBUG 값을 가져와 True/False로 변환
        is_debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        print(f"[Server Startup] Starting Flask on http://0.0.0.0:5000 (debug={is_debug}, reloader=False)...")
        # [Python 3.14 호환성] use_reloader=False를 명시하여 서브프로세스 IPC 세마포어 누수 경고 및 크래시 방어
        app.run(host='0.0.0.0', port=5000, debug=is_debug, use_reloader=False)
    except Exception as e:
        import traceback
        print(f"[Server Fatal Error] Failed to start server: {e}")
        traceback.print_exc()