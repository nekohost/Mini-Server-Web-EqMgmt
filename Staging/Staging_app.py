"""
[역할] 제안-030 메일링 서비스 통합 인증 스테이징(Staging) 백엔드 모듈
[의존성 관계] SQLite3, werkzeug.security, utils.mailer, app.py
[변경 시 영향도] 운영 환경(app.py) 반영 전 안전한 기능 검증 및 마이그레이션 모의 실행
"""

import os
import sqlite3
import random
import string
import uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from utils.mailer import send_email

load_dotenv()

DATABASE = 'equipment.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

"""
[역할] 이메일 연동 관련 무정지 데이터베이스 마이그레이션 수행
[의존성 관계] sys_migrations, users, email_verifications, password_resets 테이블
[변경 시 영향도] users 테이블에 Email 컬럼 추가 및 인증/재설정 전용 테이블 2종 신설
"""
def migrate_email_features():
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 1. sys_migrations 체크
    cursor.execute("CREATE TABLE IF NOT EXISTS sys_migrations (MigrationName TEXT PRIMARY KEY, AppliedAt TEXT)")
    cursor.execute("SELECT 1 FROM sys_migrations WHERE MigrationName = 'proposal_030_email_auth'")
    if cursor.fetchone():
        conn.close()
        return

    try:
        # SQLite 2단계 마이그레이션 (ALTER TABLE TEXT 후 UNIQUE INDEX 생성)
        cursor.execute("PRAGMA table_info(users)")
        cols = [info['name'] for info in cursor.fetchall()]
        if 'Email' not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN Email TEXT")
            print("[Staging Migration] users 테이블에 Email 컬럼이 성공적으로 추가되었습니다.")

        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(Email) WHERE Email IS NOT NULL")

        # email_verifications 신설
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_verifications (
                Email TEXT PRIMARY KEY,
                PinCode TEXT NOT NULL,
                ExpiresAt TEXT NOT NULL,
                IsVerified INTEGER DEFAULT 0
            )
        ''')

        # password_resets 신설
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS password_resets (
                Token TEXT PRIMARY KEY,
                UserId INTEGER NOT NULL,
                ExpiresAt TEXT NOT NULL,
                IsUsed INTEGER DEFAULT 0
            )
        ''')

        cursor.execute("INSERT INTO sys_migrations (MigrationName, AppliedAt) VALUES ('proposal_030_email_auth', ?)", (now,))
        conn.commit()
        print("[Staging Migration] proposal_030_email_auth 마이그레이션이 완벽하게 완료되었습니다.")
    except Exception as e:
        print(f"[Staging Migration Error] {e}")
    finally:
        conn.close()

# 스테이징 모듈 로드 시 마이그레이션 자동 실행
migrate_email_features()

