"""Linux fixture app: authentication, atomic deletes, list paths and backup HTTP."""
import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipIf(os.name == 'nt', 'Project policy: app fixtures execute on Linux only')
class ReleaseApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='eqmgmt-release-api-')
        cls.root = Path(cls.temp.name)
        cls.environment = {name: os.environ.get(name) for name in ('DATABASE_PATH', 'DATABASE_OPERATION_ROOT', 'MAINTENANCE_STATE_PATH', 'SECRET_KEY')}
        os.environ.update(DATABASE_PATH=str(cls.root / 'fixture.db'), DATABASE_OPERATION_ROOT=str(cls.root / 'operations'),
                          MAINTENANCE_STATE_PATH=str(cls.root / 'maintenance.json'), SECRET_KEY='isolated-test-secret')
        spec = importlib.util.spec_from_file_location('release_fixture_app', Path(__file__).resolve().parents[1] / 'app.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.module.app.config['TESTING'] = True
        # Stop only this fixture's access logger, not any running service.
        cls.module.ACCESS_LOG_ACCEPTING.clear()
        cls.module.shutdown_event.set()
        cls.module.logger_thread.join(timeout=3)
        with sqlite3.connect(cls.module.DATABASE_PATH) as conn:
            for uid, role in ((10001, 'admin'), (10002, 'user')):
                conn.execute("INSERT INTO users(UserId,LoginId,Password,Role,SessionToken,IsDeactivated,IsDeleted) VALUES(?,?,?,?,?,'N','N')",
                             (uid, f'fixture-{uid}', cls.module.generate_password_hash('fixture-secret'), role, f'token-{uid}'))
            conn.execute("INSERT INTO categories(CategoryId,Name,IsApproved) VALUES(10001,'FixtureCategory',1)")
            conn.execute("INSERT INTO manufacturers(ManufacturerId,Name,IsApproved) VALUES(10001,'FixtureManufacturer',1)")
            conn.execute("INSERT INTO lineup_nodes(id,parent_id,category_id,manufacturer_id,name,depth,status) VALUES(10001,NULL,10001,10001,'Root',1,'APPROVED')")
            conn.execute("INSERT INTO lineup_nodes(id,parent_id,category_id,manufacturer_id,name,depth,status) VALUES(10002,10001,10001,10001,'Leaf',2,'APPROVED')")

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.environment.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
        cls.temp.cleanup()

    def setUp(self):
        self.module.set_maintenance_state('NORMAL', '', '', 'fixture-10001')
        self.client = self.module.app.test_client()
        self.login('admin')
        with sqlite3.connect(self.module.DATABASE_PATH) as conn:
            conn.execute('DELETE FROM equipments')
            conn.execute('DELETE FROM equipment_options')
            conn.execute('DELETE FROM equipments_audit_log')
            conn.execute("INSERT INTO equipment_options(id,lineup_node_id,option_name,specs_json,status) VALUES(10001,10002,'16GB','{}','APPROVED')")
            conn.execute("INSERT INTO equipments(id,option_id,name,user_id,is_public,is_draft) VALUES(10001,10001,'Fixture',10002,0,0)")
        self.headers = {'X-CSRFToken': 'fixture-csrf'}

    def login(self, role):
        uid = 10001 if role == 'admin' else 10002
        with self.client.session_transaction() as session:
            session['user'] = {'UserId': uid, 'LoginId': f'fixture-{uid}', 'Role': role, 'NickName': 'Fixture'}
            session['session_token'] = f'token-{uid}'
            session['csrf_token'] = 'fixture-csrf'

    def test_delete_equipment_retains_history_and_option_then_option_can_be_removed(self):
        self.login('user')
        response = self.client.delete('/api/equipment/10001', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['option_id'], 10001)
        with sqlite3.connect(self.module.DATABASE_PATH) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM equipments').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM equipment_options').fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT action_type FROM equipments_audit_log").fetchone()[0], 'DELETE')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.login('admin')
        snapshot = self.client.get('/api/admin/lineup_nodes').get_json()
        option = next(row for row in snapshot['options'] if row['id'] == 10001)
        self.assertEqual(option['active_equipment_count'], 0)
        self.assertEqual(self.client.delete('/api/equipment_option/10001', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.delete('/api/equipment_option/10001', headers=self.headers).status_code, 404)

    def test_option_auth_csrf_and_draft_reference_contract(self):
        self.assertEqual(self.client.put('/api/equipment_option/10001', json={'option_name': 'x'}).status_code, 403)
        self.login('user')
        self.assertEqual(self.client.put('/api/equipment_option/10001', json={'option_name': 'x'}, headers=self.headers).status_code, 403)
        self.login('admin')
        with sqlite3.connect(self.module.DATABASE_PATH) as conn:
            conn.execute('UPDATE equipments SET is_draft=1')
        self.assertEqual(self.client.delete('/api/equipment_option/10001', headers=self.headers).status_code, 409)

    def test_audit_failure_rolls_back_delete_and_option_edit(self):
        with patch.object(self.module, 'audit_lineup_change', side_effect=sqlite3.OperationalError('fixture-only failure')):
            self.assertEqual(self.client.delete('/api/equipment/10001', headers=self.headers).status_code, 500)
            self.assertEqual(self.client.put('/api/equipment_option/10001', json={'option_name': 'CHANGED'}, headers=self.headers).status_code, 500)
        with sqlite3.connect(self.module.DATABASE_PATH) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM equipments').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM equipments_audit_log').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT option_name FROM equipment_options').fetchone()[0], '16GB')

    def test_full_path_all_three_api_contracts(self):
        self.login('user')
        self.assertEqual(self.client.get('/api/equipment').get_json()[0]['FullModelName'], 'Root / Leaf')
        self.assertEqual(self.client.get('/api/equipments_v2').get_json()['equipments'][0]['FullModelName'], 'Root / Leaf')
        stats = self.client.get('/api/dashboard/stats?category_id=10001&manufacturer_id=10001').get_json()
        self.assertEqual(stats['data']['combined_stats']['equipment_list'][0]['FullModelName'], 'Root / Leaf')

    def test_backup_http_attachment_and_private_temp_cleanup(self):
        self.module.set_maintenance_state('DRAINING', 'fixture', '', 'fixture-10001')
        response = self.client.post('/api/admin/database/backup', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b'SQLite format 3\x00'))
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertIn('no-store', response.headers['Cache-Control'])
        response.close()
        self.assertEqual(list((self.root / 'operations' / 'backups').glob('equipment-backup-*.db')), [])

    def test_backup_failure_error_id_no_internal_details(self):
        self.module.set_maintenance_state('DRAINING', 'fixture', '', 'fixture-10001')
        with patch.object(self.module, 'create_online_backup', side_effect=ValueError('fixture-private-path')):
            with self.assertLogs(self.module.app.logger, level='ERROR') as captured:
                response = self.client.post('/api/admin/database/backup', headers=self.headers)
        self.assertEqual(response.status_code, 500)
        result = response.get_json()
        self.assertEqual(len(result['error_id']), 12)
        self.assertIn(result['error_id'], captured.output[0])
        self.assertNotIn('fixture-private-path', response.get_data(as_text=True))
        self.assertNotIn('fixture-private-path', captured.output[0])


if __name__ == '__main__':
    unittest.main()
