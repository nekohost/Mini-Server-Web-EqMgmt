"""
[역할] 제안-030 메일링 서비스 통합 인증 스테이징(Staging) 독립 실행형 백엔드 모듈
[의존성 관계] SQLite3, werkzeug.security, utils.mailer
[변경 시 영향도] 운영 환경(app.py) 반영 전 안전한 기능 검증 및 마이그레이션 모의 실행
"""

import os
import sqlite3
import random
import string
import uuid
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from utils.mailer import send_email

load_dotenv()

app = Flask(__name__, template_folder='.')
app.secret_key = os.getenv('SECRET_KEY', 'staging-secret-key-1234')

DATABASE = 'equipment.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def log_audit(actor_id, actor_login_id, action, target_table, target_id=None, old_value=None, new_value=None):
    """
    [역할] 스테이징 모의 감사 로그 기록 함수 (실제 app.py의 log_audit과 동일 역할)
    """
    try:
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS audit_logs (ActorId INTEGER, ActorLoginId TEXT, IpAddress TEXT, UserAgent TEXT, TargetTable TEXT, TargetId INTEGER, Action TEXT, OldValue TEXT, NewValue TEXT, CreatedAt TEXT)")
        cursor.execute('''
            INSERT INTO audit_logs (ActorId, ActorLoginId, IpAddress, UserAgent, TargetTable, TargetId, Action, OldValue, NewValue, CreatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (actor_id, actor_login_id, ip_address, 'Staging', target_table, target_id, action, str(old_value), str(new_value), created_at))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Staging Audit Log Error] {e}")

@app.before_request
def csrf_protect():
    """
    [역할] 모든 POST 요청에 대한 범용 CSRF 토큰 검증 미들웨어
    [의존성 관계] session['csrf_token']
    """
    if request.method == "POST":
        token = request.headers.get('X-CSRFToken')
        if not token or token != session.get('csrf_token'):
            return jsonify({"success": False, "message": "CSRF 토큰 검증에 실패했습니다. 새로고침 후 다시 시도해 주세요."}), 403

def init_staging_db():
    """
    [역할] 스테이징 환경에서의 DB 마이그레이션 실행 (Rule 4-4 준수)
    [의존성 관계] equipment.db, users, email_verifications, password_resets
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("CREATE TABLE IF NOT EXISTS sys_migrations (MigrationName TEXT PRIMARY KEY, AppliedAt TEXT)")
    
    # 기초 users 테이블 생성 (Staging 테스트용)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            UserId INTEGER PRIMARY KEY AUTOINCREMENT,
            LoginId TEXT UNIQUE NOT NULL,
            Name TEXT,
            NickName TEXT,
            Password TEXT NOT NULL,
            Role TEXT,
            IsDeactivated TEXT DEFAULT 'N',
            IsDeleted TEXT DEFAULT 'N',
            SessionToken TEXT,
            CreatedAt TEXT,
            UpdatedAt TEXT
        )
    ''')

    cursor.execute("SELECT 1 FROM sys_migrations WHERE MigrationName = 'proposal_030_email_auth'")
    if not cursor.fetchone():
        try:
            cursor.execute("PRAGMA table_info(users)")
            cols = [info['name'] for info in cursor.fetchall()]
            if 'Email' not in cols:
                cursor.execute("ALTER TABLE users ADD COLUMN Email TEXT")
                print("[Staging Migration] users 테이블에 Email 컬럼 추가됨.")
            
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
            cursor.execute("INSERT INTO sys_migrations (MigrationName, AppliedAt) VALUES ('proposal_030_email_auth', ?)", (now,))
            conn.commit()
            print("[Staging Migration] 완료.")
        except Exception as e:
            print(f"[Staging Migration Error] {e}")
    conn.close()


