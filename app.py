# ==========================================
# 1. 필요한 외부 라이브러리 불러오기
# ==========================================
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
import sqlite3
import os
import json
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

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
# 2. DB 공통 모듈 (모든 DB 관련 함수가 이 모듈에 의존함)
# ==========================================

def get_db_connection():
    """
    [역할] DB 연결 객체를 생성하고 결과를 Dict(사전) 형태로 반환하도록 설정하는 공통 함수
    """
    conn = sqlite3.connect('equipment.db')
    conn.row_factory = sqlite3.Row 
    return conn


def log_audit(actor_id, actor_login_id, action, target_table, target_id=None, old_value=None, new_value=None):
    """
    [역할] 모든 C/U/D 및 로그인/권한 변경 시 Audit Log 기록
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

    # 1. 장비 테이블 (equipment)
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
    
    # 2. 사용자 테이블 (users)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            UserId INTEGER PRIMARY KEY AUTOINCREMENT,
            LoginId TEXT UNIQUE NOT NULL,
            Name TEXT,
            NickName TEXT,
            Password TEXT NOT NULL,
            Role TEXT NOT NULL,
            CreatedAt TEXT,
            UpdatedAt TEXT
        )
    ''')

    # 3. 메뉴 테이블 (menus)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menus (
            MenuId INTEGER PRIMARY KEY AUTOINCREMENT,
            MenuCode TEXT UNIQUE NOT NULL,
            MenuName TEXT NOT NULL,
            Url TEXT NOT NULL,
            Description TEXT,
            CreatedAt TEXT,
            UpdatedAt TEXT
        )
    ''')

    # 4. 메뉴 권한 테이블 (role_menu_permissions)
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

    # 5. 감사 로그 테이블 (audit_logs)
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            UserId INTEGER PRIMARY KEY,
            PreferencesJSON TEXT,
            UpdatedAt TEXT,
            FOREIGN KEY(UserId) REFERENCES users(UserId) ON DELETE CASCADE
        )
    ''')

    # 7. 카테고리 마스터 테이블 (categories) - [제안-011]
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            CategoryId INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT UNIQUE NOT NULL,
            IsApproved INTEGER DEFAULT 1,
            CreatedAt TEXT
        )
    ''')

    # 8. 제조사 마스터 테이블 (manufacturers) - [제안-011]
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manufacturers (
            ManufacturerId INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT UNIQUE NOT NULL,
            IsApproved INTEGER DEFAULT 1,
            CreatedAt TEXT
        )
    ''')

    # 9. 전자결재 요청 테이블 (approval_requests) - [제안-027]
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

    # 기본 메뉴 등록 (기존 장비관리 메뉴 대신 분리된 메뉴 2종)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("DELETE FROM menus WHERE MenuCode = 'equipment'")
    cursor.execute("DELETE FROM role_menu_permissions WHERE MenuCode = 'equipment'")
    
    cursor.execute("INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, CreatedAt, UpdatedAt) VALUES (?, ?, ?, ?, ?, ?)",
                   ('my_equipment', '나의 장비', '/my_equipment', '내 장비 등록 및 관리', now, now))
    cursor.execute("INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, CreatedAt, UpdatedAt) VALUES (?, ?, ?, ?, ?, ?)",
                   ('public_equipment', '공개된 장비', '/public_equipment', '공개된 장비 및 전체 장비 조회', now, now))
    cursor.execute("INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, CreatedAt, UpdatedAt) VALUES (?, ?, ?, ?, ?, ?)",
                   ('permissions', '메뉴 권한 관리', '/permissions', '사용자 역할별 메뉴 접근 권한 제어', now, now))
    cursor.execute("INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, CreatedAt, UpdatedAt) VALUES (?, ?, ?, ?, ?, ?)",
                   ('audit_logs', '보안 감사 로그', '/audit_logs', '시스템 접근 이력 및 감사 로그 조회', now, now))
    cursor.execute("INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, CreatedAt, UpdatedAt) VALUES (?, ?, ?, ?, ?, ?)",
                   ('users_management', '사용자 관리', '/users_management', '전체 사용자 권한 및 계정 관리', now, now))
    cursor.execute("INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, CreatedAt, UpdatedAt) VALUES (?, ?, ?, ?, ?, ?)",
                   ('dashboard', '통계 대시보드', '/dashboard', '장비 통계 및 상세 현황 조회', now, now))
    cursor.execute("INSERT OR IGNORE INTO menus (MenuCode, MenuName, Url, Description, CreatedAt, UpdatedAt) VALUES (?, ?, ?, ?, ?, ?)",
                   ('approvals', '전자결재함', '/approvals', '전자결재 요청 및 승인 관리', now, now))

    # 기본 권한 등록 (admin: 전체 허용, user: 나의 장비 및 공개된 장비, 전자결재 허용)
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'my_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'public_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'permissions', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'audit_logs', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'users_management', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'dashboard', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'approvals', 1, now))
    
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'my_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'public_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'permissions', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'audit_logs', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'users_management', 0, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'dashboard', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'approvals', 1, now))

    conn.commit()
    conn.close()

# 서버 실행 시 DB 준비 (기존 데이터 보존 원칙 적용)
init_db()

def migrate_equipment_is_public():
    """
    [역할] 기존 DB의 equipment 테이블에 IsPublic 컬럼이 없으면 추가 (무정지 마이그레이션)
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

