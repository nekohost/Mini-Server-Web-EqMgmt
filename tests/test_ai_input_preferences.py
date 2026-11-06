"""[MINI-COMMENT: USER.PREFERENCES.TESTS] [EN rev.2]
[Role] Exercises account-scoped AI input settings on the real guarded settings route and assistant preference merge.
[Dependencies] Source-derived Linux AssistantTests databases, extracted production auth/CSRF decorators and candidate roadmap_routes.
[Impact] No production app import, model request or real database access; rejected settings leave every saved row unchanged and require no migration.
"""
import ast
from functools import wraps
import json
import os
import unittest

from flask import jsonify, redirect, request, session, url_for
from jinja2 import DictLoader

from assistant_fixture_tests import AssistantTests, PROJECT
from utils.roadmap_routes import install_roadmap


@unittest.skipUnless(os.name == 'posix', 'Linux-only isolated preference fixtures')
class InputPreferenceTests(unittest.TestCase):
    """[Role] Covers the existing authenticated persistence boundary without inventing another store."""
    connect = AssistantTests.connect
    login = AssistantTests.login
    conversation = AssistantTests.conversation
    submit = AssistantTests.submit
    claim = AssistantTests.claim
    finish = AssistantTests.finish
    prepare = AssistantTests.prepare

    def setUp(self):
        """[Role] Installs the actual roadmap settings replacement over the established synthetic account fixture."""
        AssistantTests.setUp(self)
        source = ast.parse(globals().get('SOURCE_APP') or (PROJECT / 'app.py').read_text(encoding='utf-8-sig'))
        functions = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in ('login_required', 'csrf_required', 'admin_required')]
        namespace = dict(wraps=wraps, session=session, request=request, jsonify=jsonify, redirect=redirect,
                         url_for=url_for, get_db_connection=self.connect)
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'real-settings-auth-fixture', 'exec'), namespace)
        self.app.add_url_rule('/api/user_settings', 'api_user_settings', lambda: '', methods=['GET', 'POST'])
        install_roadmap(self.app, {'get_db_connection': self.connect, 'login_required': namespace['login_required'],
            'csrf_required': namespace['csrf_required'], 'admin_required': namespace['admin_required'],
            'ROADMAP_ATTACHMENT_ROOT': str(self.root / 'attachments')})

    def saved_rows(self):
        """[Role] Compares exact saved JSON and timestamps across successful reads and rejected mutations."""
        with self.connect() as db:
            return [tuple(row) for row in db.execute('SELECT UserId,PreferencesJSON,UpdatedAt FROM user_settings ORDER BY UserId')]

    def save(self, values, headers=None):
        """[Role] Uses the same JSON endpoint and CSRF header as the existing personal settings UI."""
        return self.client.post('/api/user_settings', json=values, headers=self.headers if headers is None else headers)

    def test_absent_preference_defaults_to_send_without_creating_row(self):
        """[Role] Gives old and new accounts the specified safe default without a read-triggered data migration."""
        response = self.client.get('/api/user_settings')
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['settings']['ai_enter_action'], 'send')
        self.assertEqual(self.saved_rows(), [])

    def test_modes_persist_after_reload_and_fresh_login_without_schema_change(self):
        """[Role] Saves both enum choices while preserving all existing and future JSON fields."""
        with self.connect() as db:
            schema = list(db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name"))
        previous = {'theme': 'dark', 'layout_skin': 'edge', 'deadline_email_opt_in': False,
                    'show_my_equip_first': True, 'future_setting': {'value': 'keep'}}
        self.assertEqual(self.save(previous).status_code, 200)
        response = self.save({'ai_enter_action': 'send'})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['settings'], {**previous, 'ai_enter_action': 'send'})
        self.assertEqual(self.save({'theme': 'light'}).status_code, 200)
        self.client = self.app.test_client()
        self.login(2)
        self.assertEqual(self.client.get('/api/user_settings').get_json()['settings'],
                         {**previous, 'theme': 'light', 'ai_enter_action': 'send'})
        self.assertEqual(self.save({'ai_enter_action': 'newline'}).get_json()['settings']['ai_enter_action'], 'newline')
        with self.connect() as db:
            self.assertEqual(list(db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")), schema)
            self.assertEqual(json.loads(db.execute('SELECT PreferencesJSON FROM user_settings WHERE UserId=2').fetchone()[0])['future_setting'], {'value': 'keep'})

    def test_current_actor_owns_setting_and_other_account_stays_separate(self):
        """[Role] A body or stale session cannot choose another account's persistence row."""
        self.assertEqual(self.save({'ai_enter_action': 'send', 'UserId': 3}).status_code, 200)
        self.assertEqual([row[0] for row in self.saved_rows()], [2])
        self.login(3)
        self.assertEqual(self.client.get('/api/user_settings').get_json()['settings']['ai_enter_action'], 'send')
        self.assertEqual(self.save({'ai_enter_action': 'newline', 'theme': 'system'}).status_code, 200)
        self.login(2)
        self.assertEqual(self.client.get('/api/user_settings').get_json()['settings']['ai_enter_action'], 'send')
        self.assertEqual([row[0] for row in self.saved_rows()], [2, 3])

    def test_invalid_enum_and_nonobject_body_are_rejected_atomically(self):
        """[Role] Rejects null, arrays, booleans, markup and noncanonical strings without partial settings writes."""
        self.assertEqual(self.save({'ai_enter_action': 'send', 'theme': 'dark', 'future': ['preserve']}).status_code, 200)
        before = self.saved_rows()
        for value in (None, True, False, 0, 1, [], {}, '', 'SEND', 'send ', ' newline', '<script>bad()</script>'):
            with self.subTest(value=value):
                response = self.save({'ai_enter_action': value, 'theme': 'light'})
                self.assertEqual(response.status_code, 400, response.get_json())
                self.assertEqual(self.saved_rows(), before)
        for value in ([], ['send'], 'send', 1, True):
            with self.subTest(body=value):
                self.assertEqual(self.save(value).status_code, 400)
                self.assertEqual(self.saved_rows(), before)

    def test_auth_csrf_and_disabled_accounts_cannot_write(self):
        """[Role] Reuses real login/session/CSRF and DB actor checks for this preference."""
        self.assertEqual(self.save({'ai_enter_action': 'send'}, headers={}).status_code, 403)
        self.assertEqual(self.save({'ai_enter_action': 'send'}, headers={'X-CSRFToken': 'wrong'}).status_code, 403)
        self.assertEqual(self.saved_rows(), [])
        with self.client.session_transaction() as current:
            current.clear()
        self.assertEqual(self.save({'ai_enter_action': 'send'}).status_code, 401)
        self.assertEqual(self.client.get('/api/user_settings').status_code, 401)
        self.login(2)
        with self.connect() as db:
            db.execute("UPDATE users SET IsDeactivated='Y' WHERE UserId=2")
        self.assertEqual(self.save({'ai_enter_action': 'send'}).status_code, 403)
        self.assertEqual(self.saved_rows(), [])

    def test_legacy_missing_or_invalid_values_read_safely_without_rewriting_rows(self):
        """[Role] Keeps old JSON rows and rollback compatibility while presenting a fixed safe mode."""
        for raw in ('{"theme":"dark","future":{"keep":true}}', '{"ai_enter_action":null,"theme":"dark"}',
                    '{"ai_enter_action":[],"theme":"dark"}', '[]', 'legacy-invalid-json'):
            with self.subTest(raw=raw):
                with self.connect() as db:
                    db.execute('INSERT INTO user_settings(UserId,PreferencesJSON,UpdatedAt) VALUES(?,?,?) ON CONFLICT(UserId) DO UPDATE SET PreferencesJSON=excluded.PreferencesJSON,UpdatedAt=excluded.UpdatedAt', (2, raw, 'legacy-fixture'))
                before = self.saved_rows()
                response = self.client.get('/api/user_settings')
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertEqual(response.get_json()['settings']['ai_enter_action'], 'send')
                self.assertEqual(self.saved_rows(), before)

    def test_existing_valid_modes_are_preserved_without_read_migration(self):
        """[Role] Keeps both explicit historical modes and unrelated JSON through GET and an unrelated preference save."""
        for action in ('newline', 'send'):
            with self.subTest(action=action):
                raw=json.dumps({'ai_enter_action':action,'future':{'keep':1}},ensure_ascii=False)
                with self.connect() as db:
                    db.execute('INSERT INTO user_settings(UserId,PreferencesJSON,UpdatedAt) VALUES(?,?,?) ON CONFLICT(UserId) DO UPDATE SET PreferencesJSON=excluded.PreferencesJSON,UpdatedAt=excluded.UpdatedAt',(2,raw,'preexisting-choice'))
                before=self.saved_rows()
                self.assertEqual(self.client.get('/api/user_settings').get_json()['settings']['ai_enter_action'],action)
                self.assertEqual(self.saved_rows(),before)
                self.assertEqual(self.save({'theme':'dark'}).get_json()['settings']['ai_enter_action'],action)
                with self.connect() as db:stored=json.loads(db.execute('SELECT PreferencesJSON FROM user_settings WHERE UserId=2').fetchone()[0])
                self.assertEqual(stored,{'ai_enter_action':action,'future':{'keep':1},'theme':'dark'})

    def test_unrelated_save_does_not_materialize_the_default_input_mode(self):
        """[Role] Changes the effective default without silently writing it into an old account's JSON."""
        self.assertEqual(self.save({'theme':'light'}).get_json()['settings']['ai_enter_action'],'send')
        with self.connect() as db:stored=json.loads(db.execute('SELECT PreferencesJSON FROM user_settings WHERE UserId=2').fetchone()[0])
        self.assertEqual(stored,{'theme':'light'})

    def test_assistant_page_bootstraps_current_actor_mode_without_writing_settings(self):
        """[Role] Makes the initial HTML and later API agree before settings fetch can race the first keyboard action."""
        self.app.jinja_loader=DictLoader({'equipment_ai.html':'initial-action={{ assistant_enter_action }}'})
        for raw,expected in ((None,'send'),('{"ai_enter_action":"newline"}','newline'),('{"ai_enter_action":"send"}','send'),('[]','send'),('invalid-json','send')):
            with self.subTest(raw=raw):
                with self.connect() as db:
                    db.execute('DELETE FROM user_settings WHERE UserId=2')
                    if raw is not None:db.execute('INSERT INTO user_settings(UserId,PreferencesJSON,UpdatedAt) VALUES(?,?,?)',(2,raw,'old-initial-setting'))
                    db.execute('INSERT INTO user_settings(UserId,PreferencesJSON,UpdatedAt) VALUES(?,?,?) ON CONFLICT(UserId) DO UPDATE SET PreferencesJSON=excluded.PreferencesJSON',(3,'{"ai_enter_action":"'+('send' if expected=='newline' else 'newline')+'"}','other-account'))
                before=self.saved_rows();response=self.client.get('/assistant')
                self.assertEqual(response.status_code,200,response.get_data(as_text=True))
                self.assertEqual(response.get_data(as_text=True),'initial-action='+expected)
                self.assertEqual(self.client.get('/api/user_settings').get_json()['settings']['ai_enter_action'],expected)
                self.assertEqual(self.saved_rows(),before)

    def test_assistant_theme_confirmation_keeps_input_setting_and_future_keys(self):
        """[Role] An existing AI settings proposal cannot erase the manually saved input mode."""
        self.assertEqual(self.save({'ai_enter_action': 'send', 'future': {'keep': 1}}).status_code, 200)
        proposal = self.prepare('prepare_preferences', {'theme': 'dark'})
        response = self.client.post('/api/ai/proposals/' + proposal['id'] + '/confirm', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        settings = self.client.get('/api/user_settings').get_json()['settings']
        self.assertEqual(settings['ai_enter_action'], 'send')
        self.assertEqual(settings['future'], {'keep': 1})
        self.assertEqual(settings['theme'], 'dark')
