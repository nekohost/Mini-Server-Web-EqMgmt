"""[MINI-COMMENT: STRATA.RETIREMENT.TESTS]
[EN rev.1]
[Role] Exercises real login/menu boundaries and retired URLs on synthetic Linux-only fixtures.
[Dependencies] In-memory candidate app/assets/modules, Flask test clients and temporary SQLite.
[Impact] Never imports production app.py, opens a real database or calls a model endpoint.
"""
import ast
from functools import wraps
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from jinja2 import DictLoader

import assistant_fixture_tests as assistant_fixture
import utils.ai_assistant as assistant
import utils.strata_integration as retired


@unittest.skipUnless(os.name == 'posix', 'Behavior tests require an isolated Linux fixture')
class StrataRetirementTests(unittest.TestCase):
    """[Role] Reuses actual auth and menu functions while replacing only data/templates with inert fixtures."""

    def setUp(self):
        """[Role] Builds source-derived handlers on a fresh temporary metadata database."""
        self.temporary = tempfile.TemporaryDirectory(prefix='eq-retirement-')
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / 'fixture.db'
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE users(UserId INTEGER PRIMARY KEY, Role TEXT, SessionToken TEXT,
                    IsDeleted TEXT, IsDeactivated TEXT, DeactivatedAt TEXT);
                CREATE TABLE menus(MenuId INTEGER PRIMARY KEY, MenuCode TEXT UNIQUE, MenuName TEXT, Url TEXT,
                    Description TEXT, ParentMenuCode TEXT, SortOrder INTEGER, CreatedAt TEXT, UpdatedAt TEXT);
                CREATE TABLE role_menu_permissions(Role TEXT,MenuCode TEXT,IsAllowed INTEGER,
                    UpdatedAt TEXT,UNIQUE(Role,MenuCode));
                INSERT INTO users VALUES(1,'admin','admin-token','N','N',NULL);
                INSERT INTO users VALUES(2,'user','user-token','N','N',NULL);
                INSERT INTO menus VALUES(1,'existing','Existing','/portal','keep',NULL,1,'old','old');
                INSERT INTO menus VALUES(2,'strata','Old','/ai','legacy preserved',NULL,50,'old','old');
                INSERT INTO menus VALUES(3,'admin_center','Admin','/admin_center','hub',NULL,4,'old','old');
                INSERT INTO menus VALUES(4,'equipment_ai_settings','AI settings','/admin/ai/providers','keep','admin_center',52,'old','old');
                INSERT INTO menus VALUES(5,'equipment_ai','AI','/assistant','keep',NULL,51,'old','old');
                INSERT INTO role_menu_permissions VALUES('user','strata',1,'old');
                INSERT INTO role_menu_permissions VALUES('user','equipment_ai_settings',1,'old');
                INSERT INTO role_menu_permissions VALUES('user','equipment_ai',1,'old');
                INSERT INTO role_menu_permissions VALUES('admin','equipment_ai_settings',1,'old');
            """)
        self.app = Flask('strata_retirement_fixture', static_folder=None)
        self.app.config.update(TESTING=True, SECRET_KEY='synthetic-retirement-fixture-only',
                               STRATA_ENABLED=True, USER_AI_ENABLED=True)
        templates = {key.removeprefix('templates/'): value for key, value in CANDIDATE_ASSETS.items() if key.startswith('templates/')}
        templates['miniserver_frame.html'] = '{% block content %}{% endblock %}'
        templates['admin_center.html'] = '<p>Administrative hub</p>'
        self.app.jinja_loader = DictLoader(templates)
        self.app.add_url_rule('/login', 'login_page', lambda: 'login')
        self.app.add_url_rule('/deactivated_notice', 'deactivated_notice_page', lambda: 'inactive')
        namespace = dict(app=self.app, wraps=wraps, session=session, request=request, jsonify=jsonify,
                         redirect=redirect, url_for=url_for, render_template=render_template,
                         get_db_connection=self.connect, visible_portal_menus=retired.visible_portal_menus,
                         visible_assistant_menus=assistant.visible_assistant_menus)
        source = ast.parse(SOURCE_APP)
        functions = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in
                     ('login_required', 'check_menu_permission', 'get_portal_menus', 'get_children_menus', 'admin_center_page')]
        self.assertEqual(len(functions), 5)
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<candidate-auth-menus>', 'exec'), namespace)
        self.connect_calls = 0
        retired.install_strata(self.app, self.connect, namespace['login_required'], namespace['check_menu_permission'])
        self.assertEqual(self.connect_calls, 0, 'Retirement must not seed or read DB metadata')
        self.client = self.app.test_client()

    def connect(self):
        """[Role] Opens only the current test's temporary SQLite file."""
        self.connect_calls = getattr(self, 'connect_calls', 0) + 1
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        self.addCleanup(db.close)
        return db

    def login(self, role='admin', token=None):
        """[Role] Installs a synthetic cookie checked against the fixture's current users table."""
        with self.client.session_transaction() as current:
            current['user'] = {'UserId': 1 if role == 'admin' else 2, 'Role': role, 'NickName': 'Fixture'}
            current['session_token'] = token or role + '-token'

    def test_notices_require_live_login_and_never_embed_old_ui(self):
        self.assertEqual(self.client.get('/ai').status_code, 302)
        self.login()
        for path in ('/ai', '/ai/console'):
            response = self.client.get(path)
            body = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn('href="/assistant"', body)
            for forbidden in ('<iframe', 'strata_page.js', 'strata_bridge.js', 'vendor/strata', 'admin-token'):
                self.assertNotIn(forbidden, body)
            self.assertIn('no-store', response.headers['Cache-Control'])

    def test_normal_user_gets_authenticated_replacement_notice(self):
        self.login('user')
        self.assertEqual(self.client.get('/ai/console').status_code, 200)

    def test_stale_deleted_and_deactivated_login_cannot_open_notice(self):
        self.login(token='expired')
        self.assertEqual(self.client.get('/ai').status_code, 302)
        self.login()
        with self.connect() as db:
            db.execute("UPDATE users SET IsDeleted='Y' WHERE UserId=1")
        self.assertEqual(self.client.get('/ai').status_code, 302)
        with self.connect() as db:
            db.execute("UPDATE users SET IsDeleted='N',IsDeactivated='Y' WHERE UserId=1")
        self.login()
        self.assertEqual(self.client.get('/ai').status_code, 302)

    def test_every_old_proxy_api_auth_method_is_gone_even_with_enabled_flag(self):
        self.login()
        headers = {'X-Strata-Original-Method': 'POST', 'X-Strata-Original-URI': '/strata/v1/chat/completions',
                   'Origin': 'https://fixture.example', 'X-CSRFToken': 'anything'}
        for enabled in (True, False):
            self.app.config['STRATA_ENABLED'] = enabled
            for path in ('/strata', '/strata/', '/strata/health', '/strata/v1/models',
                         '/strata/v1/chat/completions', '/strata/unload', '/strata/%2e%2e/config',
                         '/api/strata/status', '/api/strata/access', '/api/strata/unknown', '/_eqmgmt_strata_auth'):
                for method in ('GET', 'POST', 'OPTIONS', 'DELETE'):
                    with self.subTest(path=path, method=method, enabled=enabled):
                        self.assertIn(self.client.open(path, method=method, headers=headers).status_code, (404, 410))

    def test_proxy_anonymous_is_terminal_and_has_no_secret_headers(self):
        response = self.client.get('/api/strata/access')
        self.assertEqual(response.status_code, 410)
        self.assertNotIn('Authorization', response.headers)
        self.assertNotIn('X-Strata-Authorization', response.headers)
        self.assertFalse(retired.request_allowed('POST', '/strata/v1/chat/completions'))

    def test_static_tombstones_cover_bridge_page_css_and_vendor(self):
        for path in ('/static/js/strata_page.js', '/static/js/strata_bridge.js', '/static/css/strata.css',
                     '/static/vendor/strata/app.js', '/static/vendor/strata/fonts/outfit.woff2'):
            self.assertEqual(self.client.get(path).status_code, 410)
        self.assertEqual(self.client.get('/static/js/equipment_ai.js').status_code, 404)

    def test_no_network_client_or_legacy_flag_can_reenable_health(self):
        with patch('socket.create_connection', side_effect=AssertionError('Network forbidden')):
            self.assertEqual(self.client.get('/api/strata/status').status_code, 410)
            with self.assertRaises(RuntimeError):
                retired.upstream_health('http://127.0.0.1:8080')

    def test_legacy_menu_grants_and_other_rows_are_preserved_but_never_listed(self):
        retired.register_menu(lambda: self.fail('Retired seeder must never open the DB'))
        self.login()
        rows = self.client.get('/api/portal/menus').get_json()
        self.assertNotIn('strata', [row['MenuCode'] for row in rows])
        self.assertIn('equipment_ai', [row['MenuCode'] for row in rows])
        self.assertNotIn('equipment_ai_settings', [row['MenuCode'] for row in rows])
        with self.connect() as db:
            self.assertEqual(db.execute("SELECT Description FROM menus WHERE MenuCode='strata'").fetchone()[0], 'legacy preserved')
            self.assertEqual(db.execute("SELECT IsAllowed FROM role_menu_permissions WHERE Role='user' AND MenuCode='strata'").fetchone()[0], 1)

    def test_direct_children_api_checks_parent_and_hides_admin_only_child(self):
        self.login('user')
        self.assertEqual(self.client.get('/api/menus/children/admin_center').status_code, 403)
        with self.connect() as db:
            db.execute("INSERT INTO role_menu_permissions VALUES('user','admin_center',1,'fixture')")
        response = self.client.get('/api/menus/children/admin_center')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_admin_hub_lists_setting_and_disabled_assistant_hides_it(self):
        self.login()
        response = self.client.get('/api/menus/children/admin_center')
        self.assertIn('equipment_ai_settings', [row['MenuCode'] for row in response.get_json()])
        self.assertEqual(self.client.get('/admin_center').status_code, 200)
        self.app.config['USER_AI_ENABLED'] = False
        self.assertEqual(self.client.get('/api/menus/children/admin_center').get_json(), [])


