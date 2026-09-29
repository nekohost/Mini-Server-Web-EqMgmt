"""선택 실명과 이메일 기반 복구 회귀. 앱·DB·메일은 Linux 임시 fixture에서만 실행합니다."""
from contextlib import closing
from datetime import datetime, timedelta
import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from utils.roadmap_auth import email_verification_proof, matches_email_verification


class EmailProofTests(unittest.TestCase):
    def test_proof_is_bound_and_bounded_without_exposing_pin_hash(self):
        proof = email_verification_proof('fixture@example.test', 'private-pin-hash', 'fixture-secret', now=1000)
        self.assertNotIn('private-pin-hash', str(proof))
        self.assertTrue(matches_email_verification(proof, 'fixture@example.test', 'private-pin-hash', 'fixture-secret', now=1001))
        for email, challenge, secret, now in (
            ('other@example.test', 'private-pin-hash', 'fixture-secret', 1001),
            ('fixture@example.test', 'new-challenge', 'fixture-secret', 1001),
            ('fixture@example.test', 'private-pin-hash', 'other-secret', 1001),
            ('fixture@example.test', 'private-pin-hash', 'fixture-secret', 1600),
        ):
            self.assertFalse(matches_email_verification(proof, email, challenge, secret, now=now))
        for invalid in (None, [], {}, {'email': 'fixture@example.test', 'expires_at': True},
                        {**proof, 'challenge': '잘못된 증거'}):
            self.assertFalse(matches_email_verification(invalid, 'fixture@example.test', 'private-pin-hash', 'fixture-secret', now=1001))