"""
[역할] 회원가입/이메일 변경 시 입력된 메일로 6자리 핀(PIN) 코드를 발송하는 API
[의존성 관계] email_verifications 테이블, utils.mailer.send_email()
[변경 시 영향도] 사용자의 이메일 수신함으로 임의 PIN 번호 발송 및 인증 대기열 생성
"""
def api_send_pin_logic():
    data = request.json or {}
    email = data.get('email', '').strip()
    if not email or '@' not in email:
        return jsonify({"success": False, "message": "유효한 이메일 주소를 입력해 주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # 이미 다른 활성 유저가 사용 중인 이메일인지 체크 (자신의 이메일 제외)
    current_user_id = session.get('user', {}).get('UserId')
    cursor.execute("SELECT UserId FROM users WHERE Email = ? AND (IsDeleted = 'N' OR IsDeleted IS NULL)", (email,))
    existing = cursor.fetchone()
    if existing and existing['UserId'] != current_user_id:
        conn.close()
        return jsonify({"success": False, "message": "이미 다른 계정에 등록되어 사용 중인 이메일 주소입니다."}), 400

    # 6자리 난수 PIN 생성
    pin_code = ''.join(random.choices(string.digits, k=6))
    expires_at = (datetime.now() + timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')

    # DB 저장 (UPSERT)
    cursor.execute('''
        INSERT INTO email_verifications (Email, PinCode, ExpiresAt, IsVerified)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(Email) DO UPDATE SET PinCode=excluded.PinCode, ExpiresAt=excluded.ExpiresAt, IsVerified=0
    ''', (email, pin_code, expires_at))
    conn.commit()
    conn.close()

    # 메일 발송
    subject = "[미니서버 관리시스템] 이메일 인증 PIN 번호 안내"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e2e8f0; rounded-radius: 10px;">
        <h2 style="color: #0284c7;">이메일 인증 PIN 코드</h2>
        <p>요청하신 인증 PIN 번호입니다. <strong>3분 이내</strong>에 입력해 주세요.</p>
        <div style="background-color: #f1f5f9; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 5px; color: #0f172a; margin: 20px 0;">
            {pin_code}
        </div>
        <p style="font-size: 12px; color: #64748b;">본인이 요청하지 않은 경우 이 메일을 무시하시기 바랍니다.</p>
    </div>
    """

    success, msg = send_email(email, subject, body_html)
    if success:
        return jsonify({"success": True, "message": "인증 PIN 코드가 이메일로 발송되었습니다. (3분 유효)"})
    else:
        return jsonify({"success": False, "message": f"메일 발송에 실패했습니다: {msg}"}), 500

"""
[역할] 사용자가 입력한 PIN 코드를 검증하여 이메일 인증을 완료 처리하는 API
[의존성 관계] email_verifications 테이블
[변경 시 영향도] email_verifications.IsVerified 상태를 1로 변경하여 회원가입/이메일 변경 허용
"""
def api_verify_pin_logic():
    data = request.json or {}
    email = data.get('email', '').strip()
    pin = data.get('pin', '').strip()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if not email or not pin:
        return jsonify({"success": False, "message": "이메일과 PIN 코드를 모두 입력해 주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM email_verifications WHERE Email = ?", (email,))
    record = cursor.fetchone()

    if not record:
        conn.close()
        return jsonify({"success": False, "message": "인증 요청 내역을 찾을 수 없습니다. 다시 발송해 주세요."}), 400

    if record['ExpiresAt'] < now_str:
        conn.close()
        return jsonify({"success": False, "message": "PIN 코드가 만료되었습니다 (3분 초과). 다시 발송해 주세요."}), 400

    if record['PinCode'] != pin:
        conn.close()
        return jsonify({"success": False, "message": "PIN 코드가 일치하지 않습니다. 다시 확인해 주세요."}), 400

    # 인증 성공 처리
    cursor.execute("UPDATE email_verifications SET IsVerified = 1 WHERE Email = ?", (email,))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "이메일 인증이 완료되었습니다!"})

"""
[역할] 비밀번호 찾기(재설정 메일 발송) 요청 API
[의존성 관계] users, password_resets 테이블, utils.mailer.send_email()
[변경 시 영향도] 등록된 이메일 사용자에 한해 1시간 유효의 1회용 비밀번호 재설정 URL을 메일로 발송
"""
def api_request_password_reset_logic():
    data = request.json or {}
    email = data.get('email', '').strip()

    if not email:
        return jsonify({"success": False, "message": "이메일 주소를 입력해 주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserId, LoginId, Name FROM users WHERE Email = ? AND (IsDeleted = 'N' OR IsDeleted IS NULL)", (email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        # 보안을 위해 계정 존재 여부를 직관적으로 알리지 않고 동일 문구 리턴
        return jsonify({"success": True, "message": "입력하신 이메일이 등록되어 있다면 재설정 링크가 메일로 발송되었습니다."})

    token = str(uuid.uuid4())
    expires_at = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("INSERT INTO password_resets (Token, UserId, ExpiresAt, IsUsed) VALUES (?, ?, ?, 0)",
                   (token, user['UserId'], expires_at))
    conn.commit()
    conn.close()

    # 재설정 URL 생성 (Request host 기반)
    reset_url = request.host_url.rstrip('/') + f"/reset_password?token={token}"

    subject = "[미니서버 관리시스템] 비밀번호 재설정 링크 안내"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
        <h2 style="color: #0284c7;">비밀번호 재설정 안내</h2>
        <p>안녕하세요, {user['Name']}님({user['LoginId']}). 아래 버튼을 클릭하여 새 비밀번호를 설정해 주세요.</p>
        <p>본 링크는 <strong>1시간 동안</strong> 유효하며, 1회에 한해 사용 가능합니다.</p>
        <div style="margin: 25px 0;">
            <a href="{reset_url}" style="background-color: #0284c7; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">비밀번호 재설정하기</a>
        </div>
        <p style="font-size: 12px; color: #64748b;">버튼이 클릭되지 않는 경우 아래 URL을 복사하여 브라우저 주소창에 붙여넣으세요:<br>{reset_url}</p>
    </div>
    """

    success, msg = send_email(email, subject, body_html)
    return jsonify({"success": True, "message": "비밀번호 재설정 링크가 이메일로 발송되었습니다."})

"""
[역할] 비밀번호 재설정 토큰 검증 및 최종 변경 처리 API
[의존성 관계] password_resets, users 테이블, werkzeug.security
[변경 시 영향도] 대상 유저의 비밀번호를 안전하게 변경하고 토큰을 IsUsed=1 처리함
"""
def api_reset_password_logic():
    data = request.json or {}
    token = data.get('token', '').strip()
    new_password = data.get('new_password', '').strip()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if not token or not new_password:
        return jsonify({"success": False, "message": "토큰과 새 비밀번호를 모두 입력해 주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM password_resets WHERE Token = ?", (token,))
    reset_req = cursor.fetchone()

    if not reset_req:
        conn.close()
        return jsonify({"success": False, "message": "유효하지 않거나 존재하지 않는 토큰입니다."}), 400

    if reset_req['IsUsed'] == 1:
        conn.close()
        return jsonify({"success": False, "message": "이미 사용된 재설정 링크입니다."}), 400

    if reset_req['ExpiresAt'] < now_str:
        conn.close()
        return jsonify({"success": False, "message": "비밀번호 재설정 링크가 만료되었습니다 (1시간 초과)."}), 400

    # 기존 비밀번호 동일 여부 체크
    cursor.execute("SELECT Password FROM users WHERE UserId = ?", (reset_req['UserId'],))
    user_rec = cursor.fetchone()
    if user_rec and check_password_hash(user_rec['Password'], new_password):
        conn.close()
        return jsonify({"success": False, "message": "새 비밀번호는 기존 비밀번호와 다르게 설정해야 합니다."}), 400

    # 비밀번호 업데이트 및 토큰 사용 완료 처리
    hashed_pw = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET Password = ?, UpdatedAt = ? WHERE UserId = ?", (hashed_pw, now_str, reset_req['UserId']))
    cursor.execute("UPDATE password_resets SET IsUsed = 1 WHERE Token = ?", (token,))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인해 주세요."})
