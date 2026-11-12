"""Account creation from the user-management menu."""
from datetime import datetime
import sqlite3

from werkzeug.security import generate_password_hash

from utils.roadmap_validation import InputError, json_object, registration_fields


def account_creator(connection, user_id, session_token):
    """Return the live actor for both the page control and the protected write."""
    if not session_token:
        return None
    return connection.execute("""
        SELECT u.UserId, u.LoginId FROM users u
        JOIN role_menu_permissions p ON p.Role=u.Role AND p.MenuCode='users_management'
        WHERE u.UserId=? AND u.SessionToken=? AND u.Role='admin' AND p.IsAllowed=1
          AND COALESCE(u.IsDeleted,'N')='N' AND COALESCE(u.IsDeactivated,'N')='N'
    """, (user_id, session_token)).fetchone()


def create_account(connection, user_id, session_token, payload, log_audit):
    """Recheck authority under the SQLite writer lock and commit the account and audit together."""
    def require_creator():
        actor = account_creator(connection, user_id, session_token)
        if actor is None:
            raise InputError('사용자 관리 권한이 있는 관리자만 계정을 생성할 수 있습니다.', 403)
        return actor

    require_creator()
    data = json_object(payload)
    if data.keys() - {'LoginId', 'NickName', 'Password', 'Name', 'Role'}:
        raise InputError('계정 생성에 사용할 수 없는 입력 항목입니다.')
    role = data.get('Role', 'user')
    if role not in ('user', 'admin'):
        raise InputError('계정 역할은 일반 사용자 또는 관리자여야 합니다.')
    fields = registration_fields(data)
    login = fields['LoginId']
    password_hash = generate_password_hash(fields['Password'])

    with connection:
        connection.execute('BEGIN IMMEDIATE')
        actor = require_creator()
        if connection.execute('SELECT 1 FROM users WHERE LoginId=?', (login,)).fetchone():
            raise InputError('이미 등록된 아이디입니다.', 409)

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        inserted = connection.execute("""
            INSERT INTO users (LoginId, NickName, Name, Password, Role, Email, notification_verified_email,
                               IsDeactivated, IsDeleted, CreatedAt, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, NULL, NULL, 'N', 'N', ?, ?)
        """, (login, fields['NickName'], fields['Name'], password_hash, role, now, now))
        if inserted.rowcount != 1:
            raise sqlite3.IntegrityError('Account was not inserted')
        target_id = inserted.lastrowid
        log_audit(actor['UserId'], actor['LoginId'], 'ADMIN_CREATE_USER', 'users', target_id,
                  new_value={'LoginId': login, 'Role': role}, connection=connection)
    return target_id