@unittest.skipIf(os.name != 'posix', 'Actual Flask execution is Linux-only')
class OptionalRealNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='eqmgmt-optional-name-')
        cls.root = Path(cls.temp.name)
        cls.environment = patch.dict(os.environ, DATABASE_PATH=str(cls.root / 'fixture.db'),
            DATABASE_OPERATION_ROOT=str(cls.root / 'operations'), MAINTENANCE_STATE_PATH=str(cls.root / 'maintenance.json'),
            EQUIPMENT_ATTACHMENT_ROOT=str(cls.root / 'attachments'), SECRET_KEY='isolated-optional-name-secret')
        cls.environment.start()
        spec = importlib.util.spec_from_file_location('optional_name_fixture_app', Path(__file__).resolve().parents[1] / 'app.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.module.app.config['TESTING'] = True
        cls.module.ACCESS_LOG_ACCEPTING.clear()
        cls.module.shutdown_event.set()
        cls.module.logger_thread.join(timeout=3)
        cls.mailer = patch.object(cls.module, 'send_email', return_value=(True, 'fixture-only'))
        cls.mailer.start()

    @classmethod
    def tearDownClass(cls):
        cls.mailer.stop()
        cls.environment.stop()
        cls.temp.cleanup()

    def connection(self):
        connection = sqlite3.connect(self.module.DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        return connection

    def setUp(self):
        self.module.set_maintenance_state('NORMAL', '', '', 'fixture')
        with closing(self.connection()) as connection:
            for table in ('audit_logs', 'user_settings', 'password_resets', 'users', 'email_verifications', 'auth_rate_buckets'):
                connection.execute('DELETE FROM ' + table)
            connection.execute("INSERT INTO users(UserId,LoginId,Name,NickName,Password,Role,SessionToken,Email,IsDeleted,IsDeactivated) VALUES(90001,'existing','기존 이름','별명',?,'user','old-session','existing@example.test','N','N')",
                               (self.module.generate_password_hash(' GoodPass1! '),))
            connection.commit()
        self.client = self.new_client()
        self.headers = {'X-CSRFToken': 'fixture-csrf'}

    def new_client(self):
        client = self.module.app.test_client()
        with client.session_transaction() as session:
            session['csrf_token'] = 'fixture-csrf'
        return client

    def verify(self, email='new@example.test', client=None):
        client = client or self.client
        expires = (datetime.now() + timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')
        with closing(self.connection()) as connection:
            connection.execute('INSERT OR REPLACE INTO email_verifications(Email,PinCodeHash,ExpiresAt,IsVerified) VALUES(?,?,?,0)',
                               (email, self.module.generate_password_hash('123456'), expires))
            connection.commit()
        response = client.post('/api/auth/verify_pin', json={'email': email, 'pin': '123456'}, headers=self.headers)
        self.assertEqual(response.status_code, 200)

    def register(self, **fields):
        data = {'LoginId': 'new-user', 'NickName': '새 별명', 'Password': 'GoodPass1!', 'Email': 'new@example.test'}
        data.update(fields)
        return self.client.post('/register', json=data, headers=self.headers)

    def login_fixture(self):
        with self.client.session_transaction() as session:
            session['user'] = {'UserId': 90001, 'LoginId': 'existing', 'Role': 'user', 'Name': '기존 이름', 'NickName': '별명'}
            session['session_token'] = 'old-session'

    def deleted_fixture(self, name=None, suspended=False):
        old = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d %H:%M:%S')
        with closing(self.connection()) as connection:
            connection.execute("UPDATE users SET Name=?, IsDeleted='Y', DeletedAt=?, IsDeactivated=?, DeactivatedAt=? WHERE UserId=90001",
                               (name, old, 'Y' if suspended else 'N', None))
            connection.execute("INSERT INTO password_resets(TokenHash,UserId,ExpiresAt,IsUsed) VALUES('old-reset',90001,?,0)", (old,))
            connection.commit()

    def test_registration_accepts_omitted_blank_null_whitespace_and_named_values(self):
        for index, fields in enumerate(({}, {'Name': ''}, {'Name': None}, {'Name': '  '}, {'Name': '  홍 길동  '})):
            with self.subTest(fields=fields):
                email = f'new{index}@example.test'
                self.verify(email)
                result = self.register(LoginId=f'new-{index}', Email=email, **fields)
                self.assertEqual(result.status_code, 200, result.get_json())
                with closing(self.connection()) as connection:
                    row = connection.execute('SELECT Name,NickName,Role,notification_verified_email FROM users WHERE LoginId=?', (f'new-{index}',)).fetchone()
                    self.assertEqual(row['Name'], '홍 길동' if index == 4 else '')
                    self.assertEqual(row['NickName'], '새 별명')
                    self.assertEqual(row['Role'], 'user')
                    self.assertEqual(row['notification_verified_email'], email)
                    self.assertIsNone(connection.execute('SELECT 1 FROM email_verifications WHERE Email=?', (email,)).fetchone())
                with self.client.session_transaction() as session:
                    self.assertNotIn('registration_email_proof', session)

    def test_invalid_name_and_required_fields_still_rejected(self):
        for value in (123, True, [], {}, 'a' * 101):
            self.assertEqual(self.register(Name=value).status_code, 400)
        for fields in ({'NickName': ''}, {'LoginId': ''}, {'Password': 'weak'}, {'Email': ''}):
            self.assertEqual(self.register(**fields).status_code, 400)

    def test_verification_cannot_be_borrowed_from_another_session_or_email(self):
        self.verify(client=self.new_client())
        self.assertEqual(self.register().status_code, 400)
        self.verify('other@example.test')
        self.assertEqual(self.register().status_code, 400)

    def test_expired_proof_and_reissued_challenge_are_rejected(self):
        self.verify()
        with self.client.session_transaction() as session:
            proof = dict(session['registration_email_proof'])
            proof['expires_at'] = 1
            session['registration_email_proof'] = proof
        self.assertEqual(self.register().status_code, 400)
        self.verify()
        with closing(self.connection()) as connection:
            connection.execute("UPDATE email_verifications SET PinCodeHash='another-challenge'")
            connection.commit()
        self.assertEqual(self.register().status_code, 400)

    def test_missing_csrf_and_missing_verification_rejected(self):
        self.assertEqual(self.register().status_code, 400)
        self.verify()
        result = self.client.post('/register', json={'LoginId': 'new-user', 'NickName': 'Nick', 'Password': 'GoodPass1!', 'Email': 'new@example.test'})
        self.assertEqual(result.status_code, 403)

    def test_recovery_uses_registered_email_without_name_and_revokes_old_auth(self):
        self.deleted_fixture()
        self.verify('existing@example.test')
        result = self.register(LoginId='existing', Email='existing@example.test')
        self.assertEqual(result.status_code, 200, result.get_json())
        with closing(self.connection()) as connection:
            row = connection.execute('SELECT * FROM users WHERE UserId=90001').fetchone()
            self.assertEqual(row['Name'], '')
            self.assertEqual(row['IsDeleted'], 'N')
            self.assertEqual(row['IsDeactivated'], 'N')
            self.assertEqual(row['Role'], 'user')
            self.assertIsNone(row['SessionToken'])
            self.assertTrue(self.module.check_password_hash(row['Password'], 'GoodPass1!'))
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM password_resets').fetchone()[0], 0)

    def test_name_match_with_different_email_does_not_recover(self):
        self.deleted_fixture(name='동일 이름')
        self.verify()
        self.assertEqual(self.register(LoginId='existing', Name='동일 이름').status_code, 400)
        with closing(self.connection()) as connection:
            self.assertEqual(connection.execute('SELECT IsDeleted FROM users WHERE UserId=90001').fetchone()[0], 'Y')

    def test_admin_suspension_cannot_be_recovered(self):
        self.deleted_fixture(suspended=True)
        self.verify('existing@example.test')
        self.assertEqual(self.register(LoginId='existing', Email='existing@example.test').status_code, 400)

    def test_failed_insert_preserves_verification_and_existing_data(self):
        self.verify()
        with closing(self.connection()) as connection:
            connection.execute("CREATE TRIGGER fail_registration BEFORE INSERT ON users BEGIN SELECT RAISE(ABORT, 'fixture-failure'); END")
            connection.commit()
        try:
            self.assertEqual(self.register().status_code, 400)
        finally:
            with closing(self.connection()) as connection:
                connection.execute('DROP TRIGGER fail_registration')
                self.assertIsNotNone(connection.execute("SELECT 1 FROM email_verifications WHERE Email='new@example.test'").fetchone())
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
                connection.commit()
        self.assertEqual(self.register().status_code, 200)

    def test_profile_name_can_be_cleared_and_omission_preserves_value(self):
        self.login_fixture()
        data = {'login_id': 'existing', 'nickname': '수정 별명', 'current_password': ' GoodPass1! '}
        self.assertEqual(self.client.post('/api/users/update_profile', json=data, headers=self.headers).status_code, 200)
        with closing(self.connection()) as connection:
            self.assertEqual(connection.execute('SELECT Name FROM users WHERE UserId=90001').fetchone()[0], '기존 이름')
            connection.execute('UPDATE users SET Name=NULL WHERE UserId=90001')
            connection.commit()
        self.assertEqual(self.client.post('/api/users/update_profile', json=data, headers=self.headers).status_code, 200)
        with closing(self.connection()) as connection:
            self.assertIsNone(connection.execute('SELECT Name FROM users WHERE UserId=90001').fetchone()[0])
        for name in (None, '', '  ', '새 실명'):
            result = self.client.post('/api/users/update_profile', json={**data, 'name': name}, headers=self.headers)
            self.assertEqual(result.status_code, 200, result.get_json())
            with closing(self.connection()) as connection:
                self.assertEqual(connection.execute('SELECT Name FROM users WHERE UserId=90001').fetchone()[0], (name or '').strip())

    def test_profile_still_requires_password_csrf_and_valid_types(self):
        self.login_fixture()
        data = {'login_id': 'existing', 'nickname': '별명', 'name': '', 'current_password': 'wrong'}
        self.assertEqual(self.client.post('/api/users/update_profile', json=data, headers=self.headers).status_code, 400)
        data['current_password'] = ' GoodPass1! '
        self.assertEqual(self.client.post('/api/users/update_profile', json=data).status_code, 403)
        self.assertEqual(self.client.post('/api/users/update_profile', json={**data, 'name': []}, headers=self.headers).status_code, 400)

    def test_templates_render_optional_fields_and_safe_empty_profile(self):
        signup = self.client.get('/register').get_data(as_text=True)
        self.assertIn('실명 (이름, 선택)', signup)
        self.assertNotRegex(signup, r'<input[^>]*id="Name"[^>]*\brequired\b')
        self.login_fixture()
        with self.client.session_transaction() as session:
            session['user'] = {**session['user'], 'Name': None}
        page = self.client.get('/mypage').get_data(as_text=True)
        self.assertIn('미등록 / 별명', page)
        self.assertNotRegex(page, r'<input[^>]*id="editName"[^>]*\brequired\b')
        self.assertIn('name: ""', page)


if __name__ == '__main__':
    unittest.main()