migrate_equipment_is_public()

def migrate_proposals_011_027_028():
    """
    [역할] 제안-011, 027, 028 데이터베이스 마이그레이션 수행
    1. equipment 테이블에 IsDraft 컬럼 추가
    2. 기존 equipment 테이블의 Category, Manufacturer 고유값을 categories, manufacturers 마스터 테이블에 백업 (IsApproved=1)
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

migrate_proposals_011_027_028()

def migrate_passwords_to_hash():
    """
    [역할] 기존 평문 비밀번호를 해시 암호로 자동 변환 (데이터 보존 원칙 준수)
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
migrate_passwords_to_hash()

@app.after_request
def after_request_func(response):
    # 폴링 요청 시에는 플라스크가 세션을 자동으로 갱신(Refresh)하지 못하게 세션 쿠키 발급을 차단
    if request.path == '/api/check_session':
        new_headers = []
        for k, v in response.headers.items():
            if k.lower() == 'set-cookie' and v.startswith('session='):
                continue
            new_headers.append((k, v))
        response.headers = type(response.headers)(new_headers)
    return response

@app.route('/api/check_session', methods=['GET'])
def check_session():
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
    [역할] 기존 users 테이블에 동시 로그인 방어를 위한 SessionToken 컬럼 추가
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

migrate_users_session_token()


# ==========================================
# 3. 인증 및 권한 데코레이터
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        session_token = session.get('session_token')
        
        if not user or 'UserId' not in user or not session_token:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({"error": "로그인이 필요합니다."}), 401
            return redirect(url_for('login_page'))
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SessionToken FROM users WHERE UserId = ?", (user['UserId'],))
        db_user = cursor.fetchone()
        conn.close()
        
        if not db_user or db_user['SessionToken'] != session_token:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({"error": "다른 기기에서 로그인하여 세션이 만료되었습니다."}), 401
            return redirect(url_for('login_page', error='concurrent_login'))
            
        return f(*args, **kwargs)
    return decorated_function


