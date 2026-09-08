import importlib.util
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path


class Proposal013RestoreTests(unittest.TestCase):
    """Linux 스테이징 서버에서 정상 복원과 자동 원복을 모의 DB로 검증합니다."""

    @classmethod
    def setUpClass(cls):
        cls.temp_root = tempfile.mkdtemp(prefix='proposal013-test-')
        cls.live_path = os.path.join(cls.temp_root, 'live.db')
        os.environ['DATABASE_PATH'] = cls.live_path
        os.environ['DATABASE_OPERATION_ROOT'] = os.path.join(cls.temp_root, 'operations')
        os.environ['MAINTENANCE_STATE_PATH'] = os.path.join(cls.temp_root, 'maintenance.json')
        project_root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('proposal013_production_app', project_root / 'app.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        password_hash = cls.module.generate_password_hash('candidate-secret')
        conn = sqlite3.connect(cls.live_path)
        conn.execute("INSERT INTO users (LoginId, Name, NickName, Password, Role, CreatedAt, IsDeactivated, IsDeleted, SessionToken) VALUES (?, ?, ?, ?, 'admin', datetime('now'), 'N', 'N', hex(randomblob(16)))",
                     ('restore-admin', '원본 관리자', '관리자', password_hash))
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.module.shutdown_event.set()
        cls.module.logger_thread.join(timeout=2.0)
        shutil.rmtree(cls.temp_root, ignore_errors=True)

    def setUp(self):
        self.module.set_maintenance_state('DRAINING', '테스트 점검', '', 'restore-admin')
        with self.module.DATABASE_JOBS_LOCK:
            self.module.DATABASE_JOBS.clear()

    def make_candidate(self, name):
        candidate_path = os.path.join(self.temp_root, f'{name}.db')
        self.module.create_online_backup(candidate_path)
        conn = sqlite3.connect(candidate_path)
        conn.execute("UPDATE users SET Name = ? WHERE LoginId = 'restore-admin'", (name,))
        conn.commit()
        conn.close()
        return candidate_path

    def run_job(self, job_id, candidate_path, password):
        with self.module.DATABASE_JOBS_LOCK:
            self.module.DATABASE_JOBS[job_id] = {
                'job_id': job_id,
                'monitor_token': 'test-token',
                'candidate_path': candidate_path,
                'candidate_admin_login_id': 'restore-admin',
                'candidate_admin_password': password,
                'actor_login_id': 'restore-admin',
                'expected_end_at': '',
                'state': 'queued',
                'message': '대기',
                'created_at': '2026-09-07 00:00:00'
            }
        self.module.run_database_restore_job(job_id)

    def read_admin_name(self):
        conn = sqlite3.connect(self.live_path)
        name = conn.execute("SELECT Name FROM users WHERE LoginId = 'restore-admin'").fetchone()[0]
        conn.close()
        return name

    def test_valid_candidate_is_restored(self):
        candidate_path = self.make_candidate('복원된 관리자')
        self.run_job('success-job', candidate_path, 'candidate-secret')
        self.assertEqual('복원된 관리자', self.read_admin_name())
        self.assertEqual('succeeded', self.module.DATABASE_JOBS['success-job']['state'])
        self.assertEqual('RECOVERY', self.module.get_maintenance_state()['state'])

    def test_failed_post_validation_rolls_back(self):
        original_name = self.read_admin_name()
        candidate_path = self.make_candidate('원복되어야 할 값')
        self.run_job('rollback-job', candidate_path, '잘못된-비밀번호')
        self.assertEqual(original_name, self.read_admin_name())
        self.assertEqual('failed', self.module.DATABASE_JOBS['rollback-job']['state'])
        self.assertTrue(self.module.DATABASE_JOBS['rollback-job']['rollback_succeeded'])

    def test_candidate_with_missing_schema_is_rejected(self):
        candidate_path = self.make_candidate('호환성 검사 대상')
        conn = sqlite3.connect(candidate_path)
        conn.execute('DROP TABLE access_logs')
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(ValueError, '스키마 객체'):
            self.module.validate_database_compatibility(candidate_path, self.live_path)

    def test_candidate_with_missing_index_is_rejected(self):
        baseline = sqlite3.connect(self.live_path)
        baseline.execute('CREATE INDEX proposal013_test_users_name ON users(Name)')
        baseline.commit()
        baseline.close()
        candidate_path = self.make_candidate('인덱스 호환성 검사 대상')
        candidate = sqlite3.connect(candidate_path)
        candidate.execute('DROP INDEX proposal013_test_users_name')
        candidate.commit()
        candidate.close()
        try:
            with self.assertRaisesRegex(ValueError, '제약조건·인덱스'):
                self.module.validate_database_compatibility(candidate_path, self.live_path)
        finally:
            baseline = sqlite3.connect(self.live_path)
            baseline.execute('DROP INDEX IF EXISTS proposal013_test_users_name')
            baseline.commit()
            baseline.close()

    def test_journal_progress_failure_does_not_skip_rollback(self):
        original_name = self.read_admin_name()
        candidate_path = self.make_candidate('저널 오류 원복 대상')
        original_update = self.module.update_database_job

        def fail_only_rollback_progress(job_id, **changes):
            if changes.get('state') == 'rolling_back':
                raise OSError('test journal write failure')
            return original_update(job_id, **changes)

        self.module.update_database_job = fail_only_rollback_progress
        try:
            self.run_job('journal-failure-job', candidate_path, '잘못된-비밀번호')
        finally:
            self.module.update_database_job = original_update
        self.assertEqual(original_name, self.read_admin_name())
        self.assertTrue(self.module.DATABASE_JOBS['journal-failure-job']['rollback_succeeded'])

    def test_request_teardown_releases_unclosed_tracked_connection(self):
        initial_count = self.module.ACTIVE_DATABASE_CONNECTIONS
        request_context = self.module.app.test_request_context('/proposal013-test')
        request_context.push()
        self.module.get_db_connection()
        request_context.pop()
        self.assertEqual(initial_count, self.module.ACTIVE_DATABASE_CONNECTIONS)

    def test_restore_status_requires_header_token(self):
        with self.module.DATABASE_JOBS_LOCK:
            self.module.DATABASE_JOBS['status-job'] = {
                'job_id': 'status-job', 'monitor_token': 'header-only-token',
                'candidate_path': '/not/public.db', 'candidate_admin_password': 'not-public',
                'state': 'succeeded', 'message': '완료', 'error': 'not-public'
            }
        client = self.module.app.test_client()
        query_response = client.get('/api/admin/database/restore-status/status-job?token=header-only-token')
        header_response = client.get('/api/admin/database/restore-status/status-job', headers={
            'X-Restore-Monitor-Token': 'header-only-token'
        })
        self.assertEqual(404, query_response.status_code)
        self.assertEqual(200, header_response.status_code)
        self.assertNotIn('candidate_path', header_response.get_json()['job'])
        self.assertNotIn('error', header_response.get_json()['job'])

    def test_expired_candidate_file_is_purged_after_restart(self):
        directories = self.module.ensure_database_operation_directories()
        stale_path = os.path.join(directories['candidates'], 'stale-candidate.db')
        Path(stale_path).write_bytes(b'SQLite format 3\x00' + (b'0' * 100))
        expired_at = 0
        os.utime(stale_path, (expired_at, expired_at))
        self.module.purge_expired_database_operation_files()
        self.assertFalse(os.path.exists(stale_path))


if __name__ == '__main__':
    unittest.main()
