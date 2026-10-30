"""Linux-only isolated tests. Reuses the real login/permission functions without importing app.py."""
import ast
from functools import wraps
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask, jsonify, redirect, request, session, url_for
from jinja2 import ChoiceLoader, FileSystemLoader


@unittest.skipUnless(os.name == 'posix', 'Actual behavior checks run on the Linux server only')
class StrataIntegrationTests(unittest.TestCase):
    """[역할] 임시 DB와 실제 인증 함수를 사용하여 중계 권한 경계를 검증합니다.
    [의존성 관계] Linux, Flask test client, 원본 app.py의 인증 AST.
    [변경 시 영향도] 운영 앱을 import하거나 운영 DB·API 키를 읽지 않습니다.
    """
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='eqmgmt-strata-')
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / 'fixture.db'
        self.root = Path(__file__).resolve().parents[1]
        self.project = self.root
        if self.root.name == 'overlay':
            self.project = self.root.parent.parent.parent
        with self.connect() as connection:
            connection.executescript('''
                CREATE TABLE users(UserId INTEGER PRIMARY KEY,Role TEXT,SessionToken TEXT,IsDeleted TEXT,
                    IsDeactivated TEXT,DeactivatedAt TEXT);
                CREATE TABLE menus(MenuCode TEXT UNIQUE,MenuName TEXT,Url TEXT,Description TEXT,
                    ParentMenuCode TEXT,SortOrder INTEGER,CreatedAt TEXT,UpdatedAt TEXT);
                CREATE TABLE role_menu_permissions(Role TEXT,MenuCode TEXT,IsAllowed INTEGER,
                    UpdatedAt TEXT,UNIQUE(Role,MenuCode));
                INSERT INTO users VALUES(1,'admin','admin-token','N','N',NULL);
                INSERT INTO users VALUES(2,'user','user-token','N','N',NULL);
                INSERT INTO menus VALUES('existing','Existing','/portal','keep',NULL,1,'old','old');
            ''')
        self.app = Flask(__name__, static_folder=str(self.root / 'static'))
        self.app.config.update(TESTING=True, SECRET_KEY='isolated-strata-fixture-only', STRATA_ENABLED=True,
                               STRATA_PUBLIC_ORIGIN='https://fixture.example', STRATA_UPSTREAM_URL='http://127.0.0.1:8080')
        self.app.jinja_loader = ChoiceLoader([FileSystemLoader(self.root / 'templates'),
                                             FileSystemLoader(self.project / 'templates')])
        self.app.add_url_rule('/login', 'login_page', lambda: 'login')
        self.app.add_url_rule('/deactivated_notice', 'deactivated_notice_page', lambda: 'inactive')
        source = ast.parse((self.project / 'app.py').read_text(encoding='utf-8-sig'))
        functions = [node for node in source.body if isinstance(node, ast.FunctionDef) and
                     node.name in ('login_required', 'check_menu_permission')]
        self.assertEqual(len(functions), 2)
        namespace = dict(wraps=wraps, session=session, request=request, jsonify=jsonify,
                         redirect=redirect, url_for=url_for, get_db_connection=self.connect)
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'real-auth-fixture', 'exec'), namespace)
        spec = importlib.util.spec_from_file_location('isolated_strata_module', self.root / 'utils/strata_integration.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.install_strata(self.app, self.connect, namespace['login_required'], namespace['check_menu_permission'])
        self.client = self.app.test_client()

    def connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        return connection

    def login(self, role='admin', token=None):
        uid = 1 if role == 'admin' else 2
        with self.client.session_transaction() as current:
            current['user'] = {'UserId': uid, 'Role': role, 'NickName': 'Fixture'}
            current['session_token'] = token or role + '-token'
            current['csrf_token'] = 'a' * 32

    def authorize(self, method='GET', path='/strata/metrics', origin='https://fixture.example', csrf='a' * 32):
        return self.client.get('/api/strata/access', headers={
            'X-Strata-Original-Method': method, 'X-Strata-Original-URI': path,
            'X-Strata-Original-Origin': origin, 'X-CSRFToken': csrf})

    def test_anonymous_api_is_401(self):
        self.assertEqual(self.authorize().status_code, 401)

    def test_page_requires_login(self):
        self.assertEqual(self.client.get('/ai').status_code, 302)

    def test_user_cannot_access_console_or_proxy(self):
        self.login('user')
        self.assertEqual(self.authorize().status_code, 403)
        self.assertEqual(self.client.get('/ai/console').status_code, 403)

    def test_admin_read_allowed_and_no_key_headers(self):
        self.login()
        response = self.authorize()
        self.assertEqual(response.status_code, 204)
        self.assertNotIn('Authorization', response.headers)
        self.assertNotIn('X-Strata-Authorization', response.headers)

    def test_stale_session_rejected(self):
        self.login(token='expired-token')
        self.assertEqual(self.authorize().status_code, 401)

    def test_role_change_is_effective_without_new_cookie(self):
        self.login()
        with self.connect() as connection:
            connection.execute("UPDATE users SET Role='user' WHERE UserId=1")
        self.assertEqual(self.authorize().status_code, 403)

    def test_deleted_admin_is_rejected(self):
        self.login()
        with self.connect() as connection:
            connection.execute("UPDATE users SET IsDeleted='Y' WHERE UserId=1")
        self.assertEqual(self.authorize().status_code, 401)

    def test_deactivated_admin_is_rejected(self):
        self.login()
        with self.connect() as connection:
            connection.execute("UPDATE users SET IsDeactivated='Y' WHERE UserId=1")
        self.assertEqual(self.authorize().status_code, 403)

    def test_disabled_feature_denies_admin(self):
        self.login()
        self.app.config['STRATA_ENABLED'] = False
        self.assertEqual(self.authorize().status_code, 403)
        self.assertEqual(self.client.get('/ai').status_code, 404)

    def test_write_requires_origin_and_csrf(self):
        self.login()
        for origin, token in [('https://evil.example', 'a' * 32), ('', 'a' * 32),
                              ('https://fixture.example', ''), ('https://fixture.example', 'wrong')]:
            with self.subTest(origin=origin, token=token):
                self.assertEqual(self.authorize('POST', '/strata/config', origin, token).status_code, 403)
        self.assertEqual(self.authorize('POST', '/strata/config').status_code, 204)

    def test_non_ascii_csrf_fails_without_500(self):
        self.login()
        self.assertEqual(self.authorize('POST', '/strata/config', csrf='é').status_code, 403)

    def test_path_traversal_and_unknown_control_paths_rejected(self):
        self.login()
        for path in ['/strata/%2e%2e/config', '/strata/../config', '/strata//config',
                     '/strata/unload', '/strata/slots/0', '/other/metrics', '/strata/http://evil.example']:
            with self.subTest(path=path):
                self.assertEqual(self.authorize('POST', path).status_code, 403)

    def test_known_path_wrong_method_rejected(self):
        self.login()
        self.assertEqual(self.authorize('DELETE', '/strata/config').status_code, 403)
        self.assertEqual(self.authorize('POST', '/strata/metrics').status_code, 403)

    def test_query_and_expected_fonts_are_allowed(self):
        self.login()
        self.assertEqual(self.authorize(path='/strata/metrics?requests=all').status_code, 204)
        self.assertEqual(self.authorize(path='/strata/fonts/outfit-latin-wght.woff2').status_code, 204)

    def test_registration_is_idempotent_and_preserves_existing(self):
        self.module.register_menu(self.connect)
        with self.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM menus WHERE MenuCode='strata'").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT Description FROM menus WHERE MenuCode='existing'").fetchone()[0], 'keep')

    def test_conflicting_menu_is_not_overwritten(self):
        with self.connect() as connection:
            connection.execute("UPDATE menus SET Url='/other' WHERE MenuCode='strata'")
        with self.assertRaises(ValueError):
            self.module.register_menu(self.connect)
        with self.connect() as connection:
            self.assertEqual(connection.execute("SELECT Url FROM menus WHERE MenuCode='strata'").fetchone()[0], '/other')

    def test_general_grant_does_not_show_admin_menu(self):
        rows = [{'MenuCode':'existing'}, {'MenuCode':'strata'}]
        self.assertEqual(self.module.visible_portal_menus(rows, 'user', self.app.config), [{'MenuCode':'existing'}])
        self.app.config['STRATA_ENABLED'] = False
        self.assertEqual(self.module.visible_portal_menus(rows, 'admin', self.app.config), [{'MenuCode':'existing'}])

    def test_console_has_csrf_namespace_no_raw_login_token(self):
        self.login()
        response = self.client.get('/ai/console')
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('eqmgmt-strata-namespace', text)
        self.assertNotIn('admin-token', text)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(response.headers['X-Frame-Options'], 'SAMEORIGIN')

    def test_health_success_and_lazy_model_state(self):
        self.login()
        data = {'service':'strata','status':'ok','api_key':True,'loaded':False}
        with patch.object(self.module.requests, 'Session') as constructor:
            response = constructor.return_value.__enter__.return_value.get.return_value.__enter__.return_value
            response.status_code = 200
            response.iter_content.return_value = [json.dumps(data).encode()]
            result = self.client.get('/api/strata/status')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json['connected'])
        self.assertEqual(result.json['state'], 'idle')

    def test_health_failure_is_bounded_and_does_not_leak_address(self):
        self.login()
        with patch.object(self.module.requests, 'Session', side_effect=self.module.requests.ConnectionError('private-address')):
            response = self.client.get('/api/strata/status')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-address', response.get_data(as_text=True))

    def test_no_health_request_for_general_user(self):
        self.login('user')
        with patch.object(self.module.requests, 'Session') as constructor:
            self.assertEqual(self.client.get('/api/strata/status').status_code, 403)
            constructor.assert_not_called()

    def test_private_key_include_has_owner_only_permissions(self):
        spec = importlib.util.spec_from_file_location('isolated_strata_key_tool', self.root / 'tools/write_strata_nginx_key.py')
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        output = Path(self.temporary.name) / 'private' / 'upstream.conf'
        helper.write_key_include(output, 'fixture-only-not-a-real-key')
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertIn('Authorization "Bearer fixture-only-not-a-real-key"', output.read_text())
        with self.assertRaises(FileExistsError):
            helper.write_key_include(output, 'other-fixture-key')

    def test_private_key_include_rejects_newline_and_relative_target(self):
        spec = importlib.util.spec_from_file_location('isolated_strata_key_tool', self.root / 'tools/write_strata_nginx_key.py')
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        with self.assertRaises(ValueError):
            helper.write_key_include(Path(self.temporary.name) / 'bad.conf', 'bad\nkey')
        with self.assertRaises(ValueError):
            helper.write_key_include('relative.conf', 'fixture-only-key')


if __name__ == '__main__':
    unittest.main()