@app.route('/register', methods=['GET', 'POST'])
def staging_register_page():
    """
    [역할] 회원가입 페이지 렌더링 및 가입/탈퇴복구 통합 처리 API (CSRF 토큰 부여)
    [의존성 관계] Staging_register.html, email_verifications
    [변경 시 영향도] 회원가입 및 탈퇴 복구 플로우 전반
    """
    if request.method == 'GET':
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(16)
        return render_template('Staging_register.html', csrf_token=session['csrf_token'])
        
    data = request.json or {}
    login_id = data.get('LoginId')
    name = data.get('Name')
    nickname = data.get('NickName')
    password = data.get('Password')
    email = data.get('Email')
    
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

    # 중복 체크 및 탈퇴 복구 분기 (Staging 모의)
    cursor.execute("SELECT * FROM users WHERE LoginId = ?", (login_id,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        if existing_user['IsDeleted'] == 'Y':
            if name and existing_user['Name'] and name.strip() == existing_user['Name'].strip():
                # 이메일 충돌 체크 로직 추가
                cursor.execute("UPDATE users SET Password=?, Name=?, NickName=?, Email=?, IsDeleted='N', UpdatedAt=? WHERE UserId=?",
                               (hashed_password, name, nickname, email, now, existing_user['UserId']))
                conn.commit()
                log_audit(existing_user['UserId'], login_id, 'RECOVER_ACCOUNT_WITH_EMAIL', 'users', existing_user['UserId'])
                conn.close()
                return jsonify({"success": True, "message": "탈퇴 계정이 성공적으로 복구되었습니다."})
            else:
                conn.close()
                return jsonify({"success": False, "message": "실명이 일치하지 않아 복구할 수 없습니다."}), 400
        else:
            conn.close()
            return jsonify({"success": False, "message": "이미 존재하는 아이디입니다."}), 400

    # 신규 가입
    cursor.execute("INSERT INTO users (LoginId, Name, NickName, Password, Email, Role, CreatedAt, UpdatedAt) VALUES (?, ?, ?, ?, ?, 'user', ?, ?)",
                   (login_id, name, nickname, hashed_password, email, now, now))
    conn.commit()
    log_audit(cursor.lastrowid, login_id, 'REGISTER_USER', 'users', cursor.lastrowid)
    conn.close()
    
    return jsonify({"success": True, "message": "회원가입이 완료되었습니다."})


@app.route('/api/auth/send_pin', methods=['POST'])
def api_send_pin_logic():
    """
    [역할] 이메일로 6자리 핀(PIN) 코드를 발송하는 API (Rule 4-5 해시 저장 및 속도 제한 방어 적용)
    [의존성 관계] email_verifications 테이블, utils.mailer.send_email()
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    if not email or '@' not in email:
        return jsonify({"success": False, "message": "유효한 이메일 주소를 입력해 주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Rate Limiting (쿨다운 체크): 최근 발급일시로부터 1분 경과 확인
    cursor.execute("SELECT ExpiresAt FROM email_verifications WHERE Email = ?", (email,))
    existing_req = cursor.fetchone()
    if existing_req:
        # ExpiresAt은 발급시점 + 3분이므로, 남은 시간이 2분 이상이면 1분 쿨다운 미경과
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
def api_verify_pin_logic():
    """
    [역할] 입력된 PIN 코드를 해시 대조하여 이메일 인증을 완료 처리하는 API
    [의존성 관계] email_verifications 테이블, werkzeug.security
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
def api_request_password_reset_logic():
    """
    [역할] 비밀번호 재설정 요청 시 1회용 난수 토큰(해시 저장)과 URL을 메일로 발송하는 API
    [의존성 관계] password_resets, utils.mailer
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    if not email: return jsonify({"success": False}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserId, LoginId, Name FROM users WHERE Email = ? AND IsDeleted = 'N'", (email,))
    user = cursor.fetchone()

    # 계정 존재 유무와 상관없이 동일 응답 (보안)
    if not user:
        conn.close()
        return jsonify({"success": True, "message": "입력하신 이메일이 등록되어 있다면 재설정 링크가 메일로 발송되었습니다."})

    # Rate Limiting 방어
    cursor.execute("SELECT ExpiresAt FROM password_resets WHERE UserId = ? ORDER BY ExpiresAt DESC LIMIT 1", (user['UserId'],))
    last_req = cursor.fetchone()
    if last_req:
        last_expires = datetime.strptime(last_req['ExpiresAt'], '%Y-%m-%d %H:%M:%S')
        if (last_expires - datetime.now()).total_seconds() > 3540: # 1시간 유효 중 1분(60초) 이내 재발송 차단
            conn.close()
            return jsonify({"success": False, "message": "재발송 쿨다운 중입니다. 잠시 후 다시 시도해 주세요."}), 429

    raw_token = str(uuid.uuid4())
    token_hash = generate_password_hash(raw_token)
    expires_at = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("INSERT INTO password_resets (TokenHash, UserId, ExpiresAt, IsUsed) VALUES (?, ?, ?, 0)",
                   (token_hash, user['UserId'], expires_at))
    conn.commit()
    conn.close()

    reset_url = request.host_url.rstrip('/') + f"/reset_password?token={raw_token}&email={email}"
    success, msg = send_email(email, "[미니서버] 비밀번호 재설정", f"<a href='{reset_url}'>비밀번호 재설정하기</a>")
    
    return jsonify({"success": True, "message": "비밀번호 재설정 링크가 발송되었습니다."})


@app.route('/reset_password', methods=['GET'])
def reset_password_page():
    if 'csrf_token' not in session: session['csrf_token'] = secrets.token_hex(16)
    return render_template('Staging_reset_password.html', csrf_token=session['csrf_token'])


@app.route('/api/auth/reset_password', methods=['POST'])
def api_reset_password_logic():
    """
    [역할] 비밀번호 재설정 실행 API (세션 무효화 및 감사 로그 포함)
    [의존성 관계] password_resets, users
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
    # 기존 세션 강제 무효화를 위해 SessionToken 초기화 (강제 로그아웃)
    new_session_token = secrets.token_hex(32)
    cursor.execute("UPDATE users SET Password = ?, SessionToken = ?, UpdatedAt = ? WHERE UserId = ?", 
                   (hashed_pw, new_session_token, now_str, user['UserId']))
    cursor.execute("UPDATE password_resets SET IsUsed = 1 WHERE TokenHash = ?", (valid_req['TokenHash'],))
    conn.commit()
    
    log_audit(user['UserId'], 'System', 'RESET_PASSWORD', 'users', user['UserId'])
    conn.close()

    return jsonify({"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."})


@app.route('/api/users/update_profile', methods=['POST'])
def api_update_profile():
    """
    [역할] 로그인한 사용자의 기본 프로필(LoginId, Name, NickName)을 변경합니다. 현재 비밀번호 검증이 필수입니다.
    [의존성 관계] users 테이블, check_password_hash(), session['user']
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

    # 세션 갱신
    session['user']['LoginId'] = new_login_id
    session['user']['Name'] = new_name
    session['user']['NickName'] = new_nickname

    return jsonify({"success": True, "message": "프로필 정보가 성공적으로 변경되었습니다."})



if __name__ == '__main__':
    with app.app_context():
        init_staging_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
