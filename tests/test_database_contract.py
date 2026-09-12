"""Linux-only integration cases for real schema history, atomic master edits and migration recovery."""

import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from utils.database_contract import connect_database, configure_connection, schema_contract, migrate_contract, rollback_contract, INDEXES


@unittest.skipIf(os.name == 'nt', 'Linux execution only')
class DatabaseContractTests(unittest.TestCase):
    """[역할] 격리 DB/API 회귀를 수행합니다. [의존성 관계] Flask test client. [변경 시 영향도] 운영 파일 접근 없음."""
    @classmethod
    def setUpClass(cls):
        """[역할] 임시 앱을 생성합니다. [의존성 관계] 환경 경로. [변경 시 영향도] 독립 logger만 종료합니다."""
        cls.temp = tempfile.TemporaryDirectory(prefix='contract-test-')
        cls.root = Path(cls.temp.name)
        names = ('DATABASE_PATH', 'DATABASE_OPERATION_ROOT', 'MAINTENANCE_STATE_PATH', 'SECRET_KEY')
        cls.environment = {name: os.environ.get(name) for name in names}
        os.environ.update(DATABASE_PATH=str(cls.root / 'test.db'), DATABASE_OPERATION_ROOT=str(cls.root / 'operations'), MAINTENANCE_STATE_PATH=str(cls.root / 'maintenance.json'), SECRET_KEY='isolated-contract-test')
        spec = importlib.util.spec_from_file_location('contract_fixture_app', Path(__file__).resolve().parents[1] / 'app.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.module.app.config['TESTING'] = True
        cls.module.ACCESS_LOG_ACCEPTING.clear()
        cls.module.shutdown_event.set()
        cls.module.logger_thread.join(timeout=3)
        with connect_database(cls.module.DATABASE_PATH) as connection:
            connection.execute("INSERT INTO users(UserId,LoginId,Password,Role,SessionToken,IsDeleted,IsDeactivated) VALUES(90001,'contract-admin',?,'admin','test-token','N','N')", (cls.module.generate_password_hash('fixture-password'),))
        connection.close()

    @classmethod
    def tearDownClass(cls):
        """[역할] 임시 파일을 반환합니다. [의존성 관계] TemporaryDirectory. [변경 시 영향도] 테스트 격리."""
        for key, value in cls.environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.temp.cleanup()

    def setUp(self):
        """[역할] FK를 켠 채 자식부터 fixture를 교체합니다. [의존성 관계] 실제 생성 스키마. [변경 시 영향도] 참조 검증."""
        self.module.set_maintenance_state('NORMAL', '', '', 'contract-admin')
        self.connection = connect_database(self.module.DATABASE_PATH)
        self.connection.row_factory = sqlite3.Row
        self.addCleanup(self.connection.close)
        for table in ('equipments', 'equipment_options', 'lineup_nodes', 'approval_requests', 'equipment', 'categories', 'manufacturers'):
            self.connection.execute(f'DELETE FROM {table}')
        for kind, key in (('categories', 'CategoryId'), ('manufacturers', 'ManufacturerId')):
            self.connection.executemany(f'INSERT INTO {kind}({key},Name,IsApproved) VALUES(?,?,1)', ((90001, 'First'), (90002, 'Second'), (90003, 'Third')))
        self.connection.execute("INSERT INTO lineup_nodes(id,category_id,manufacturer_id,name,depth,status) VALUES(90001,90001,90001,'Root',1,'APPROVED')")
        self.connection.execute("INSERT INTO equipment_options(id,lineup_node_id,option_name,status) VALUES(90001,90001,'Base','APPROVED')")
        self.connection.execute("INSERT INTO equipments(id,option_id,name,user_id) VALUES(90001,90001,'Fixture',90001)")
        self.connection.commit()
        self.client = self.module.app.test_client()
        with self.client.session_transaction() as session:
            session['user'] = {'UserId': 90001, 'LoginId': 'contract-admin', 'Role': 'admin'}
            session['session_token'] = 'test-token'
            session['csrf_token'] = 'test-csrf'
        self.headers = {'X-CSRFToken': 'test-csrf'}

    def test_user_deletion_clears_reset_tokens_and_preserves_equipment(self):
        """[역할] 사용자 삭제 뒤 논리 참조를 검증합니다. [의존성 관계] 사용자 API. [변경 시 영향도] FK 활성화 회귀."""
        self.connection.execute("INSERT INTO users(UserId,LoginId,Password,Role) VALUES(90002,'delete-user','fixture-hash','user')")
        self.connection.execute("INSERT INTO password_resets(TokenHash,UserId,ExpiresAt) VALUES('fixture-token',90002,'2099-01-01')")
        self.connection.execute('UPDATE equipments SET user_id=90002 WHERE id=90001')
        self.connection.commit()
        response = self.client.post('/api/users/delete_selected', json={'user_ids': [90002]}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM password_resets WHERE UserId=90002').fetchone()[0], 0)
        self.assertIsNone(self.connection.execute('SELECT user_id FROM equipments WHERE id=90001').fetchone()[0])
        self.assertEqual(self.connection.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_reject_referenced_node_rolls_back_request_status(self):
        """[역할] 반려 중 참조 충돌을 검증합니다. [의존성 관계] 승인 API. [변경 시 영향도] 대기 상태 보존."""
        self.connection.execute("UPDATE lineup_nodes SET status='PENDING' WHERE id=90001")
        cursor = self.connection.execute("INSERT INTO approval_requests(RequesterId,RequestType,RequestDataJSON,Status) VALUES(90001,'Lineup_Node','{\"node_id\":90001}','PENDING')")
        request_id = cursor.lastrowid
        self.connection.commit()
        response = self.client.post(f'/api/approvals/{request_id}/process', json={'action': 'reject', 'reject_reason': 'fixture'}, headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.connection.execute('SELECT Status FROM approval_requests WHERE RequestId=?', (request_id,)).fetchone()[0], 'PENDING')
        self.assertIsNotNone(self.connection.execute('SELECT 1 FROM lineup_nodes WHERE id=90001').fetchone())

    def test_approval_succeeds_with_same_transaction_audit(self):
        """[역할] 승인 성공 경로도 보존합니다. [의존성 관계] 승인 API. [변경 시 영향도] writer 교착 회귀."""
        self.connection.execute("UPDATE lineup_nodes SET status='PENDING' WHERE id=90001")
        cursor = self.connection.execute("INSERT INTO approval_requests(RequesterId,RequestType,RequestDataJSON,Status) VALUES(90001,'Lineup_Node','{\"node_id\":90001}','PENDING')")
        request_id = cursor.lastrowid
        self.connection.commit()
        response = self.client.post(f'/api/approvals/{request_id}/process', json={'action': 'approve'}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.connection.execute('SELECT Status FROM approval_requests WHERE RequestId=?', (request_id,)).fetchone()[0], 'APPROVED')
        self.assertIsNotNone(self.connection.execute("SELECT 1 FROM audit_logs WHERE TargetId=? AND Action='APPROVE_REQUEST'", (request_id,)).fetchone())

    def test_normal_connection_enforces_foreign_keys(self):
        """[역할] 선언 FK 실제 강제를 확인합니다. [의존성 관계] 앱 연결. [변경 시 영향도] 연결 정책."""
        connection = self.module.get_db_connection()
        try:
            self.assertEqual(connection.execute('PRAGMA foreign_keys').fetchone()[0], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO equipment_options(lineup_node_id,option_name) VALUES(999999,'orphan')")
        finally:
            connection.close()

    def test_configuration_failure_releases_tracked_connection_once(self):
        """[역할] 실패한 연결의 누수와 음수 계수를 방지합니다. [의존성 관계] 초기화 mock. [변경 시 영향도] 복원 drain."""
        before = self.module.ACTIVE_DATABASE_CONNECTIONS
        with patch.object(self.module, 'configure_connection', side_effect=sqlite3.OperationalError('fixture')):
            with self.assertRaises(sqlite3.OperationalError):
                self.module.get_db_connection()
        self.assertEqual(self.module.ACTIVE_DATABASE_CONNECTIONS, before)

    def test_referenced_single_and_bulk_deletion_preserve_all_items(self):
        """[역할] 단건·일괄 삭제 계약을 검증합니다. [의존성 관계] 관리자 API. [변경 시 영향도] 부분 삭제 차단."""
        response = self.client.delete('/api/master/manage/categories/90001', headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['references']['90001']['nodes'], 1)
        response = self.client.post('/api/master/manage/categories/delete_selected', json={'item_ids': [90002, 90001]}, headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM categories').fetchone()[0], 3)
        self.assertEqual(self.client.delete('/api/master/manage/categories/90002', headers=self.headers).status_code, 200)

    def test_pending_request_blocks_delete(self):
        """[역할] 명칭 기반 승인 참조를 보호합니다. [의존성 관계] approval_requests. [변경 시 영향도] 삭제 계약."""
        self.connection.execute("INSERT INTO approval_requests(RequesterId,RequestType,RequestDataJSON,Status) VALUES(90001,'ADD_CATEGORY','{\"name\":\"Second\"}','PENDING')")
        self.connection.commit()
        response = self.client.delete('/api/master/manage/categories/90002', headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['references']['90002']['pending_approvals'], 1)

    def test_merge_preserves_ids_and_rejects_self_and_duplicate_roots(self):
        """[역할] 성공·자기 선택·충돌을 대조합니다. [의존성 관계] merge API. [변경 시 영향도] 계층과 장비 ID."""
        endpoint = '/api/master/manage/categories/90002/merge_from'
        self.assertEqual(self.client.post(endpoint, json={'source_ids': [90002]}, headers=self.headers).status_code, 400)
        self.connection.execute("INSERT INTO lineup_nodes(category_id,manufacturer_id,name,depth) VALUES(90002,90001,'root',1)")
        self.connection.commit()
        self.assertEqual(self.client.post(endpoint, json={'source_ids': [90001]}, headers=self.headers).status_code, 409)
        self.connection.execute("UPDATE lineup_nodes SET name='Different' WHERE category_id=90002")
        self.connection.commit()
        self.assertEqual(self.client.post(endpoint, json={'source_ids': [90001]}, headers=self.headers).status_code, 200)
        self.assertEqual(self.connection.execute('SELECT category_id FROM lineup_nodes WHERE id=90001').fetchone()[0], 90002)
        self.assertEqual(self.connection.execute('SELECT option_id FROM equipments WHERE id=90001').fetchone()[0], 90001)
        self.assertEqual(self.connection.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_merge_pending_and_unapproved_rejected(self):
        """[역할] 승인 우회를 검사합니다. [의존성 관계] master 상태. [변경 시 영향도] merge API."""
        self.connection.execute('UPDATE categories SET IsApproved=0 WHERE CategoryId=90002')
        self.connection.commit()
        response = self.client.post('/api/master/manage/categories/90002/merge_from', json={'source_ids': [90001]}, headers=self.headers)
        self.assertEqual(response.status_code, 409)

    def test_audit_failure_rolls_back_merge(self):
        """[역할] 감사 실패 시 이동을 복구합니다. [의존성 관계] 같은 connection 감사. [변경 시 영향도] 원자성."""
        with patch.object(self.module, 'audit_lineup_change', side_effect=sqlite3.OperationalError('fixture')):
            response = self.client.post('/api/master/manage/categories/90002/merge_from', json={'source_ids': [90001]}, headers=self.headers)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.connection.execute('SELECT category_id FROM lineup_nodes WHERE id=90001').fetchone()[0], 90001)
        self.assertIsNotNone(self.connection.execute('SELECT 1 FROM categories WHERE CategoryId=90001').fetchone())

    def test_invalid_types_and_csrf_are_rejected(self):
        """[역할] 타입·인증 경계를 검증합니다. [의존성 관계] API decorator. [변경 시 영향도] 예상된 400/403."""
        endpoint = '/api/master/manage/categories/delete_selected'
        for values in ([True], [0], ['90002'], [90002, 90002], [2**64]):
            self.assertEqual(self.client.post(endpoint, json={'item_ids': values}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post(endpoint, json={'item_ids': [90002]}).status_code, 403)
        self.assertEqual(self.client.post(endpoint, json=[], headers=self.headers).status_code, 400)

    def test_physical_column_order_is_ignored_but_constraints_are_not(self):
        """[역할] 순서 동등성과 제약 차이를 구분합니다. [의존성 관계] schema_contract. [변경 시 영향도] 복원 호환성."""
        left, right = connect_database(':memory:'), connect_database(':memory:')
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        left.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, SessionToken TEXT, email TEXT UNIQUE, value TEXT CHECK(value != 'a  b'))")
        right.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, value TEXT CHECK(value != 'a  b'), SessionToken TEXT)")
        self.assertEqual(schema_contract(left), schema_contract(right))
        right.execute('DROP TABLE users')
        right.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, value TEXT CHECK(value != 'a b'), SessionToken TEXT)")
        self.assertNotEqual(schema_contract(left), schema_contract(right))

    def test_history_user_column_order_restore_compatibility(self):
        """[역할] 실제 앱 테이블의 ALTER 이력을 재현합니다. [의존성 관계] backup validator. [변경 시 영향도] Proposal013."""
        path = self.root / 'history.db'
        candidate = connect_database(path)
        self.connection.backup(candidate)
        candidate.execute('ALTER TABLE users DROP COLUMN SessionToken')
        candidate.execute('ALTER TABLE users ADD COLUMN SessionToken TEXT')
        candidate.commit()
        candidate.close()
        self.module.validate_database_compatibility(path, self.module.DATABASE_PATH)
        self.module.validate_database_compatibility(self.module.DATABASE_PATH, path)

    def test_version_mismatch_and_missing_index_rejected(self):
        """[역할] 구조 버전과 인덱스 누락을 차단합니다. [의존성 관계] backup validator. [변경 시 영향도] 복원 게이트."""
        path = self.root / 'mismatch.db'
        candidate = connect_database(path)
        self.connection.backup(candidate)
        candidate.execute('PRAGMA user_version=2')
        candidate.close()
        with self.assertRaisesRegex(ValueError, '버전'):
            self.module.validate_database_compatibility(path, self.module.DATABASE_PATH)
        candidate = connect_database(path)
        candidate.execute('PRAGMA user_version=1')
        candidate.execute('DROP INDEX idx_contract_equipment_owner')
        candidate.close()
        with self.assertRaisesRegex(ValueError, '인덱스'):
            self.module.validate_database_compatibility(path, self.module.DATABASE_PATH)

    def test_migration_down_up_is_idempotent_and_keeps_rows(self):
        """[역할] 복구와 재적용을 실제 사본에서 시험합니다. [의존성 관계] migration. [변경 시 영향도] 업무 행 보존."""
        path = self.root / 'rollback.db'
        candidate = connect_database(path)
        self.connection.backup(candidate)
        before = tuple(candidate.execute('SELECT * FROM equipments').fetchone())
        candidate.close()
        self.assertEqual(rollback_contract(path, self.root / 'rollback-backups')['version'], 0)
        self.assertTrue(migrate_contract(path, self.root / 'rollback-backups')['applied'])
        self.assertFalse(migrate_contract(path, self.root / 'rollback-backups')['applied'])
        candidate = connect_database(path)
        self.addCleanup(candidate.close)
        self.assertEqual(tuple(candidate.execute('SELECT * FROM equipments').fetchone()), before)
        self.assertEqual(candidate.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_declared_indexes_support_actual_query_shapes(self):
        """[역할] 실제 WHERE/ORDER BY의 인덱스 선택을 검증합니다. [의존성 관계] SQLite planner. [변경 시 영향도] 중복 인덱스 방지."""
        cases = (
            ('SELECT id FROM equipments WHERE user_id=? AND (is_draft=0 OR is_draft IS NULL) ORDER BY id DESC', (90001,), 'idx_contract_equipment_owner'),
            ('SELECT id FROM equipments WHERE is_public=1 AND user_id!=? AND (is_draft=0 OR is_draft IS NULL) ORDER BY id DESC', (90002,), 'idx_contract_equipment_public'),
            ('SELECT ExpiresAt FROM password_resets WHERE UserId=? ORDER BY ExpiresAt DESC LIMIT 1', (90001,), 'idx_contract_password_latest'),
            ("SELECT RequestId FROM approval_requests WHERE RequestType='ADD_CATEGORY' AND Status='PENDING' AND json_extract(RequestDataJSON,'$.name')=?", ('Second',), 'idx_contract_approval_pending'),
        )
        for query, params, index in cases:
            plan = ' '.join(row[3] for row in self.connection.execute('EXPLAIN QUERY PLAN ' + query, params))
            self.assertIn(index, plan)
            self.assertNotIn('TEMP B-TREE', plan)


if __name__ == '__main__':
    unittest.main()
