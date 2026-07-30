# ==========================================
# 1. 필요한 외부 라이브러리 불러오기
# ==========================================
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import json
from datetime import datetime
from functools import wraps

app = Flask(__name__)
# 세션 암호화를 위한 비밀키 설정
app.secret_key = 'mini_server_equipment_mgmt_secret_key_2026'

# ==========================================
# 2. DB 공통 모듈 (모든 DB 관련 함수가 이 모듈에 의존함)
# ==========================================

def get_db_connection():
    """
    [역할] DB 연결 객체를 생성하고 결과를 Dict(사전) 형태로 반환하도록 설정하는 공통 함수
    
    [의존성 관계]
    - 의존하는 대상: 'equipment.db' 파일
    - 이 함수에 의존하는 대상: init_db(), get_equipment(), add_equipment(), update_equipment(), delete_equipment(), log_audit() 등 전 함수
    
    [변경 시 영향도]
    - 만약 DB 파일명이 바뀌거나, PostgreSQL/MSSQL 등 다른 DB로 교체될 경우
      오직 이 함수 내부의 sqlite3.connect() 부분만 수정하면 됩니다.
    """
    conn = sqlite3.connect('equipment.db')
    conn.row_factory = sqlite3.Row 
    return conn


def log_audit(actor_id, actor_username, action, target_table, target_id=None, old_value=None, new_value=None):
    """
    [역할] 모든 C/U/D 및 로그인/권한 변경 시 접속자의 IP, User-Agent, 변경 전/후 데이터를 기록하는 Audit Log 함수
    
    [의존성 관계]
    - 의존하는 대상: get_db_connection(), audit_logs 테이블
    - 이 함수에 의존하는 대상: login(), add_equipment(), update_equipment(), delete_equipment(), update_permissions()
    
    [변경 시 영향도]
    - Audit Log 항목이 추가되거나 이력 저장 방식이 바뀔 때 이 함수를 수정합니다.
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
            INSERT INTO audit_logs (actor_id, actor_username, ip_address, user_agent, target_table, target_id, action, old_value, new_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (actor_id, actor_username, ip_address, user_agent, target_table, target_id, action, old_json, new_json, created_at))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Audit Log Error] {e}")


def init_db():
    """
    [역할] 테이블 구조를 초기화 및 관리하고 기본 데이터(초기 사용자, 메뉴, 권한)를 생성하는 함수
    
    [의존성 관계]
    - 의존하는 대상: get_db_connection()
    - 이 함수에 의존하는 대상: 서버 스타트업 로직
    
    [변경 시 영향도] (★ DB 칼럼 및 테이블 확장 시 수정 지침)
    - 새로운 테이블이나 컬럼이 필요한 경우 이 함수 내 CREATE TABLE 구문 및 초기 INSERT 구문을 수정합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 장비 테이블 (user_id, created_at, updated_at 추가)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            manufacturer TEXT,
            model_name TEXT,
            purchase_date TEXT,
            serial_number TEXT,
            memo TEXT,
            user_id INTEGER,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    # 기존 DB 호환성을 위해 user_id, created_at, updated_at 컬럼 미존재 시 PRAGMA로 동적 추가
    cursor.execute("PRAGMA table_info(equipment)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'user_id' not in columns:
        cursor.execute("ALTER TABLE equipment ADD COLUMN user_id INTEGER DEFAULT 1")
    if 'created_at' not in columns:
        cursor.execute("ALTER TABLE equipment ADD COLUMN created_at TEXT")
    if 'updated_at' not in columns:
        cursor.execute("ALTER TABLE equipment ADD COLUMN updated_at TEXT")

    # 2. 사용자 테이블 (users)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    # 3. 메뉴 테이블 (menus)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_code TEXT UNIQUE NOT NULL,
            menu_name TEXT NOT NULL,
            url TEXT NOT NULL,
            description TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    # 4. 메뉴 권한 테이블 (role_menu_permissions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS role_menu_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            menu_code TEXT NOT NULL,
            is_allowed INTEGER DEFAULT 1,
            updated_at TEXT,
            UNIQUE(role, menu_code)
        )
    ''')

    # 5. 감사 로그 테이블 (audit_logs)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER,
            actor_username TEXT,
            ip_address TEXT,
            user_agent TEXT,
            target_table TEXT,
            target_id INTEGER,
            action TEXT,
            old_value TEXT,
            new_value TEXT,
            created_at TEXT
        )
    ''')

    # 초기 기본 데이터 등록
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 기본 계정 생성 (admin / admin123, user1 / user123)
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                       ('admin', 'admin123', 'admin', now, now))
        cursor.execute("INSERT INTO users (username, password, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                       ('user1', 'user123', 'user', now, now))

    # 기본 메뉴 등록
    cursor.execute("SELECT COUNT(*) FROM menus")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO menus (menu_code, menu_name, url, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                       ('equipment', '장비 관리 시스템', '/equipment', '보유 장비 등록 및 통합 관리', now, now))
        cursor.execute("INSERT INTO menus (menu_code, menu_name, url, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                       ('permissions', '메뉴 권한 관리', '/permissions', '사용자 역할별 메뉴 접근 권한 제어', now, now))

    # 기본 권한 등록 (admin은 전 메뉴 허용, user는 장비관리만 허용)
    cursor.execute("SELECT COUNT(*) FROM role_menu_permissions")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO role_menu_permissions (role, menu_code, is_allowed, updated_at) VALUES (?, ?, ?, ?)",
                       ('admin', 'equipment', 1, now))
        cursor.execute("INSERT INTO role_menu_permissions (role, menu_code, is_allowed, updated_at) VALUES (?, ?, ?, ?)",
                       ('admin', 'permissions', 1, now))
        cursor.execute("INSERT INTO role_menu_permissions (role, menu_code, is_allowed, updated_at) VALUES (?, ?, ?, ?)",
                       ('user', 'equipment', 1, now))
        cursor.execute("INSERT INTO role_menu_permissions (role, menu_code, is_allowed, updated_at) VALUES (?, ?, ?, ?)",
                       ('user', 'permissions', 0, now))

    conn.commit()
    conn.close()

# 서버 실행 시 DB 준비
init_db()


# ==========================================
# 3. 인증 및 권한 데코레이터
# ==========================================

def login_required(f):
    """
    [역할] 로그인 상태 검증 데코레이터
    [의존성 관계] session['user'] 데이터에 의존함
    [변경 시 영향도] 미로그인 사용자가 보호된 페이지나 API에 접근할 때 로그인 페이지로 이동시키거나 401 에러 반환
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"error": "로그인이 필요합니다."}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


def check_menu_permission(menu_code):
    """
    [역할] 현재 로그인한 사용자 역할(role)의 해당 메뉴 접근 권한 검증 함수
    [의존성 관계] role_menu_permissions 테이블 및 session['user']
    [변경 시 영향도] 권한이 없는 경우 접근 거부 처리
    """
    user = session.get('user')
    if not user:
        return False
    if user['role'] == 'admin':
        return True
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_allowed FROM role_menu_permissions WHERE role = ? AND menu_code = ?", (user['role'], menu_code))
    row = cursor.fetchone()
    conn.close()
    
    return bool(row and row['is_allowed'] == 1)


# ==========================================
# 4. 화면 라우터 (뷰 페이지)
# ==========================================

@app.route('/')
def index():
    """
    [역할] 루트 경로 접속 시 세션에 따라 로그인 또는 포털 화면으로 리다이렉트
    [의존성 관계] session['user']
    [변경 시 영향도] 접속 시 첫 화면 분기 로직 변경 시 수정
    """
    if 'user' in session:
        return redirect(url_for('portal_page'))
    return redirect(url_for('login_page'))


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """
    [역할] 로그인 페이지 표시 및 로그인 처리 API
    [의존성 관계] templates/login.html, users 테이블, log_audit()
    [변경 시 영향도] 로그인 방식이나 폼 데이터 변경 시 수정
    """
    if request.method == 'GET':
        if 'user' in session:
            return redirect(url_for('portal_page'))
        return render_template('login.html')
    
    data = request.json or request.form
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and user['password'] == password:
        user_dict = {
            'id': user['id'],
            'username': user['username'],
            'role': user['role']
        }
        session['user'] = user_dict
        log_audit(user['id'], user['username'], 'LOGIN_SUCCESS', 'users', user['id'], None, {"username": username})
        return jsonify({"success": True, "message": "로그인 성공"})
    else:
        log_audit(None, username, 'LOGIN_FAILED', 'users', None, None, {"username": username, "reason": "invalid_credentials"})
        return jsonify({"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 400


@app.route('/logout')
def logout():
    """
    [역할] 로그아웃 처리 및 세션 파기
    [의존성 관계] session, log_audit()
    [변경 시 영향도] 로그아웃 시 리다이렉트 위치 또는 Audit Log 항목 수정
    """
    user = session.get('user')
    if user:
        log_audit(user['id'], user['username'], 'LOGOUT', 'users', user['id'], None, None)
        session.pop('user', None)
    return redirect(url_for('login_page'))


@app.route('/portal')
@login_required
def portal_page():
    """
    [역할] 메인 포털 화면 출력 (각 기능 메뉴 진입점)
    [의존성 관계] templates/portal.html, session['user']
    [변경 시 영향도] 포털 화면 템플릿 변경 시 수정
    """
    return render_template('portal.html', user=session['user'])


@app.route('/equipment')
@login_required
def equipment_page():
    """
    [역할] 장비 관리 화면 출력 (기존 index.html 템플릿 사용)
    [의존성 관계] templates/index.html, check_menu_permission()
    [변경 시 영향도] 권한 체크 실패 시 포털로 리다이렉트
    """
    if not check_menu_permission('equipment'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('index.html', user=session['user'])


@app.route('/permissions')
@login_required
def permissions_page():
    """
    [역할] 메뉴 권한 관리 화면 출력 (관리자 전용)
    [의존성 관계] templates/permissions.html, check_menu_permission()
    [변경 시 영향도] 권한 관리 템플릿 변경 시 수정
    """
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
    [역할] 현재 로그인한 사용자 정보 반환 API
    [의존성 관계] session['user']
    [변경 시 영향도] 프론트엔드 내 사용자 정보 조회 시 사용
    """
    return jsonify(session['user'])


@app.route('/api/portal/menus', methods=['GET'])
@login_required
def get_portal_menus():
    """
    [역할] 현재 로그인한 사용자가 접근 가능한 메뉴 목록 JSON 반환 API
    [의존성 관계] menus, role_menu_permissions 테이블 및 session['user']
    [변경 시 영향도] 포털 화면의 메뉴 카드 동적 생성 시 수정
    """
    user = session['user']
    role = user['role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if role == 'admin':
        cursor.execute("SELECT * FROM menus ORDER BY id ASC")
    else:
        cursor.execute('''
            SELECT m.* FROM menus m
            JOIN role_menu_permissions p ON m.menu_code = p.menu_code
            WHERE p.role = ? AND p.is_allowed = 1
            ORDER BY m.id ASC
        ''', (role,))
        
    rows = cursor.fetchall()
    conn.close()
    
    menu_list = [dict(row) for row in rows]
    return jsonify(menu_list)


# ------------------------------------------
# [기능 A] 장비 목록 전체 조회 API (사용자별 분기)
# ------------------------------------------
@app.route('/api/equipment', methods=['GET'])
@login_required
def get_equipment():
    """
    [역할] DB의 장비 데이터를 JSON 배열로 반환 (일반 사용자는 본인 등록 장비만, 관리자는 전체 + 소유자 정보 포함)
    
    [의존성 관계]
    - 의존하는 대상: get_db_connection(), equipment 및 users 테이블, session['user']
    - 이 API에 의존하는 대상: 프론트엔드(index.html)의 fetchEquipment() 자바스크립트 함수
    
    [변경 시 영향도]
    - 관리자 조회 시 users 테이블과 JOIN하여 소유자 username을 함께 전달함.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user['role'] == 'admin':
        cursor.execute('''
            SELECT e.*, u.username as owner_username 
            FROM equipment e
            LEFT JOIN users u ON e.user_id = u.id
            ORDER BY e.id DESC
        ''')
    else:
        cursor.execute('''
            SELECT e.*, u.username as owner_username 
            FROM equipment e
            LEFT JOIN users u ON e.user_id = u.id
            WHERE e.user_id = ?
            ORDER BY e.id DESC
        ''', (user['id'],))
        
    rows = cursor.fetchall()
    conn.close()
    
    equipment_list = [dict(row) for row in rows]
    return jsonify(equipment_list)


# ------------------------------------------
# [기능 B] 신규 장비 등록 API (Audit Log 및 소유자 저장)
# ------------------------------------------
@app.route('/api/equipment', methods=['POST'])
@login_required
def add_equipment():
    """
    [역할] 클라이언트가 보낸 JSON 데이터를 받아 소유자(user_id) 및 생성일/수정일과 함께 DB 저장 및 Audit Log 기록
    
    [의존성 관계]
    - 의존하는 대상: get_db_connection(), equipment 테이블, log_audit()
    - 이 API에 의존하는 대상: 프론트엔드(index.html) 등록 폼
    
    [변경 시 영향도]
    - 신규 장비 저장 시 user_id, created_at, updated_at이 자동 기록되며 Audit Log가 생성됩니다.
    """
    data = request.json
    user = session['user']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO equipment (name, category, manufacturer, model_name, purchase_date, serial_number, memo, user_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('name'), 
        data.get('category'), 
        data.get('manufacturer'), 
        data.get('model_name'), 
        data.get('purchase_date'), 
        data.get('serial_number'), 
        data.get('memo'),
        user['id'],
        now,
        now
    ))
    
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Audit Log 기록
    log_audit(user['id'], user['username'], 'INSERT', 'equipment', new_id, None, data)
    
    return jsonify({"message": "성공적으로 등록되었습니다!"})


# ------------------------------------------
# [기능 C] 기존 장비 수정 API (Audit Log 및 권한 검증)
# ------------------------------------------
@app.route('/api/equipment/<int:eq_id>', methods=['PUT'])
@login_required
def update_equipment(eq_id):
    """
    [역할] ID를 받아 권한 검증 후 장비 정보 수정 및 변경 전/후 Audit Log 기록
    
    [의존성 관계]
    - 의존하는 대상: get_db_connection(), equipment 테이블, log_audit()
    - 이 API에 의존하는 대상: 프론트엔드(index.html) 수정 폼
    
    [변경 시 영향도]
    - 일반 사용자는 본인 소유 장비만 수정 가능하며, 수정 시 updated_at이 갱신됩니다.
    """
    data = request.json
    user = session['user']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 기존 데이터 조회 (Audit Log 및 권한 체크)
    cursor.execute("SELECT * FROM equipment WHERE id = ?", (eq_id,))
    old_row = cursor.fetchone()
    if not old_row:
        conn.close()
        return jsonify({"error": "해당 장비를 찾을 수 없습니다."}), 404

    old_dict = dict(old_row)
    if user['role'] != 'admin' and old_dict['user_id'] != user['id']:
        conn.close()
        return jsonify({"error": "수정 권한이 없습니다."}), 403

    cursor.execute('''
        UPDATE equipment 
        SET name=?, category=?, manufacturer=?, model_name=?, purchase_date=?, serial_number=?, memo=?, updated_at=?
        WHERE id=?
    ''', (
        data.get('name'), 
        data.get('category'), 
        data.get('manufacturer'), 
        data.get('model_name'), 
        data.get('purchase_date'), 
        data.get('serial_number'), 
        data.get('memo'),
        now,
        eq_id
    ))
    
    conn.commit()
    conn.close()
    
    # Audit Log 기록
    log_audit(user['id'], user['username'], 'UPDATE', 'equipment', eq_id, old_dict, data)
    
    return jsonify({"message": "수정되었습니다."})


# ------------------------------------------
# [기능 D] 기존 장비 삭제 API (Audit Log 및 권한 검증)
# ------------------------------------------
@app.route('/api/equipment/<int:eq_id>', methods=['DELETE'])
@login_required
def delete_equipment(eq_id):
    """
    [역할] ID를 받아 권한 검증 후 장비 삭제 및 기존 데이터 Audit Log 기록
    
    [의존성 관계]
    - 의존하는 대상: get_db_connection(), equipment 테이블, log_audit()
    - 이 API에 의존하는 대상: 프론트엔드(index.html) 삭제 버튼
    
    [변경 시 영향도]
    - 일반 사용자는 본인 소유 장비만 삭제할 수 있습니다.
    """
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM equipment WHERE id = ?", (eq_id,))
    old_row = cursor.fetchone()
    if not old_row:
        conn.close()
        return jsonify({"error": "해당 장비를 찾을 수 없습니다."}), 404

    old_dict = dict(old_row)
    if user['role'] != 'admin' and old_dict['user_id'] != user['id']:
        conn.close()
        return jsonify({"error": "삭제 권한이 없습니다."}), 403

    cursor.execute("DELETE FROM equipment WHERE id = ?", (eq_id,))
    conn.commit()
    conn.close()
    
    # Audit Log 기록
    log_audit(user['id'], user['username'], 'DELETE', 'equipment', eq_id, old_dict, None)
    
    return jsonify({"message": "삭제되었습니다."})


# ------------------------------------------
# [기능 E] 메뉴 권한 관리 API (관리자 전용)
# ------------------------------------------
@app.route('/api/permissions', methods=['GET'])
@login_required
def get_permissions():
    """
    [역할] 전체 메뉴 권한 설정 정보 조회 API (관리자 전용)
    [의존성 관계] role_menu_permissions, menus 테이블
    [변경 시 영향도] 권한 관리 화면 렌더링 시 사용되며, 응답 구조 변경 시 권한 관리 템플릿(JS 로직)을 수정해야 합니다.
    """
    if session['user']['role'] != 'admin':
        return jsonify({"error": "관리자만 접근할 수 있습니다."}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, m.menu_name 
        FROM role_menu_permissions p
        JOIN menus m ON p.menu_code = m.menu_code
        ORDER BY p.role ASC, m.id ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(r) for r in rows])


@app.route('/api/permissions', methods=['POST'])
@login_required
def update_permissions():
    """
    [역할] 메뉴 권한 변경 및 Audit Log 기록 API (관리자 전용)
    [의존성 관계] role_menu_permissions 테이블, log_audit()
    [변경 시 영향도] 권한 저장 로직 또는 권한 체계(Role) 변경 시 수정해야 하며, Audit Log 형식 변경 시 함께 검토해야 합니다.
    """
    user = session['user']
    if user['role'] != 'admin':
        return jsonify({"error": "관리자만 접근할 수 있습니다."}), 403
        
    data = request.json  # list of { role, menu_code, is_allowed }
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 기존 데이터 가져오기 (Audit Log용)
    cursor.execute("SELECT * FROM role_menu_permissions")
    old_perms = [dict(r) for r in cursor.fetchall()]
    
    for item in data:
        cursor.execute('''
            INSERT INTO role_menu_permissions (role, menu_code, is_allowed, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(role, menu_code) DO UPDATE SET is_allowed=excluded.is_allowed, updated_at=excluded.updated_at
        ''', (item['role'], item['menu_code'], item['is_allowed'], now))
        
    conn.commit()
    conn.close()
    
    log_audit(user['id'], user['username'], 'UPDATE_PERMISSIONS', 'role_menu_permissions', None, old_perms, data)
    
    return jsonify({"message": "권한 설정이 업데이트되었습니다."})


# ==========================================
# 6. 서버 가동
# ==========================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)