@unittest.skipUnless(os.name == 'posix', 'Behavior tests require an isolated Linux fixture')
class AssistantAdminMenuMigrationTests(unittest.TestCase):
    """[Role] Checks real assistant startup migration/grants without inheriting the full unrelated fixture suite."""

    def setUp(self):
        """[Role] Reuses a source-derived isolated assistant fixture as a contained dependency."""
        self.fixture = assistant_fixture.AssistantTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def reinstall(self):
        """[Role] Runs the real startup metadata transaction in a fresh Flask instance against only temporary DBs."""
        app = Flask('assistant_menu_reinstall', static_folder=None)
        app.config.update(self.fixture.app.config)
        assistant.install_assistant(app, {'get_db_connection': self.fixture.connect,
            'login_required': lambda handler: handler, 'get_maintenance_state': lambda: {'state': 'NORMAL'},
            'ROADMAP_ATTACHMENT_ROOT': str(self.fixture.root / 'attachments')})
        return app

    def test_new_seed_and_existing_reparent_preserve_order_name_url_and_grants(self):
        with self.fixture.connect() as db:
            self.assertEqual(db.execute("SELECT ParentMenuCode FROM menus WHERE MenuCode='equipment_ai_settings'").fetchone()[0], 'admin_center')
            db.execute("UPDATE menus SET ParentMenuCode=NULL,MenuName='Custom name',SortOrder=777,UpdatedAt='old' WHERE MenuCode='equipment_ai_settings'")
            db.execute("INSERT OR REPLACE INTO role_menu_permissions(Role,MenuCode,IsAllowed,UpdatedAt) VALUES('user','equipment_ai_settings',1,'keep-grant')")
            db.commit()
        self.reinstall()
        with self.fixture.connect() as db:
            first = tuple(db.execute("SELECT MenuName,Url,ParentMenuCode,SortOrder,UpdatedAt FROM menus WHERE MenuCode='equipment_ai_settings'").fetchone())
            grants = [tuple(row) for row in db.execute("SELECT * FROM role_menu_permissions WHERE MenuCode='equipment_ai_settings' ORDER BY Role")]
        self.reinstall()
        with self.fixture.connect() as db:
            second = tuple(db.execute("SELECT MenuName,Url,ParentMenuCode,SortOrder,UpdatedAt FROM menus WHERE MenuCode='equipment_ai_settings'").fetchone())
            self.assertEqual([tuple(row) for row in db.execute("SELECT * FROM role_menu_permissions WHERE MenuCode='equipment_ai_settings' ORDER BY Role")], grants)
        self.assertEqual(first, second)
        self.assertEqual(first[:4], ('Custom name', '/admin/ai/providers', 'admin_center', 777))

    def test_collision_stops_without_overwriting_existing_metadata(self):
        for column, value in (('Url', '/other-admin'), ('ParentMenuCode', 'unrelated_parent')):
            with self.subTest(column=column):
                with self.fixture.connect() as db:
                    db.execute("UPDATE menus SET Url='/admin/ai/providers',ParentMenuCode=NULL WHERE MenuCode='equipment_ai_settings'")
                    db.execute('UPDATE menus SET ' + column + "=? WHERE MenuCode='equipment_ai_settings'", (value,))
                    db.commit()
                with self.assertRaises(ValueError):
                    self.reinstall()
                with self.fixture.connect() as db:
                    self.assertEqual(db.execute('SELECT ' + column + " FROM menus WHERE MenuCode='equipment_ai_settings'").fetchone()[0], value)

    def test_direct_setting_page_and_api_ignore_wrong_general_grant(self):
        with self.fixture.connect() as db:
            db.execute("INSERT OR REPLACE INTO role_menu_permissions(Role,MenuCode,IsAllowed,UpdatedAt) VALUES('user','equipment_ai_settings',1,'fixture')")
            db.commit()
        self.fixture.login(2)
        self.assertEqual(self.fixture.client.get('/admin/ai/providers').status_code, 403)
        self.assertEqual(self.fixture.client.get('/api/admin/ai/providers').status_code, 403)
        self.fixture.login(1)
        self.assertEqual(self.fixture.client.get('/api/admin/ai/providers').status_code, 200)