def check_menu_permission(menu_code):
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
    return send_from_directory(os.path.join(app.root_path, 'Resources'),
                               'EqMgmt.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def index():
    user = session.get('user')
    if user and 'UserId' in user:
        return redirect(url_for('portal_page'))
    session.pop('user', None)
    return redirect(url_for('login_page'))


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET':
        user = session.get('user')
        if user and 'UserId' in user:
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
    
    if user and check_password_hash(user['Password'], password):
        user_dict = {
            'UserId': user['UserId'],
            'LoginId': user['LoginId'],
            'NickName': user['NickName'],
            'Role': user['Role']
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
        
        log_audit(user['UserId'], user['LoginId'], 'LOGIN_SUCCESS', 'users', user['UserId'], None, {"LoginId": login_id})
        return jsonify({"success": True, "message": "로그인 성공"})
    else:
        log_audit(None, login_id, 'LOGIN_FAILED', 'users', None, None, {"LoginId": login_id, "reason": "invalid_credentials"})
        return jsonify({"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 400


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'GET':
        return render_template('register.html')
        
    data = request.json
    login_id = data.get('LoginId')
    name = data.get('Name')
    nickname = data.get('NickName')
    password = data.get('Password')
    hashed_password = generate_password_hash(password)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 중복 체크
    cursor.execute("SELECT * FROM users WHERE LoginId = ?", (login_id,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "이미 존재하는 아이디입니다."}), 400
        
    # 권한 설정 (최초 가입자는 admin)
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    role = 'admin' if count == 0 else 'user'
    
    cursor.execute('''
        INSERT INTO users (LoginId, Name, NickName, Password, Role, CreatedAt, UpdatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (login_id, name, nickname, hashed_password, role, now, now))
    
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    log_audit(new_id, login_id, 'REGISTER', 'users', new_id, None, {"LoginId": login_id, "Role": role})
    return jsonify({"success": True, "message": "회원가입이 완료되었습니다!"})


@app.route('/logout')
def logout():
    user = session.get('user')
    if user:
        if 'UserId' in user:
            log_audit(user['UserId'], user['LoginId'], 'LOGOUT', 'users', user['UserId'], None, None)
        session.clear()
    return redirect(url_for('login_page'))


@app.route('/portal')
@login_required
def portal_page():
    return render_template('portal.html', user=session['user'])


@app.route('/equipment')
def equipment_redirect():
    # 하위 호환성 (기존 URL로 올 경우 나의 장비로 리다이렉트)
    return redirect(url_for('my_equipment_page'))


@app.route('/my_equipment')
@login_required
def my_equipment_page():
    if not check_menu_permission('my_equipment'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('index.html', user=session['user'], mode='my')


@app.route('/public_equipment')
@login_required
def public_equipment_page():
    if not check_menu_permission('public_equipment'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('index.html', user=session['user'], mode='public')


@app.route('/permissions')
@login_required
def permissions_page():
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

@app.route('/users_management')
@login_required
def users_management_page():
    if not check_menu_permission('users_management'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('users_management.html', user=session['user'])

@app.route('/dashboard')
@login_required
def dashboard_page():
    if not check_menu_permission('dashboard'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('dashboard.html', user=session['user'])

@app.route('/mypage')
@login_required
def mypage_page():
    # 마이페이지는 모든 로그인 사용자가 접근 가능하므로 메뉴 권한 체크 생략(또는 기본 허용)
    return render_template('mypage.html', user=session['user'])

@app.route('/approvals')
@login_required
def approvals_page():
    if not check_menu_permission('approvals'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('approvals.html', user=session['user'])

# ==========================================
# 5. RESTful API 모듈 (인증/권한 및 데이터 처리)
# ==========================================

@app.route('/api/extend_session', methods=['POST'])
@login_required
def extend_session():
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
def api_user_settings():
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
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 내 장비 수
    cursor.execute("SELECT COUNT(*) as count FROM equipment WHERE UserId = ?", (user['UserId'],))
    my_eq_count = cursor.fetchone()['count']
    
    # 2. 총 장비 수 (관리자 권한 고려)
    if user['Role'] == 'admin':
        cursor.execute("SELECT COUNT(*) as count FROM equipment")
        total_count = cursor.fetchone()['count']
    else:
        # 일반 사용자는 공개된 장비 + 내 장비만 카운트
        cursor.execute("SELECT COUNT(*) as count FROM equipment WHERE IsPublic = 1 OR UserId = ?", (user['UserId'],))
        total_count = cursor.fetchone()['count']
        
    # 3. 카테고리별 통계
    if user['Role'] == 'admin':
        cursor.execute("SELECT Category, COUNT(*) as count FROM equipment GROUP BY Category")
    else:
        cursor.execute("SELECT Category, COUNT(*) as count FROM equipment WHERE IsPublic = 1 OR UserId = ? GROUP BY Category", (user['UserId'],))
    
    categories = [{"category": row['Category'], "count": row['count']} for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        "success": True,
        "data": {
            "my_equipments": my_eq_count,
            "total_equipments": total_count,
            "categories": categories
        }
    })

# ------------------------------------------
# 사용자 프로필 (비밀번호 변경) API
# ------------------------------------------
@app.route('/api/users/change_password', methods=['POST'])
@login_required
def api_change_my_password():
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

# ------------------------------------------
# 관리자용 사용자 관리 API
# ------------------------------------------
@app.route('/api/users', methods=['GET'])
@login_required
def api_get_users():
    user = session['user']
    if user['Role'] != 'admin':
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserId, LoginId, Name, NickName, Role, CreatedAt FROM users ORDER BY UserId DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify({"success": True, "data": [dict(row) for row in rows]})

@app.route('/api/users/<int:target_user_id>/role', methods=['PUT'])
@login_required
def api_update_user_role(target_user_id):
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
def api_reset_user_password(target_user_id):
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
def api_force_logout_all():
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
def api_force_logout_selected():
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
def api_delete_selected_users():
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
    cursor.execute(f"UPDATE equipment SET UserId = NULL, IsPublic = 1 WHERE UserId IN ({del_placeholders})", del_tuple)
    
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
        cursor.execute("SELECT * FROM menus ORDER BY MenuId ASC")
    else:
        cursor.execute('''
            SELECT m.* FROM menus m
            JOIN role_menu_permissions p ON m.MenuCode = p.MenuCode
            WHERE p.Role = ? AND p.IsAllowed = 1
            ORDER BY m.MenuId ASC
        ''', (role,))
        
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])


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
    [역할] 장비 등록 시 드롭다운에 표시될 승인된 카테고리 및 제조사 목록 조회
    [의존성 관계] categories, manufacturers 테이블
    [변경 시 영향도] 프론트엔드 장비 등록/수정 모달의 선택 항목 렌더링에 직접적인 영향을 줍니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Name FROM categories WHERE IsApproved = 1 ORDER BY Name ASC")
    categories = [r['Name'] for r in cursor.fetchall()]
    cursor.execute("SELECT Name FROM manufacturers WHERE IsApproved = 1 ORDER BY Name ASC")
    manufacturers = [r['Name'] for r in cursor.fetchall()]
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
            
        log_audit(user['UserId'], user['LoginId'], 'REJECT_REQUEST', 'approval_requests', req_id, req_dict, {"Status": "REJECTED", "Reason": reject_reason, "Replacement": replacement_name})
        
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "결재 처리가 완료되었습니다."})


# 장비 조회 (나의 장비, 공개된 장비, 임시저장함 분기 처리) - [제안-028]
@app.route('/api/equipment', methods=['GET'])
@login_required
def get_equipment():
    """
    [역할] 장비 목록을 조회하여 프론트엔드로 반환. (본인 장비, 공개 장비, 관리자 전체 조회, 임시저장함 분기 처리)
    [의존성 관계] equipment 테이블, users 테이블 (NickName JOIN용)
    [변경 시 영향도] 화면의 장비 목록(Table) 출력 조건 및 순서가 변경됩니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    req_type = request.args.get('type', 'my')
    include_mine = request.args.get('include_mine', 'false').lower() == 'true'
    is_draft = request.args.get('is_draft', '0') == '1'
    
    if is_draft:
        # [임시저장함] 모드: 본인의 IsDraft = 1 장비만 조회
        cursor.execute('''
            SELECT e.*, u.NickName as OwnerNickName 
            FROM equipment e
            LEFT JOIN users u ON e.UserId = u.UserId
            WHERE e.UserId = ? AND e.IsDraft = 1
            ORDER BY e.EquipmentId DESC
        ''', (user['UserId'],))
        
    elif req_type == 'my':
        # [나의 장비] 모드: 본인의 정식 등록 장비(IsDraft = 0)만 조회
        cursor.execute('''
            SELECT e.*, u.NickName as OwnerNickName 
            FROM equipment e
            LEFT JOIN users u ON e.UserId = u.UserId
            WHERE e.UserId = ? AND (e.IsDraft = 0 OR e.IsDraft IS NULL)
            ORDER BY e.EquipmentId DESC
        ''', (user['UserId'],))
        
    elif req_type == 'public':
        # [공개된 장비] 모드: IsDraft = 0 정식 데이터만 노출
        if user['Role'] == 'admin':
            cursor.execute('''
                SELECT e.*, u.NickName as OwnerNickName 
                FROM equipment e
                LEFT JOIN users u ON e.UserId = u.UserId
                WHERE (e.IsDraft = 0 OR e.IsDraft IS NULL)
                ORDER BY e.EquipmentId DESC
            ''')
        else:
            if include_mine:
                cursor.execute('''
                    SELECT e.*, u.NickName as OwnerNickName 
                    FROM equipment e
                    LEFT JOIN users u ON e.UserId = u.UserId
                    WHERE (e.IsPublic = 1 OR e.UserId = ?) AND (e.IsDraft = 0 OR e.IsDraft IS NULL)
                    ORDER BY CASE WHEN e.UserId = ? THEN 0 ELSE 1 END, e.EquipmentId DESC
                ''', (user['UserId'], user['UserId']))
            else:
                cursor.execute('''
                    SELECT e.*, u.NickName as OwnerNickName 
                    FROM equipment e
                    LEFT JOIN users u ON e.UserId = u.UserId
                    WHERE e.IsPublic = 1 AND e.UserId != ? AND (e.IsDraft = 0 OR e.IsDraft IS NULL)
                    ORDER BY e.EquipmentId DESC
                ''', (user['UserId'],))
    else:
        cursor.execute("SELECT * FROM equipment WHERE 1=0")

    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])


# 장비 등록
@app.route('/api/equipment', methods=['POST'])
@login_required
def add_equipment():
    """
    [역할] 새로운 장비 데이터를 DB에 인서트(INSERT) 합니다. (임시저장 및 카테고리/제조사 전자결재 자동상신 연동)
    [의존성 관계] equipment, categories, manufacturers, approval_requests 테이블
    [변경 시 영향도] 장비 등록 필드(컬럼) 추가 시 이 함수와 프론트엔드의 payload, init_db 스키마를 모두 수정해야 합니다.
    """
    data = request.json
    user = session['user']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    target_user_id = user['UserId']
    if user['Role'] == 'admin' and data.get('UserId'):
        target_user_id = data.get('UserId')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    is_draft = 1 if (data.get('IsDraft') or data.get('is_draft')) else 0
    is_public = 0 if is_draft == 1 else (1 if data.get('IsPublic') else 0)
    
    cat_name = data.get('Category', '').strip() if data.get('Category') else ''
    mfg_name = data.get('Manufacturer', '').strip() if data.get('Manufacturer') else ''
    
    # 카테고리 마스터 확인 및 자동 전자결재 생성
    if cat_name:
        cursor.execute("SELECT * FROM categories WHERE Name = ?", (cat_name,))
        cat_row = cursor.fetchone()
        if not cat_row:
            cursor.execute("INSERT INTO categories (Name, IsApproved, CreatedAt) VALUES (?, 0, ?)", (cat_name, now))
            req_json = json.dumps({"type": "category", "name": cat_name}, ensure_ascii=False)
            cursor.execute("INSERT INTO approval_requests (RequesterId, RequestType, RequestDataJSON, Status, CreatedAt, UpdatedAt) VALUES (?, 'ADD_CATEGORY', ?, 'PENDING', ?, ?)", (user['UserId'], req_json, now, now))
            
    # 제조사 마스터 확인 및 자동 전자결재 생성
    if mfg_name:
        cursor.execute("SELECT * FROM manufacturers WHERE Name = ?", (mfg_name,))
        mfg_row = cursor.fetchone()
        if not mfg_row:
            cursor.execute("INSERT INTO manufacturers (Name, IsApproved, CreatedAt) VALUES (?, 0, ?)", (mfg_name, now))
            req_json = json.dumps({"type": "manufacturer", "name": mfg_name}, ensure_ascii=False)
            cursor.execute("INSERT INTO approval_requests (RequesterId, RequestType, RequestDataJSON, Status, CreatedAt, UpdatedAt) VALUES (?, 'ADD_MANUFACTURER', ?, 'PENDING', ?, ?)", (user['UserId'], req_json, now, now))

    cursor.execute('''
        INSERT INTO equipment (Name, Category, Manufacturer, ModelName, PurchaseDate, SerialNumber, Memo, UserId, IsPublic, IsDraft, CreatedAt, UpdatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('Name'), 
        cat_name, 
        mfg_name, 
        data.get('ModelName'), 
        data.get('PurchaseDate'), 
        data.get('SerialNumber'), 
        data.get('Memo'),
        target_user_id,
        is_public,
        is_draft,
        now,
        now
    ))
    
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'INSERT', 'equipment', new_id, None, data)
    return jsonify({"message": "임시저장되었습니다." if is_draft == 1 else "성공적으로 등록되었습니다!"})


# 장비 수정
@app.route('/api/equipment/<int:eq_id>', methods=['PUT'])
@login_required
def update_equipment(eq_id):
    """
    [역할] 기존 장비의 데이터를 수정(UPDATE) 합니다. (임시저장 ➡️ 정식등록 전환 지원)
    [의존성 관계] equipment, categories, manufacturers, approval_requests 테이블
    [변경 시 영향도] 장비 수정 컬럼이 추가/삭제될 경우 DB 업데이트 쿼리와 프론트엔드의 수정 모달 로직이 함께 변경되어야 합니다.
    """
    data = request.json
    user = session['user']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM equipment WHERE EquipmentId = ?", (eq_id,))
    old_row = cursor.fetchone()
    if not old_row:
        conn.close()
        return jsonify({"error": "해당 장비를 찾을 수 없습니다."}), 404

    old_dict = dict(old_row)
    if user['Role'] != 'admin' and old_dict['UserId'] != user['UserId']:
        conn.close()
        return jsonify({"error": "수정 권한이 없습니다."}), 403

    target_user_id = old_dict['UserId']
    if user['Role'] == 'admin' and data.get('UserId'):
        target_user_id = data.get('UserId')

    # 만약 기존 데이터가 정식 장비(IsDraft=0)였다면, 임시저장으로 되돌리는 것 방지 (상세 1)
    if old_dict.get('IsDraft') == 0:
        is_draft = 0
        is_public = 1 if data.get('IsPublic') else 0
    else:
        is_draft = 1 if (data.get('IsDraft') or data.get('is_draft')) else 0
        is_public = 0 if is_draft == 1 else (1 if data.get('IsPublic') else 0)

    cat_name = data.get('Category', '').strip() if data.get('Category') else ''
    mfg_name = data.get('Manufacturer', '').strip() if data.get('Manufacturer') else ''

    # 카테고리 마스터 확인 및 자동 전자결재 생성
    if cat_name:
        cursor.execute("SELECT * FROM categories WHERE Name = ?", (cat_name,))
        cat_row = cursor.fetchone()
        if not cat_row:
            cursor.execute("INSERT INTO categories (Name, IsApproved, CreatedAt) VALUES (?, 0, ?)", (cat_name, now))
            req_json = json.dumps({"type": "category", "name": cat_name}, ensure_ascii=False)
            cursor.execute("INSERT INTO approval_requests (RequesterId, RequestType, RequestDataJSON, Status, CreatedAt, UpdatedAt) VALUES (?, 'ADD_CATEGORY', ?, 'PENDING', ?, ?)", (user['UserId'], req_json, now, now))
            
    # 제조사 마스터 확인 및 자동 전자결재 생성
    if mfg_name:
        cursor.execute("SELECT * FROM manufacturers WHERE Name = ?", (mfg_name,))
        mfg_row = cursor.fetchone()
        if not mfg_row:
            cursor.execute("INSERT INTO manufacturers (Name, IsApproved, CreatedAt) VALUES (?, 0, ?)", (mfg_name, now))
            req_json = json.dumps({"type": "manufacturer", "name": mfg_name}, ensure_ascii=False)
            cursor.execute("INSERT INTO approval_requests (RequesterId, RequestType, RequestDataJSON, Status, CreatedAt, UpdatedAt) VALUES (?, 'ADD_MANUFACTURER', ?, 'PENDING', ?, ?)", (user['UserId'], req_json, now, now))

    cursor.execute('''
        UPDATE equipment 
        SET Name=?, Category=?, Manufacturer=?, ModelName=?, PurchaseDate=?, SerialNumber=?, Memo=?, UserId=?, IsPublic=?, IsDraft=?, UpdatedAt=?
        WHERE EquipmentId=?
    ''', (
        data.get('Name'), 
        cat_name, 
        mfg_name, 
        data.get('ModelName'), 
        data.get('PurchaseDate'), 
        data.get('SerialNumber'), 
        data.get('Memo'),
        target_user_id,
        is_public,
        is_draft,
        now,
        eq_id
    ))
    
    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'UPDATE', 'equipment', eq_id, old_dict, data)
    return jsonify({"message": "수정되었습니다."})


# 장비 삭제
@app.route('/api/equipment/<int:eq_id>', methods=['DELETE'])
@login_required
def delete_equipment(eq_id):
    """
    [역할] 특정 장비를 DB에서 완전히 삭제(DELETE) 합니다.
    [의존성 관계] equipment 테이블, log_audit()
    [변경 시 영향도] 타인 장비 삭제 권한 탈취 방어선이므로 삭제 로직 변경에 주의해야 합니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM equipment WHERE EquipmentId = ?", (eq_id,))
    old_row = cursor.fetchone()
    if not old_row:
        conn.close()
        return jsonify({"error": "해당 장비를 찾을 수 없습니다."}), 404

    old_dict = dict(old_row)
    if user['Role'] != 'admin' and old_dict['UserId'] != user['UserId']:
        conn.close()
        return jsonify({"error": "삭제 권한이 없습니다."}), 403

    cursor.execute("DELETE FROM equipment WHERE EquipmentId = ?", (eq_id,))
    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'DELETE', 'equipment', eq_id, old_dict, None)
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
        SELECT p.*, m.MenuName 
        FROM role_menu_permissions p
        JOIN menus m ON p.MenuCode = m.MenuCode
        ORDER BY p.Role ASC, m.MenuId ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(r) for r in rows])


# 권한 설정 수정
@app.route('/api/permissions', methods=['POST'])
@login_required
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
    
    for item in data:
        cursor.execute('''
            INSERT INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(Role, MenuCode) DO UPDATE SET IsAllowed=excluded.IsAllowed, UpdatedAt=excluded.UpdatedAt
        ''', (item['Role'], item['MenuCode'], item['IsAllowed'], now))
        
    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'UPDATE_PERMISSIONS', 'role_menu_permissions', None, old_perms, data)
    return jsonify({"message": "권한 설정이 업데이트되었습니다."})


if __name__ == '__main__':
    # .env 파일에서 FLASK_DEBUG 값을 가져와 True/False로 변환
    is_debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=is_debug)