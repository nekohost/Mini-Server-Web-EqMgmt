"""Linux 승격 후 실행할 격리 회귀시험. Windows/운영 DB/실제 메일을 사용하지 않습니다."""
from contextlib import closing
from datetime import date
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from utils.database_contract import connect_database, assert_contract_version, migrate_contract, assert_integrity, rollback_official_models
from utils import roadmap_equipment as equipment, roadmap_files as files, roadmap_auth as auth
from utils.roadmap_notifications import run_notifications
from utils.roadmap_validation import InputError, equipment_fields, password, day, integer
from roadmap_fixture_history import make_v2_fixture


@unittest.skipIf(os.name != 'posix', 'Linux isolated fixtures only')
class RoadmapBatchTests(unittest.TestCase):
    """[역할] 8개 기능과 교차 시나리오. [의존성 관계] fixture app/표준 unittest. [변경 시 영향도] 운영 파일 접근 없음."""
    @classmethod
    def setUpClass(cls):
        """[역할] 모든 경로가 전용 임시 디렉터리인 앱. [의존성 관계] env patch. [변경 시 영향도] 실제 서버와 격리."""
        cls.temp = tempfile.TemporaryDirectory(prefix='roadmap-test-')
        cls.root = Path(cls.temp.name)
        cls.environment = patch.dict(os.environ, DATABASE_PATH=str(cls.root / 'fixture.db'), DATABASE_OPERATION_ROOT=str(cls.root / 'operations'),
            MAINTENANCE_STATE_PATH=str(cls.root / 'maintenance.json'), EQUIPMENT_ATTACHMENT_ROOT=str(cls.root / 'attachments'), SECRET_KEY='isolated-roadmap-test-secret')
        cls.environment.start()
        spec = importlib.util.spec_from_file_location('roadmap_fixture_app', Path(__file__).resolve().parents[1] / 'app.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.module.app.config['TESTING'] = True
        cls.module.ACCESS_LOG_ACCEPTING.clear()
        cls.module.shutdown_event.set()
        cls.module.logger_thread.join(timeout=3)
        with closing(connect_database(cls.module.DATABASE_PATH)) as connection:
            for user_id, role in ((20001, 'admin'), (20002, 'user'), (20003, 'user')):
                connection.execute("INSERT INTO users(UserId,LoginId,Password,Role,SessionToken,Email,notification_verified_email,IsDeleted,IsDeactivated) VALUES(?,?,?,?,?,?,?,'N','N')",
                    (user_id, 'fixture-' + str(user_id), cls.module.generate_password_hash('GoodPass1!'), role, f'token-{user_id}', f'user{user_id}@example.test', f'user{user_id}@example.test'))
            connection.execute("INSERT INTO categories(CategoryId,Name,IsApproved) VALUES(20001,'FixtureCategory',1)")
            connection.execute("INSERT INTO manufacturers(ManufacturerId,Name,IsApproved) VALUES(20001,'FixtureMaker',1)")
            connection.execute("INSERT INTO lineup_nodes(id,category_id,manufacturer_id,name,depth,status) VALUES(20001,20001,20001,'Root',1,'APPROVED')")
            connection.execute("INSERT INTO lineup_nodes(id,parent_id,category_id,manufacturer_id,name,depth,status,official_model_name) VALUES(20002,20001,20001,20001,'Leaf',2,'APPROVED','Complete Model')")
            connection.execute("INSERT INTO equipment_options(id,lineup_node_id,option_name,specs_json,status) VALUES(20001,20002,'Base','{}','APPROVED')")
            connection.commit()

    @classmethod
    def tearDownClass(cls):
        """[역할] fixture 자원만 반환. [의존성 관계] TemporaryDirectory. [변경 시 영향도] 사용자 env 복구."""
        cls.environment.stop()
        cls.temp.cleanup()

    def connection(self):
        """[역할] 같은 fixture/FK 연결. [의존성 관계] API/service tests. [변경 시 영향도] 운영 기본 경로 미사용."""
        connection = connect_database(self.module.DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        return connection

    def setUp(self):
        """[역할] 테스트별 최소 기준선. [의존성 관계] owner/public fixture. [변경 시 영향도] 실패 주입 격리."""
        self.module.set_maintenance_state('NORMAL', '', '', 'fixture-20001')
        with closing(self.connection()) as connection:
            for table in ('equipment_files', 'equipment_imports', 'equipment_notification_log', 'auth_rate_buckets', 'equipments_audit_log', 'equipments', 'user_settings'):
                connection.execute('DELETE FROM ' + table)
            connection.execute("UPDATE users SET SessionToken='token-' || UserId WHERE UserId IN (20001,20002,20003)")  # 로그인 테스트가 갱신한 토큰도 다음 fixture에서 격리합니다.
            connection.execute("UPDATE equipment_options SET status='APPROVED' WHERE id=20001")
            connection.execute("INSERT INTO equipments(id,option_id,name,serial_number,purchase_date,user_id,is_public,is_draft) VALUES(20001,20001,'Fixture','EXISTING','2026-01-01',20002,0,0)")
            connection.commit()
        self.client = self.module.app.test_client()
        self.headers = {'X-CSRFToken': 'fixture-csrf'}
        self.login(20002)

    def login(self, user_id):
        """[역할] 테스트 세션만 설정. [의존성 관계] 기존 login_required. [변경 시 영향도] 권한 비교."""
        with self.client.session_transaction() as session:
            session['user'] = {'UserId': user_id, 'LoginId': f'fixture-{user_id}', 'Role': 'admin' if user_id == 20001 else 'user'}
            session['session_token'] = f'token-{user_id}'
            session['csrf_token'] = 'fixture-csrf'

    def csv_bytes(self, rows):
        """[역할] 공통 헤더 synthetic CSV. [의존성 관계] export. [변경 시 영향도] 실제 사용자 데이터 없음."""
        return equipment.export_csv([{'Name': name, 'OptionId': 20001, 'SerialNumber': serial, 'IsPublic': 0} for name, serial in rows])

    def preview(self, rows):
        """[역할] 실제 multipart 경로. [의존성 관계] CSRF. [변경 시 영향도] 파일 크기 검증."""
        return self.client.post('/api/equipment/csv/preview', data={'file': (io.BytesIO(self.csv_bytes(rows)), 'fixture.csv')}, headers=self.headers)

    def test_validation_boundary_and_password_compatibility(self):
        for value in (True, [], {}, 1.5, '-1', '1 OR 1=1'):
            with self.assertRaises(InputError): integer(value, 'id')
        for value in ('2026-02-29', '2026-13-01', True):
            with self.assertRaises(InputError): day(value, 'day')
        self.assertEqual(day('2024-02-29', 'day'), '2024-02-29')
        self.assertEqual(password('old'), 'old')
        with self.assertRaises(InputError): password('old', new=True)
        with self.assertRaises(InputError): equipment_fields({'Name': [], 'IsPublic': 'false'})
        with self.assertRaises(InputError): equipment_fields({'Name': 'A', 'PurchaseDate': '2026-03-01', 'WarrantyEndDate': '2026-02-28'})
        self.assertEqual(self.client.post('/api/equipment', json=[], headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/equipment', json={'Name': 23}, headers=self.headers).status_code, 400)

    def test_auth_limit_has_retry_header_and_expiry(self):
        for attempt in range(10):
            self.assertEqual(self.client.post('/login', json={'LoginId': 'fixture-20002', 'Password': 'wrong'}).status_code, 400)
        blocked = self.client.post('/login', json={'LoginId': 'fixture-20002', 'Password': 'GoodPass1!'})
        self.assertEqual(blocked.status_code, 429)
        self.assertGreater(int(blocked.headers['Retry-After']), 0)
        self.assertEqual(self.client.post('/login', json={'LoginId': 'fixture-20003', 'Password': 'GoodPass1!'}).status_code, 200)
        with closing(self.connection()) as connection:
            connection.execute('UPDATE auth_rate_buckets SET expires_at=0')
            connection.commit()
        self.assertEqual(self.client.post('/login', json={'LoginId': 'fixture-20002', 'Password': 'GoodPass1!'}).status_code, 200)

    def test_forged_forwarded_ip_does_not_change_untrusted_peer(self):
        class Request:
            environ = {'REMOTE_ADDR': '198.51.100.1', 'werkzeug.proxy_fix.orig': {'REMOTE_ADDR': '198.51.100.1'}}
            remote_addr = '192.0.2.5'
        self.assertEqual(auth.peer_address(Request(), '127.0.0.1/32'), '198.51.100.1')

    def test_status_history_permissions_and_revision_conflict(self):
        payload = {'status': 'LOANED', 'reason': '<script>loan</script>', 'revision': 0}
        self.assertEqual(self.client.post('/api/equipment/20001/status', json=payload).status_code, 403)
        self.assertEqual(self.client.post('/api/equipment/20001/status', json=payload, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post('/api/equipment/20001/status', json=payload, headers=self.headers).status_code, 409)
        detail = self.client.get('/api/equipment/20001/lifecycle').get_json()
        self.assertEqual(detail['equipment']['status'], 'LOANED')
        self.assertEqual(len(detail['history']), 1)
        with closing(self.connection()) as connection:
            connection.execute('UPDATE equipments SET is_public=1 WHERE id=20001'); connection.commit()
        self.login(20003)
        detail = self.client.get('/api/equipment/20001/lifecycle').get_json()
        self.assertEqual(detail['history'], [])
        self.assertFalse(detail['writable'])
        self.assertEqual(self.client.post('/api/equipment/20001/status', json=payload, headers=self.headers).status_code, 404)

    def test_status_failure_is_atomic(self):
        with closing(self.connection()) as connection:
            connection.execute("CREATE TRIGGER roadmap_test_fail BEFORE INSERT ON equipments_audit_log BEGIN SELECT RAISE(ABORT,'fixture'); END"); connection.commit()
        try:
            response = self.client.post('/api/equipment/20001/status', json={'status': 'REPAIR', 'reason': 'fixture', 'revision': 0}, headers=self.headers)
            self.assertEqual(response.status_code, 500)
            with closing(self.connection()) as connection:
                self.assertEqual(connection.execute('SELECT status,revision FROM equipments WHERE id=20001').fetchone()[:], ('ACTIVE', 0))
        finally:
            with closing(self.connection()) as connection:
                connection.execute('DROP TRIGGER roadmap_test_fail'); connection.commit()

    def test_search_full_model_filters_page_and_csv_share_scope(self):
        for keyword in ('Root / Leaf', 'Complete Model', 'FixtureMaker'):
            data = self.client.get('/api/equipment', query_string={'paginated': '1', 'keyword': keyword, 'category_id': 20001, 'status': 'ACTIVE', 'per_page': 1}).get_json()
            self.assertEqual(data['total'], 1)
            self.assertEqual(data['items'][0]['DisplayModelName'], 'Complete Model')
        self.assertEqual(self.client.get('/api/equipment?paginated=1&purchase_from=2026-04-01&purchase_to=2026-01-01').status_code, 400)
        self.assertEqual(self.client.get('/api/equipment?paginated=1&sort=DROP').status_code, 400)
        self.assertIsInstance(self.client.get('/api/equipment').get_json(), list)
        self.login(20003)
        self.assertEqual(self.client.get('/api/equipment?type=public&paginated=1').get_json()['total'], 0)
        self.assertNotIn(b'EXISTING', self.client.get('/api/equipment/csv/export?type=public').data)

    def test_deadline_creation_update_clear_and_skin_preservation(self):
        data = {'Name': 'Added', 'option_id': 20001, 'PurchaseDate': '2026-01-01', 'WarrantyEndDate': '2027-01-01'}
        response = self.client.post('/api/equipments_v2', json=data, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        identifier = response.get_json()['equipment_id']
        detail = self.client.get(f'/api/equipment/{identifier}/lifecycle').get_json()['equipment']
        self.assertEqual(detail['warranty_end_date'], '2027-01-01')
        self.assertEqual(self.client.put(f'/api/equipment/{identifier}', json={'Name': 'Changed', 'WarrantyEndDate': '', 'Revision': 0}, headers=self.headers).status_code, 200)
        self.assertIsNone(self.client.get(f'/api/equipment/{identifier}/lifecycle').get_json()['equipment']['warranty_end_date'])
        self.client.post('/api/user_settings', json={'theme': 'dark'}, headers=self.headers)
        result = self.client.post('/api/user_settings', json={'layout_skin': 'edge', 'deadline_email_opt_in': True}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()['settings']['theme'], 'dark')
        self.assertEqual(self.client.post('/api/user_settings', json={'layout_skin': []}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/user_settings', json={'deadline_email_opt_in': 'true'}, headers=self.headers).status_code, 400)

    def test_csv_preview_errors_atomic_commit_and_replay(self):
        result = self.preview([('A', 'EXISTING'), ('B', 'NEW')]).get_json()
        self.assertIsNone(result['token'])
        self.assertEqual(result['errors'][0]['row'], 2)
        result = self.preview([('A', 'NEW-A'), ('B', 'NEW-B')]).get_json()
        payload = {'token': result['token']}
        commit = self.client.post('/api/equipment/csv/commit', json=payload, headers=self.headers)
        self.assertEqual(commit.status_code, 200)
        self.assertEqual(commit.get_json()['count'], 2)
        self.assertTrue(self.client.post('/api/equipment/csv/commit', json=payload, headers=self.headers).get_json()['replayed'])
        self.assertEqual(self.client.get('/api/equipment?paginated=1').get_json()['total'], 3)
        self.assertTrue(equipment.safe_csv_cell(' =1+1').startswith("'"))

    def test_csv_catalog_changes_block_entire_commit(self):
        token = self.preview([('A', 'NEW-A'), ('B', 'NEW-B')]).get_json()['token']
        with closing(self.connection()) as connection:
            connection.execute("UPDATE equipment_options SET status='PENDING' WHERE id=20001"); connection.commit()
        self.assertEqual(self.client.post('/api/equipment/csv/commit', json={'token': token}, headers=self.headers).status_code, 409)
        self.assertEqual(self.client.get('/api/equipment?paginated=1').get_json()['total'], 1)

    def test_attachment_permissions_tombstone_and_full_backup(self):
        content = b'%PDF-1.4\nfixture-only\n%%EOF'
        response = self.client.post('/api/equipment/20001/files', data={'file': (io.BytesIO(content), 'fixture.pdf', 'application/pdf')}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        file_id = response.get_json()['id']
        self.login(20003)
        self.assertEqual(self.client.get(f'/api/equipment/20001/files/{file_id}/download').status_code, 404)
        self.login(20002)
        response = self.client.get(f'/api/equipment/20001/files/{file_id}/download')
        self.assertEqual(response.data, content)
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff'); response.close()
        self.assertEqual(self.client.delete('/api/equipment/20001', headers=self.headers).status_code, 200)
        with closing(self.connection()) as connection:
            self.assertIsNotNone(connection.execute('SELECT deleted_at FROM equipment_files WHERE id=?', (file_id,)).fetchone()[0])
        self.login(20001); self.module.set_maintenance_state('DRAINING', 'fixture', '', 'fixture-20001')
        response = self.client.post('/api/admin/database/full-backup', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['schema_version'], 3)
            self.assertEqual(len(manifest['files']), 2)
        response.close()

    def test_disguised_upload_and_traversal_rejected(self):
        for name, body, mime in [('x.png', b'<svg/>', 'image/png'), ('../x.pdf', b'%PDF-1.4\nx\n%%EOF', 'application/pdf')]:
            self.assertEqual(self.client.post('/api/equipment/20001/files', data={'file': (io.BytesIO(body), name, mime)}, headers=self.headers).status_code, 400)

    def test_notifications_opt_in_duplicate_and_unknown_retry(self):
        with closing(self.connection()) as connection:
            connection.execute("UPDATE equipments SET warranty_end_date='2026-09-13' WHERE id=20001")
            connection.execute('INSERT INTO user_settings(UserId,PreferencesJSON) VALUES(?,?)', (20002, json.dumps({'deadline_email_opt_in': True})))
            connection.commit()
        send = unittest.mock.Mock(return_value=(False, 'ambiguous'))
        args = {'dry_run': False, 'today': date(2026, 9, 13), 'mail_configured': True}
        self.assertEqual(run_notifications(self.connection, send, **args)['unknown'], 1)
        run_notifications(self.connection, send, **args)
        self.assertEqual(send.call_count, 1)
        send.return_value = (True, 'accepted')
        self.assertEqual(run_notifications(self.connection, send, retry_unknown=True, **args)['sent'], 1)
        run_notifications(self.connection, send, retry_unknown=True, **args)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(equipment.due_badge('2024-02-29', date(2024, 2, 28))['days'], 1)

    def test_schema_v3_down_is_refused_and_backup_identity_preserved(self):
        with closing(self.connection()) as connection:
            self.assertEqual(assert_contract_version(connection), 3)
            assert_integrity(connection)
        with self.assertRaises(ValueError): rollback_official_models(self.module.DATABASE_PATH, self.root / 'down-backups')
        self.assertFalse(migrate_contract(self.module.DATABASE_PATH, self.root / 'up-backups')['applied'])

    def test_v2_upgrade_failure_then_success_keeps_equipment_values(self):
        path = self.root / 'migration-copy.db'
        with closing(self.connection()) as source, closing(connect_database(path)) as target:
            source.backup(target)
            target.execute('UPDATE users SET notification_verified_email=NULL'); target.commit()
        make_v2_fixture(path, self.root)
        with closing(connect_database(path)) as connection:
            before = connection.execute('SELECT id,option_id,name,serial_number,user_id,status FROM equipments').fetchall()
        with patch('utils.roadmap_schema.assert_schema', side_effect=ValueError('fixture-after-alter')):
            with self.assertRaisesRegex(ValueError, 'fixture-after-alter'):
                migrate_contract(path, self.root / 'copy-backups')
        with closing(connect_database(path)) as connection:
            self.assertEqual(assert_contract_version(connection), 2)
        self.assertEqual(migrate_contract(path, self.root / 'copy-backups')['version'], 3)
        with closing(connect_database(path)) as connection:
            self.assertEqual(connection.execute('SELECT id,option_id,name,serial_number,user_id,status FROM equipments').fetchall(), before)

    def test_full_archive_recovery_and_missing_attachment_block(self):
        response = self.client.post('/api/equipment/20001/files', data={'file': (io.BytesIO(b'%PDF-1.4\nfixture\n%%EOF'), 'fixture.pdf', 'application/pdf')}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        db_path = self.root / 'archive-source.db'
        self.module.create_online_backup(db_path)
        archive = self.root / 'archive.zip'
        files.build_archive(db_path, self.root / 'attachments', archive, connect_database)
        recovered = files.prepare_archive(archive, self.root / 'recovered', connect_database, lambda connection: (assert_integrity(connection), assert_contract_version(connection)))
        with closing(connect_database((recovered / 'equipment.db').as_uri() + '?mode=ro', uri=True)) as connection:
            self.assertEqual(len(files.assert_files(connection, recovered / 'attachments')), 1)
            with self.assertRaises(ValueError): files.assert_files(connection, self.root / 'missing-store')

    def test_large_fixture_page_totals_and_query_plan(self):
        with closing(self.connection()) as connection:
            connection.executemany("INSERT INTO equipments(id,option_id,name,user_id,status,purchase_date,is_draft) VALUES(?,20001,?,20002,'REPAIR','2026-05-01',0)",
                ((30000 + number, 'Bulk-' + str(number),) for number in range(2000)))
            connection.commit()
            args = {'status': 'REPAIR', 'purchase_from': '2026-01-01', 'per_page': '100', 'page': '2'}
            user = {'UserId': 20002, 'Role': 'user'}
            cte, where, values, order = equipment.query_contract(args, user)
            plan = connection.execute('EXPLAIN QUERY PLAN ' + cte + 'SELECT e.id' + equipment.FROM_SQL + where + order, values).fetchall()
            self.assertTrue(any('SEARCH e USING' in row[3] for row in plan))
            result = equipment.list_equipment(connection, args, user)
            self.assertEqual(result['total'], 2000)
            self.assertEqual(len(result['items']), 100)
            self.assertEqual(len({item['EquipmentId'] for item in result['items']}), 100)

    def test_json_and_csv_request_size_limits(self):
        self.assertEqual(self.client.post('/api/equipment', json={'Name': 'A', 'Memo': 'x' * 65536}, headers=self.headers).status_code, 413)
        response = self.client.post('/api/equipment/csv/preview', data={'file': (io.BytesIO(b'x' * (equipment.CSV_LIMIT + 1)), 'oversized.csv')}, headers=self.headers)
        self.assertEqual(response.status_code, 413)


if __name__ == '__main__':
    unittest.main()
