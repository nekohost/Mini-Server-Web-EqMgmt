# ==========================================
# 1. 필요한 외부 라이브러리 불러오기
# ==========================================
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
import sqlite3
import os
import json
from datetime import datetime
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

    # 기본 권한 등록 (admin: 전체 허용, user: 나의 장비 및 공개된 장비 허용)
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'my_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'public_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('admin', 'permissions', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'my_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'public_equipment', 1, now))
    cursor.execute("INSERT OR IGNORE INTO role_menu_permissions (Role, MenuCode, IsAllowed, UpdatedAt) VALUES (?, ?, ?, ?)", ('user', 'permissions', 0, now))

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


# ==========================================
# 3. 인증 및 권한 데코레이터
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user or 'UserId' not in user:
            session.pop('user', None)
            if request.path.startswith('/api/'):
                return jsonify({"error": "로그인이 필요합니다."}), 401
            return redirect(url_for('login_page'))
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
        session['user'] = user_dict
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
        session.pop('user', None)
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


# ==========================================
# 5. RESTful API 모듈 (인증/권한 및 데이터 처리)
# ==========================================

@app.route('/api/me', methods=['GET'])
@login_required
def get_current_user():
    """
    [역할] 현재 세션에 로그인되어 있는 사용자 정보 반환
    [의존성 관계] @login_required, session 객체
    [변경 시 영향도] 프론트엔드의 사용자 프로필 표시 및 권한 체계 처리에 영향을 줍니다.
    """
    return jsonify(session['user'])


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


# 장비 조회 (나의 장비 & 공개된 장비 분기 처리)
@app.route('/api/equipment', methods=['GET'])
@login_required
def get_equipment():
    """
    [역할] 장비 목록을 조회하여 프론트엔드로 반환. (본인 장비, 공개 장비, 관리자 전체 조회 분기 처리)
    [의존성 관계] equipment 테이블, users 테이블 (NickName JOIN용)
    [변경 시 영향도] 화면의 장비 목록(Table) 출력 조건 및 순서가 변경됩니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    req_type = request.args.get('type', 'my')
    include_mine = request.args.get('include_mine', 'false').lower() == 'true'
    
    if req_type == 'my':
        # [나의 장비] 모드: 관리자/일반인 불문 무조건 자기 자신 것만 조회
        cursor.execute('''
            SELECT e.*, u.NickName as OwnerNickName 
            FROM equipment e
            LEFT JOIN users u ON e.UserId = u.UserId
            WHERE e.UserId = ?
            ORDER BY e.EquipmentId DESC
        ''', (user['UserId'],))
        
    elif req_type == 'public':
        # [공개된 장비] 모드
        if user['Role'] == 'admin':
            # 관리자: 묻지도 따지지도 않고 전체 열람 (관리 권한)
            cursor.execute('''
                SELECT e.*, u.NickName as OwnerNickName 
                FROM equipment e
                LEFT JOIN users u ON e.UserId = u.UserId
                ORDER BY e.EquipmentId DESC
            ''')
        else:
            # 일반 사용자: IsPublic = 1 인 타인의 장비 노출. include_mine 여부에 따라 내 장비 합침
            if include_mine:
                cursor.execute('''
                    SELECT e.*, u.NickName as OwnerNickName 
                    FROM equipment e
                    LEFT JOIN users u ON e.UserId = u.UserId
                    WHERE e.IsPublic = 1 OR e.UserId = ?
                    ORDER BY CASE WHEN e.UserId = ? THEN 0 ELSE 1 END, e.EquipmentId DESC
                ''', (user['UserId'], user['UserId']))
            else:
                cursor.execute('''
                    SELECT e.*, u.NickName as OwnerNickName 
                    FROM equipment e
                    LEFT JOIN users u ON e.UserId = u.UserId
                    WHERE e.IsPublic = 1 AND e.UserId != ?
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
    [역할] 새로운 장비 데이터를 DB에 인서트(INSERT) 합니다.
    [의존성 관계] equipment 테이블, log_audit()
    [변경 시 영향도] 관리자의 경우 대상 사용자(UserId)를 덮어쓰는 로직이 있으므로 이 구조 변경 시 권한 에러가 발생할 수 있습니다.
    """
    data = request.json
    user = session['user']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 일반 사용자는 본인 아이디를 사용하고, 관리자는 지정한 소유자(data['UserId'])를 사용 (없으면 기본은 본인)
    target_user_id = user['UserId']
    if user['Role'] == 'admin' and data.get('UserId'):
        target_user_id = data.get('UserId')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    is_public = 1 if data.get('IsPublic') else 0
    
    cursor.execute('''
        INSERT INTO equipment (Name, Category, Manufacturer, ModelName, PurchaseDate, SerialNumber, Memo, UserId, IsPublic, CreatedAt, UpdatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('Name'), 
        data.get('Category'), 
        data.get('Manufacturer'), 
        data.get('ModelName'), 
        data.get('PurchaseDate'), 
        data.get('SerialNumber'), 
        data.get('Memo'),
        target_user_id,
        is_public,
        now,
        now
    ))
    
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    log_audit(user['UserId'], user['LoginId'], 'INSERT', 'equipment', new_id, None, data)
    return jsonify({"message": "성공적으로 등록되었습니다!"})


# 장비 수정
@app.route('/api/equipment/<int:eq_id>', methods=['PUT'])
@login_required
def update_equipment(eq_id):
    """
    [역할] 기존 장비의 데이터를 수정(UPDATE) 합니다. 소유자 권한을 강력하게 검증합니다.
    [의존성 관계] equipment 테이블, log_audit()
    [변경 시 영향도] 타인 장비 수정 권한 탈취 방어선이므로, 수정 시 보안 취약점이 생길 수 있습니다.
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

    is_public = 1 if data.get('IsPublic') else 0

    cursor.execute('''
        UPDATE equipment 
        SET Name=?, Category=?, Manufacturer=?, ModelName=?, PurchaseDate=?, SerialNumber=?, Memo=?, UserId=?, IsPublic=?, UpdatedAt=?
        WHERE EquipmentId=?
    ''', (
        data.get('Name'), 
        data.get('Category'), 
        data.get('Manufacturer'), 
        data.get('ModelName'), 
        data.get('PurchaseDate'), 
        data.get('SerialNumber'), 
        data.get('Memo'),
        target_user_id,
        is_public,
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