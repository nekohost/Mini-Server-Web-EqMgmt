"""Administrator account creation. Storage tests run offline. HTTP tests use an isolated Linux app."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash

from utils import admin_accounts
from utils.roadmap_validation import InputError


CREATE = '/api/users/create'
ACTION = 'ADMIN_CREATE_USER'
PASSWORD = '  Fixture9!account  '
FIELDS = {'LoginId': 'new-user', 'NickName': ' 새 별명 ', 'Password': PASSWORD}


class AccountTransactionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'fixture.db'
        with closing(self.connect()) as db:
            db.executescript("""
                CREATE TABLE users (UserId INTEGER PRIMARY KEY, LoginId TEXT UNIQUE, NickName, Name,
                    Password, Role, SessionToken, Email TEXT UNIQUE, notification_verified_email,
                    IsDeleted DEFAULT 'N', IsDeactivated DEFAULT 'N', CreatedAt, UpdatedAt);
                CREATE TABLE role_menu_permissions (Role, MenuCode, IsAllowed);
                CREATE TABLE audit_logs (ActorId, ActorLoginId, Action, TargetTable, TargetId, OldValue, NewValue);
                INSERT INTO users(UserId,LoginId,Role,SessionToken) VALUES (1,'creator','admin','live');
                INSERT INTO role_menu_permissions VALUES ('admin','users_management',1);
            """)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def record(actor_id, actor_login, action, table, target, *, new_value, connection):
        connection.execute('INSERT INTO audit_logs VALUES (?,?,?,?,?,NULL,?)',
                           (actor_id, actor_login, action, table, target, json.dumps(new_value)))

    def create(self, data):
        with closing(self.connect()) as db:
            return admin_accounts.create_account(db, 1, 'live', data, self.record)

    def test_fields_roles_and_hash(self):
        for role, extra, name in [('user', {}, ''), ('admin', {'Role': 'admin', 'Name': ' 실명 '}, '실명')]:
            target = self.create(dict(FIELDS, LoginId='  account-' + role + ' ', **extra))
            with closing(self.connect()) as db:
                row = db.execute('SELECT * FROM users WHERE UserId=?', (target,)).fetchone()
                self.assertEqual((row['Role'], row['LoginId'], row['Name'], row['NickName']),
                                 (role, 'account-' + role, name, '새 별명'))
                self.assertEqual((row['Email'], row['notification_verified_email'], row['SessionToken']), (None, None, None))
                self.assertTrue(check_password_hash(row['Password'], PASSWORD))
                self.assertFalse(check_password_hash(row['Password'], PASSWORD.strip()))
                audit = db.execute('SELECT * FROM audit_logs WHERE TargetId=?', (target,)).fetchone()
                self.assertEqual((audit['ActorId'], audit['ActorLoginId'], audit['Action']), (1, 'creator', ACTION))
                self.assertEqual(json.loads(audit['NewValue']), {'LoginId': row['LoginId'], 'Role': role})

    def test_invalid_input_never_creates_an_account(self):
        cases = [None, [], {}]
        cases.extend(dict(FIELDS, **overrides) for overrides in (
            {'Role': None}, {'Role': []}, {'Role': 'owner'}, {'Role': 'ADMIN'}, {'Email': 'x@example.test'},
            {'notification_verified_email': 'x@example.test'}, {'SessionToken': 'custom'}, {'LoginId': 'x!'},
            {'LoginId': 'a' * 65}, {'NickName': '  '}, {'NickName': 'a' * 101}, {'Name': []},
            {'Name': 'a' * 101}, {'Password': 'OnlyLetters'}, {'Password': 'a9!' * 86},
        ))
        for index, data in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(InputError) as caught:
                self.create(data)
            self.assertEqual(caught.exception.status, 400)
        with closing(self.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0], 0)

    def test_revocation_during_hash_is_rechecked_under_the_write_lock(self):
        for change, restore in [
            ("UPDATE users SET SessionToken='revoked'", "UPDATE users SET SessionToken='live'"),
            ("UPDATE users SET Role='user'", "UPDATE users SET Role='admin'"),
            ("UPDATE users SET IsDeactivated='Y'", "UPDATE users SET IsDeactivated='N'"),
            ("UPDATE users SET IsDeleted='Y'", "UPDATE users SET IsDeleted='N'"),
            ('UPDATE role_menu_permissions SET IsAllowed=0', 'UPDATE role_menu_permissions SET IsAllowed=1'),
        ]:
            def revoke(_password):
                with closing(self.connect()) as db, db:
                    db.execute(change)
                return 'unused-fixture-hash'

            with self.subTest(change=change), patch.object(admin_accounts, 'generate_password_hash', revoke):
                with self.assertRaises(InputError) as caught:
                    self.create(FIELDS)
                self.assertEqual(caught.exception.status, 403)
            with closing(self.connect()) as db, db:
                db.execute(restore)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0], 0)

    def test_concurrent_duplicate_and_failed_audit(self):
        start = Barrier(2)

        def submit():
            start.wait(timeout=5)
            try:
                self.create(FIELDS)
                return 201
            except InputError as error:
                return error.status

        with ThreadPoolExecutor(2) as pool:
            attempts = [pool.submit(submit) for _ in range(2)]
            self.assertEqual(sorted(task.result(timeout=10) for task in attempts), [201, 409])
        with closing(self.connect()) as db:
            db.execute("""CREATE TRIGGER reject_audit BEFORE INSERT ON audit_logs
                          BEGIN SELECT RAISE(ABORT,'fixture audit failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.create(dict(FIELDS, LoginId='retry-user'))
        with closing(self.connect()) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM users WHERE LoginId='retry-user'").fetchone())
            self.assertEqual(db.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0], 1)
            db.execute('DROP TRIGGER reject_audit')
        self.create(dict(FIELDS, LoginId='retry-user'))

    def test_existing_rows_remain_reserved_independently_of_historical_audits(self):
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO users(LoginId,Role,IsDeleted) VALUES ('withdrawn','user','Y')")
            db.execute("INSERT INTO audit_logs(ActorLoginId,Action,TargetTable) VALUES ('archived','SYSTEM_HARD_DELETE','users')")
        for login in ('creator', 'withdrawn'):
            with self.subTest(login=login), self.assertRaises(InputError) as caught:
                self.create(dict(FIELDS, LoginId=login))
            self.assertEqual(caught.exception.status, 409)
        self.create(dict(FIELDS, LoginId='archived'))


    def test_credential_endpoint_suppresses_even_materialized_error_bodies(self):
        from werkzeug.wrappers import Request, Response
        from utils.http_security import legacy_audit_payloads
        from utils.http_audit_queue import payload_visible

        request = Request.from_values(path=CREATE, method='POST', json=FIELDS)
        request.endpoint = 'api_create_user'
        request.get_data(cache=True)
        for status in (201, 400, 401, 403, 409, 500):
            response = Response(json.dumps({'detail': PASSWORD}), status=status, mimetype='application/json')
            self.assertEqual(legacy_audit_payloads(request, response, 'fixture-secret', ()), (None, None))
        self.assertFalse(payload_visible(CREATE))


