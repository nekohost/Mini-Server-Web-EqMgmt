"""Linux-only Flask fixtures. All DB/files live under fresh private temporary roots."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipIf(os.name != 'posix', 'Linux isolated fixtures only')
class MenuWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='eqmgmt-menu-workflow-')
        cls.root = Path(cls.temp.name)
        cls.environment = patch.dict(os.environ, DATABASE_PATH=str(cls.root / 'fixture.db'),
            DATABASE_OPERATION_ROOT=str(cls.root / 'operations'), MAINTENANCE_STATE_PATH=str(cls.root / 'maintenance.json'),
            EQUIPMENT_ATTACHMENT_ROOT=str(cls.root / 'attachments'), SECRET_KEY='isolated-workflow-secret')
        cls.environment.start()
        spec = importlib.util.spec_from_file_location('menu_workflow_fixture_app', Path(__file__).resolve().parents[1] / 'app.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.module.app.config['TESTING'] = True
        cls.module.ACCESS_LOG_ACCEPTING.clear()
        cls.module.shutdown_event.set()
        cls.module.logger_thread.join(timeout=3)
        with cls.connection() as conn:
            for uid, role in [(41001, 'admin'), (41002, 'user'), (41003, 'user')]:
                conn.execute("INSERT INTO users(UserId,LoginId,Password,Role,SessionToken,IsDeactivated,IsDeleted) VALUES(?,?,?,?,?,'N','N')",
                    (uid, f'workflow-{uid}', cls.module.generate_password_hash('fixture-only-password'), role, f'token-{uid}'))
            for index in range(60):
                uid = [41001, 41002, 41003][index % 3]
                status = ['PENDING', 'APPROVED', 'REJECTED'][(index // 3) % 3]
                conn.execute('''INSERT INTO approval_requests(RequestId,RequesterId,RequestType,RequestDataJSON,Status,RejectReason,CreatedAt,UpdatedAt)
                    VALUES(?,?,?,?,?,?,?,?)''', (42000 + index, uid, 'ADD_CATEGORY', json.dumps({'name': '<img onerror=alert(1)>'}),
                    status, '검증용 반려 사유' if status == 'REJECTED' else None, '2026-09-14 10:00:00', '2026-09-14 11:00:00'))

    @classmethod
    def connection(cls):
        conn = sqlite3.connect(cls.module.DATABASE_PATH); conn.row_factory = sqlite3.Row; return conn

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.client = self.module.app.test_client()
        self.module.set_maintenance_state('NORMAL', '', '', 'fixture')
        with self.connection() as conn:
            conn.execute("UPDATE role_menu_permissions SET IsAllowed=1 WHERE MenuCode='my_approvals'")
        self.login(41002)

    def login(self, uid):
        with self.client.session_transaction() as session:
            session['user'] = {'UserId': uid, 'Role': 'admin' if uid == 41001 else 'user', 'LoginId': f'workflow-{uid}', 'NickName': 'Fixture'}
            session['session_token'] = f'token-{uid}'; session['csrf_token'] = 'fixture-csrf'

    def test_own_history_all_statuses_and_foreign_scope_ignored(self):
        result = self.client.get('/api/my_approvals?RequesterId=41003&user_id=41001&scope=all').get_json()
        self.assertEqual(result['total'], 20)
        self.assertEqual({r['Status'] for r in result['data']}, {'PENDING', 'APPROVED', 'REJECTED'})
        self.assertTrue(all((r['RequestId'] - 42000) % 3 == 1 for r in result['data']))
        self.assertTrue(all('RequesterName' not in r and 'RequesterId' not in r for r in result['data']))

    def test_admin_personal_history_is_not_global_history(self):
        self.login(41001)
        result = self.client.get('/api/my_approvals').get_json()
        self.assertEqual(result['total'], 20)
        self.assertTrue(all((r['RequestId'] - 42000) % 3 == 0 for r in result['data']))
        self.assertEqual(len(self.client.get('/api/approvals').get_json()['data']), 60)

    def test_status_filter_pagination_and_large_page_clamp(self):
        first = self.client.get('/api/my_approvals?per_page=3').get_json()
        second = self.client.get('/api/my_approvals?per_page=3&page=2').get_json()
        self.assertEqual((first['total'], first['pages']), (20, 7))
        self.assertEqual(len(first['data']), 3)
        self.assertTrue(min(r['RequestId'] for r in first['data']) > max(r['RequestId'] for r in second['data']))
        filtered = self.client.get('/api/my_approvals?status=REJECTED').get_json()
        self.assertTrue(filtered['data'])
        self.assertTrue(all(r['Status'] == 'REJECTED' and r['RejectReason'] for r in filtered['data']))
        last = self.client.get('/api/my_approvals?per_page=3&page=999999999999999999999').get_json()
        self.assertEqual(last['page'], last['pages'])

    def test_invalid_filters_are_rejected(self):
        for query in ['status=ALL', 'status=PENDING%27%20OR%201=1', 'page=0', 'page=no', 'per_page=0', 'per_page=101']:
            self.assertEqual(self.client.get('/api/my_approvals?' + query).status_code, 400, query)

    def test_auth_menu_permission_and_no_processing_authority(self):
        self.assertEqual(self.module.app.test_client().get('/api/my_approvals').status_code, 401)
        self.assertEqual(self.client.post('/api/approvals/42001/process', json={'action': 'approve'}, headers={'X-CSRFToken': 'fixture-csrf'}).status_code, 403)
        with self.connection() as conn:
            conn.execute("UPDATE role_menu_permissions SET IsAllowed=0 WHERE Role='user' AND MenuCode='my_approvals'")
        self.assertEqual(self.client.get('/my_approvals').status_code, 403)
        self.assertEqual(self.client.get('/api/my_approvals').status_code, 403)
        self.assertEqual(self.client.get('/api/approvals').status_code, 403)

    def test_portal_and_legacy_link_resolve_to_own_inbox(self):
        codes = [m['MenuCode'] for m in self.client.get('/api/portal/menus').get_json()]
        self.assertIn('my_approvals', codes); self.assertNotIn('admin_center', codes)
        response = self.client.get('/approvals')
        self.assertEqual(response.status_code, 302); self.assertTrue(response.location.endswith('/my_approvals'))
        for route in ['/my_approvals', '/mypage']:
            self.assertEqual(self.client.get(route).status_code, 200)

    def test_role_catalog_preserves_unused_roles_and_role_only_save(self):
        self.login(41001)
        with self.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO role_menu_permissions(Role,MenuCode,IsAllowed,UpdatedAt) VALUES('future-reviewer','my_equipment',0,'fixture')")
            before_admin = conn.execute("SELECT * FROM role_menu_permissions WHERE Role='admin' ORDER BY MenuCode").fetchall()
        catalog = self.client.get('/api/permissions').get_json()
        self.assertIn('future-reviewer', {r['Role'] for r in catalog})
        payload = [{k: r[k] for k in ['Role','MenuCode','IsAllowed']} for r in catalog if r['Role'] == 'user']
        response = self.client.post('/api/permissions', json=payload, headers={'X-CSRFToken':'fixture-csrf'})
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.connection() as conn:
            self.assertEqual(before_admin, conn.execute("SELECT * FROM role_menu_permissions WHERE Role='admin' ORDER BY MenuCode").fetchall())
        self.login(41002)
        self.assertEqual(self.client.get('/api/permissions').status_code, 403)

    def test_migration_is_one_time_and_does_not_reset_explicit_denial(self):
        with self.connection() as conn:
            conn.execute("UPDATE role_menu_permissions SET IsAllowed=0 WHERE Role='user' AND MenuCode='my_approvals'")
            before = conn.execute('SELECT * FROM role_menu_permissions ORDER BY PermissionId').fetchall()
        self.module.migrate_personal_approvals_menu()
        with self.connection() as conn:
            self.assertEqual(before, conn.execute('SELECT * FROM role_menu_permissions ORDER BY PermissionId').fetchall())
            self.assertEqual(conn.execute("SELECT IsAllowed FROM role_menu_permissions WHERE Role='user' AND MenuCode='approvals'").fetchone()[0], 0)
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])


if __name__ == '__main__':
    unittest.main()
