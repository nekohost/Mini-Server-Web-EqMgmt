"""승인된 운영 smoke: 합성 이메일 인증 fixture만 준비하고 실제 HTTPS 가입·복구를 검사한다.

메일 발송/수신은 시험하지 않는다. 비밀·실제 회원 내용은 출력하지 않으며, 기존 계정은
변경하지 않는다. 이번 실행이 만든 계정만 정확한 식별자로 정리하고 감사/접근 로그는 남긴다.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request

from werkzeug.security import generate_password_hash

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
RELEASE = Path('/home/nekohost/.local/share/mini-server-eqmgmt/releases/optional-real-name-20260929T043205268927Z')
BASE = 'https://nekohost.org'
COMMIT = '706c537052b7453a790fea886395d30023b3f44e'
TABLES = ('users', 'equipment', 'equipments', 'equipment_options', 'lineup_nodes', 'categories',
          'manufacturers', 'approval_requests', 'menus', 'role_menu_permissions', 'sys_migrations',
          'equipment_files', 'equipment_imports', 'equipment_notification_log', 'user_settings')


def connect():
    connection = sqlite3.connect(ROOT / 'equipment.db', timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    return connection


def snapshot():
    with closing(connect()) as connection:
        return {table: hashlib.sha256(repr([tuple(row) for row in connection.execute(
            'SELECT * FROM ' + table + ' ORDER BY rowid')]).encode()).hexdigest() for table in TABLES}


def private_json(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


class Fields(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.csrf = None
        self.name = None
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'meta' and attributes.get('name') == 'csrf-token':
            self.csrf = attributes.get('content')
        if tag == 'input' and attributes.get('id') == 'Name':
            self.name = attributes


class Client:
    def __init__(self, marker):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.opener.addheaders = [('User-Agent', 'EqMgmt-Optional-Name-Smoke/' + marker)]
        with self.opener.open(BASE + '/register', timeout=15) as response:
            fields = Fields(response.read().decode())
            assert response.status == 200 and fields.csrf and fields.name is not None
            assert 'required' not in fields.name and fields.name.get('maxlength') == '100'
        self.csrf = fields.csrf

    def post(self, path, payload, expected, csrf=True):
        headers = {'Content-Type': 'application/json'}
        if csrf:
            headers['X-CSRFToken'] = self.csrf
        request = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), headers=headers)
        try:
            response = self.opener.open(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.status
            body = json.loads(response.read())
        assert status == expected, f'{path}: unexpected HTTP {status}'
        assert body.get('success') is (expected == 200), f'{path}: unexpected result'
        return status


def main():
    assert os.name == 'posix' and Path.cwd() == ROOT and ROOT.resolve() == ROOT
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                  env=dict(os.environ, GIT_OPTIONAL_LOCKS='0')).decode().strip() == COMMIT
    assert RELEASE.is_dir() and RELEASE.stat().st_uid == os.getuid() and not RELEASE.is_symlink()
    marker = secrets.token_hex(8)
    directory = RELEASE / ('smoke-' + marker)
    directory.mkdir(mode=0o700)
    login = 'qa_optional_' + marker
    email = login + '@example.invalid'
    password = 'Qa1!' + secrets.token_urlsafe(24)
    payload = {'LoginId': login, 'NickName': 'Optional Name QA', 'Password': password, 'Email': email}
    result = {'started_at': datetime.now(timezone.utc).isoformat(), 'commit': COMMIT,
              'base_url': BASE, 'fixture_login': login, 'mail_delivery_tested': False, 'checks': {}}
    private_json(directory / 'manifest.json', {key: value for key, value in result.items() if key != 'checks'})
    before = snapshot()
    owned_user = None
    pin_hashes = []

    def verify(client):
        pin = f'{secrets.randbelow(1000000):06d}'
        hashed = generate_password_hash(pin)
        expires = (datetime.now() + timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')
        with closing(connect()) as connection, connection:
            assert connection.execute('SELECT 1 FROM email_verifications WHERE Email=?', (email,)).fetchone() is None
            connection.execute('INSERT INTO email_verifications(Email,PinCodeHash,ExpiresAt,IsVerified) VALUES(?,?,?,0)',
                               (email, hashed, expires))
        pin_hashes.append(hashed)
        client.post('/api/auth/verify_pin', {'email': email, 'pin': pin}, 200)

    try:
        with closing(connect()) as connection:
            assert connection.execute("SELECT COUNT(*) FROM users WHERE Role='admin' AND IsDeleted='N'").fetchone()[0] > 0
            assert connection.execute('SELECT 1 FROM users WHERE LoginId=? OR Email=?', (login, email)).fetchone() is None
        client = Client(marker)
        outsider = Client(marker + '-other-session')
        result['checks']['register_html_optional'] = True
        verify(client)
        result['checks']['other_session_proof_rejected'] = outsider.post('/register', payload, 400)
        result['checks']['missing_csrf_rejected'] = client.post('/register', payload, 403, csrf=False)
        result['checks']['register_without_name'] = client.post('/register', payload, 200)
        with closing(connect()) as connection, connection:
            row = connection.execute('SELECT * FROM users WHERE LoginId=? AND Email=?', (login, email)).fetchone()
            assert row and row['Name'] == '' and row['Role'] == 'user' and row['notification_verified_email'] == email
            owned_user = row['UserId']
            assert connection.execute('SELECT 1 FROM email_verifications WHERE Email=?', (email,)).fetchone() is None
            old = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d %H:%M:%S')
            connection.execute("UPDATE users SET IsDeleted='Y',DeletedAt=?,SessionToken=? WHERE UserId=? AND LoginId=? AND Email=?",
                               (old, secrets.token_hex(16), owned_user, login, email))
        result['checks']['new_account_blank_user_role'] = True
        verify(client)
        result['checks']['recover_without_name'] = client.post('/register', payload, 200)
        with closing(connect()) as connection:
            row = connection.execute('SELECT * FROM users WHERE UserId=?', (owned_user,)).fetchone()
            assert row['LoginId'] == login and row['Email'] == email and row['Name'] == '' and row['Role'] == 'user'
            assert row['IsDeleted'] == 'N' and row['IsDeactivated'] == 'N' and row['SessionToken'] is None
            assert connection.execute('SELECT 1 FROM email_verifications WHERE Email=?', (email,)).fetchone() is None
        result['checks']['recovery_identity_role_and_token'] = True
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__, error=str(error)[:200])
    finally:
        try:
            with closing(connect()) as connection, connection:
                connection.execute('BEGIN IMMEDIATE')
                row = connection.execute('SELECT * FROM users WHERE LoginId=? AND Email=?', (login, email)).fetchone()
                if row is not None:
                    assert owned_user in (None, row['UserId']) and row['Role'] == 'user'
                    owned_user = row['UserId']
                    references = (('equipments', 'user_id'), ('equipment', 'UserId'), ('equipment_files', 'uploaded_by'),
                                  ('approval_requests', 'RequesterId'), ('approval_requests', 'ApproverId'),
                                  ('equipment_imports', 'user_id'), ('equipment_notification_log', 'user_id'),
                                  ('user_settings', 'UserId'), ('password_resets', 'UserId'))
                    for table, column in references:
                        assert connection.execute(f'SELECT COUNT(*) FROM {table} WHERE {column}=?', (owned_user,)).fetchone()[0] == 0
                    private_json(directory / 'synthetic-user-before-cleanup.private.json', dict(row))
                    assert connection.execute('DELETE FROM users WHERE UserId=? AND LoginId=? AND Email=?',
                                              (owned_user, login, email)).rowcount == 1
                challenge = connection.execute('SELECT * FROM email_verifications WHERE Email=?', (email,)).fetchone()
                if challenge:
                    assert challenge['PinCodeHash'] in pin_hashes
                    connection.execute('DELETE FROM email_verifications WHERE Email=? AND PinCodeHash=?', (email, challenge['PinCodeHash']))
            result['fixture_removed'] = True
            result['business_tables_unchanged'] = before == snapshot()
            assert result['business_tables_unchanged'], 'concurrent or unexpected business change; no automatic rollback'
            with closing(connect()) as connection:
                result['db_integrity'] = connection.execute('PRAGMA integrity_check').fetchone()[0]
                result['foreign_key_violations'] = len(connection.execute('PRAGMA foreign_key_check').fetchall())
                result['audit_events_retained'] = connection.execute('SELECT COUNT(*) FROM audit_logs WHERE ActorLoginId=?', (login,)).fetchone()[0]
            assert result['db_integrity'] == 'ok' and result['foreign_key_violations'] == 0
        except BaseException as error:
            result.update(status='failed', cleanup_error_type=type(error).__name__, cleanup_error=str(error)[:200])
        result['completed_at'] = datetime.now(timezone.utc).isoformat()
        result['evidence_path'] = str(directory)
        private_json(directory / 'result.json', result)
        print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