@unittest.skipUnless(sys.platform == 'linux', 'The full Flask application runs only in an isolated Linux fixture')
class AccountHttpTests(unittest.TestCase):
    def setUp(self):
        if __package__:
            from .test_access_log_separation import HEADERS, client_for, fixture_app
        else:
            from test_access_log_separation import HEADERS, client_for, fixture_app
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.module = fixture_app(Path(temp.name))
        self.addCleanup(self.module.on_app_exit)
        # Establish the normal journal mode before anonymous and authenticated clients open parallel connections.
        with closing(self.db()) as db:
            self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
        self.admin = client_for(self.module)
        self.regular = client_for(self.module, 41202)
        self.headers = HEADERS
        mail = patch.object(self.module, 'send_email', return_value=(True, 'fixture'))
        self.mail = mail.start()
        self.addCleanup(mail.stop)

    def db(self):
        db = sqlite3.connect(self.module.DATABASE_PATH)
        db.row_factory = sqlite3.Row
        return db

    def csrf(self, client):
        with client.session_transaction() as session:
            return {'X-CSRFToken': session['csrf_token']}

    def anonymous(self):
        client = self.module.app.test_client()
        client.get('/login', headers={'Accept': 'application/json'})
        return client

    def login(self, login):
        client = self.anonymous()
        for password, status in [(PASSWORD.strip(), 400), (PASSWORD, 200)]:
            response = client.post('/login', json={'LoginId': login, 'Password': password}, headers=self.csrf(client))
            self.assertEqual(response.status_code, status)
        client.get('/mypage')  # Successful login rotates the session and issues a new form token.
        return client

    def verify_email(self, client, email):
        headers = self.csrf(client)
        with patch.object(self.module.secrets, 'randbelow', return_value=135792):
            sent = client.post('/api/auth/send_pin', json={'email': email}, headers=headers)
        self.assertEqual(sent.status_code, 200, sent.get_json())
        verified = client.post('/api/auth/verify_pin', json={'email': email, 'pin': '135792'}, headers=headers)
        self.assertEqual(verified.status_code, 200, verified.get_json())

    def test_both_roles_login_and_credentials_stay_out_of_responses_and_logs(self):
        responses = []
        hashes = []
        for fields, headers, status in [(dict(FIELDS, Role='owner'), self.headers, 400), (FIELDS, {}, 403)]:
            rejected = self.admin.post(CREATE, json=fields, headers=headers)
            self.assertEqual(rejected.status_code, status)
            responses.append(rejected)
        with self.admin.session_transaction() as session:
            session['user'] = dict(session['user'], LoginId='stale-cookie-name')
        for role, extra in [('user', {}), ('admin', {'Role': 'admin', 'Name': '이름'})]:
            login = 'created-' + role
            data = dict(FIELDS, LoginId=login, **extra)
            response = self.admin.post(CREATE, json=data, headers=self.headers)
            self.assertEqual(response.status_code, 201)
            responses.append(response)
            client = self.login(login)
            me = client.get('/api/me')
            self.assertEqual((me.json['Role'], me.json['Email'], me.json['UserId']),
                             (role, None, response.json['UserId']))
            page = client.get('/users_management').get_data(as_text=True)
            self.assertEqual('id="openCreateUser"' in page, role == 'admin')
            self.assertEqual(client.get('/api/users').status_code, 200 if role == 'admin' else 403)
            duplicate = self.admin.post(CREATE, json=data, headers=self.headers)
            self.assertEqual(duplicate.status_code, 409)
            responses.extend([me, duplicate])
            with closing(self.db()) as db:
                hashes.append(db.execute('SELECT Password FROM users WHERE LoginId=?', (login,)).fetchone()[0])
                self.assertTrue(check_password_hash(hashes[-1], PASSWORD))
                audit = db.execute('SELECT * FROM audit_logs WHERE Action=? AND TargetId=?',
                                   (ACTION, me.json['UserId'])).fetchone()
                self.assertEqual((audit['ActorId'], audit['ActorLoginId']), (41201, 'access-user-41201'))
                self.assertEqual(json.loads(audit['NewValue']), {'LoginId': login, 'Role': role})
        self.mail.assert_not_called()
        self.module.access_log_queue.join()
        with closing(self.db()) as db:
            access = db.execute('SELECT * FROM access_logs').fetchall()
            requests = [r for r in access if r['RequestPath'] == CREATE]
            self.assertCountEqual([r['StatusCode'] for r in requests], [400, 403, 201, 409, 201, 409])
            self.assertTrue(all(r['RequestPayload'] is None and r['ResponsePayload'] is None for r in requests))
            audit = db.execute('SELECT * FROM audit_logs').fetchall()
            observed = [r.get_data(as_text=True) for r in responses]
            observed.extend(str(tuple(row)) for row in [*access, *audit])
            for secret in [PASSWORD.strip(), *hashes]:
                self.assertFalse(any(secret in item for item in observed), 'credential found in an output surface')

    def test_permissions_csrf_and_session_status(self):
        def denied(client, status, headers):
            self.assertEqual(client.post(CREATE, json=FIELDS, headers=headers).status_code, status)

        denied(self.anonymous(), 401, self.headers)
        denied(self.admin, 403, {})
        denied(self.admin, 403, {'X-CSRFToken': 'wrong'})
        with closing(self.db()) as db, db:
            db.execute("UPDATE role_menu_permissions SET IsAllowed=1 WHERE Role='user' AND MenuCode='users_management'")
        with self.regular.session_transaction() as session:
            session['user'] = dict(session['user'], Role='admin')
        denied(self.regular, 403, self.headers)
        self.assertNotIn('id="openCreateUser"', self.regular.get('/users_management').get_data(as_text=True))
        for sql in ["UPDATE role_menu_permissions SET IsAllowed=0", 'DELETE FROM role_menu_permissions']:
            with closing(self.db()) as db, db:
                db.execute(sql + " WHERE Role='admin' AND MenuCode='users_management'")
            denied(self.admin, 403, self.headers)
            self.assertNotIn('id="openCreateUser"', self.admin.get('/users_management').get_data(as_text=True))
        with closing(self.db()) as db, db:
            db.execute("INSERT INTO role_menu_permissions(Role,MenuCode,IsAllowed) VALUES('admin','users_management',1)")
            db.execute("UPDATE users SET IsDeactivated='Y' WHERE UserId=41201")
        denied(self.admin, 403, self.headers)
        with closing(self.db()) as db, db:
            db.execute("UPDATE users SET IsDeactivated='N', SessionToken=NULL WHERE UserId=41201")
        denied(self.admin, 401, self.headers)
        with closing(self.db()) as db:
            self.assertIsNone(db.execute('SELECT 1 FROM users WHERE LoginId=?', (FIELDS['LoginId'],)).fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM audit_logs WHERE Action=?', (ACTION,)).fetchone())

    def test_own_email_needs_password_and_current_browser_pin(self):
        self.assertEqual(self.admin.post(CREATE, json=FIELDS, headers=self.headers).status_code, 201)
        client = self.login(FIELDS['LoginId'])
        email = 'owner@example.test'
        data = {'email': email, 'current_password': PASSWORD}
        def update(fields):
            return client.post('/api/users/update_email', json=fields, headers=self.csrf(client))
        self.assertEqual(update(data).status_code, 400)
        self.verify_email(self.admin, email)
        self.assertEqual(update(data).status_code, 400)
        with closing(self.db()) as db, db:
            db.execute('DELETE FROM email_verifications WHERE Email=?', (email,))
        self.verify_email(client, email)
        self.assertEqual(update(dict(data, current_password='wrong')).status_code, 403)
        self.assertEqual(update(data).status_code, 200)
        self.assertEqual(client.get('/api/me').json['Email'], email)
        with closing(self.db()) as db:
            row = db.execute('SELECT Email,notification_verified_email FROM users WHERE LoginId=?', (FIELDS['LoginId'],)).fetchone()
            self.assertEqual(tuple(row), (email, email))
            self.assertIsNone(db.execute('SELECT 1 FROM email_verifications WHERE Email=?', (email,)).fetchone())

    def test_lifecycle_duplicates_and_transaction_failure(self):
        expired = (datetime.now() - timedelta(days=370)).strftime('%Y-%m-%d %H:%M:%S')
        with closing(self.db()) as db, db:
            for login, deactivated, deleted, since in [
                ('suspended','Y','N',None), ('withdrawn','Y','N',expired), ('soft-deleted','N','Y',None),
            ]:
                db.execute('INSERT INTO users(LoginId,Password,Role,IsDeactivated,IsDeleted,DeactivatedAt) VALUES (?,?,?,?,?,?)',
                           (login,'original','user',deactivated,deleted,since))
        def create(login):
            return self.admin.post(CREATE, json=dict(FIELDS, LoginId=login), headers=self.headers)
        for login in ('suspended', 'withdrawn', 'soft-deleted'):
            self.assertEqual(create(login).status_code, 409)
        with closing(self.db()) as db:
            self.assertEqual(db.execute("SELECT Password FROM users WHERE LoginId='withdrawn'").fetchone()[0], 'original')
        self.assertEqual(self.admin.get('/api/users').status_code, 200)  # Triggers the existing expiry workflow.
        with closing(self.db()) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM users WHERE LoginId='withdrawn'").fetchone())
        self.assertEqual(create('withdrawn').status_code, 201)
        self.assertEqual(self.admin.post('/api/users/delete_selected', json={'user_ids':[41202]}, headers=self.headers).status_code, 200)
        new_account = create('access-user-41202')
        self.assertEqual(new_account.status_code, 201)
        self.assertNotEqual(new_account.json['UserId'], 41202)
        for table, failure in [('audit_logs', "RAISE(ABORT,'private failure detail')"),
                               ('audit_logs', 'RAISE(IGNORE)'), ('users', 'RAISE(IGNORE)')]:
            with self.subTest(table=table, failure=failure):
                with closing(self.db()) as db:
                    db.execute(f'CREATE TRIGGER reject_insert BEFORE INSERT ON {table} BEGIN SELECT {failure}; END')
                failed = create('retryable')
                self.assertEqual(failed.status_code, 500)
                self.assertNotIn('private failure detail', failed.get_data(as_text=True))
                with closing(self.db()) as db:
                    self.assertIsNone(db.execute("SELECT 1 FROM users WHERE LoginId='retryable'").fetchone())
                    self.assertIsNone(db.execute("SELECT 1 FROM audit_logs WHERE Action=? AND json_extract(NewValue,'$.LoginId')=?", (ACTION,'retryable')).fetchone())
                    db.execute('DROP TRIGGER reject_insert')
        self.assertEqual(create('retryable').status_code, 201)
        self.module.access_log_queue.join()
        with closing(self.db()) as db:
            failures = db.execute('SELECT RequestPayload,ResponsePayload FROM access_logs WHERE RequestPath=? AND StatusCode=500', (CREATE,))
            self.assertEqual([tuple(row) for row in failures], [(None, None)] * 3)

    def test_public_signup_requires_verified_email_and_ignores_requested_role(self):
        with closing(self.db()) as db, db:
            db.execute('DELETE FROM users')
        client = self.anonymous()
        def register(fields):
            return client.post('/register', json=fields, headers=self.csrf(client))
        bootstrap = 'bootstrap@example.test'
        other = 'public@example.test'
        with patch.dict(os.environ, BOOTSTRAP_ADMIN_EMAIL=bootstrap):
            self.assertEqual(register(FIELDS).status_code, 400)
            data = dict(FIELDS, Email=other, Role='admin')
            self.assertEqual(register(data).status_code, 400)
            self.verify_email(client, other)
            self.assertEqual(register(data).status_code, 403)
            self.verify_email(client, bootstrap)
            self.assertEqual(register(dict(FIELDS, LoginId='first-admin', Email=bootstrap)).status_code, 200)
            second = self.anonymous()
            self.verify_email(second, 'second@example.test')
            self.assertEqual(register(dict(data, Email='second@example.test')).status_code, 400)
            self.assertEqual(second.post('/register', json=dict(data, Email='second@example.test'),
                                         headers=self.csrf(second)).status_code, 200)
        with closing(self.db()) as db:
            roles = dict(db.execute('SELECT LoginId,Role FROM users'))
            self.assertEqual(roles, {'first-admin': 'admin', FIELDS['LoginId']: 'user'})


if __name__ == '__main__':
    unittest.main()
