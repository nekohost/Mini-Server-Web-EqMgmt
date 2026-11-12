"""
tests/test_access_log_cleanup_sql.py

Pure in-memory deterministic SQLite unit tests for utils.access_log_cleanup.
"""
from __future__ import annotations

import json
import sqlite3
import unittest
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from utils.access_log_cleanup import (
    CHUNK_SIZE,
    CleanupError,
    advance,
    begin,
)


def create_equipment_test_db() -> sqlite3.Connection:
    """Create in-memory SQLite connection with equipment DB tables and sqlite3.Row factory."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE access_logs (
            LogId INTEGER PRIMARY KEY AUTOINCREMENT,
            IpAddress TEXT,
            HttpMethod TEXT,
            RequestPath TEXT,
            StatusCode INTEGER,
            UserAgent TEXT,
            Referer TEXT,
            DurationMs INTEGER,
            IsStatic INTEGER,
            RequestPayload TEXT,
            ResponsePayload TEXT,
            CreatedAt TEXT
        )
    ''')
    conn.execute('CREATE INDEX idx_access_logs_created_at ON access_logs (CreatedAt DESC)')
    conn.execute('CREATE INDEX idx_access_logs_ip ON access_logs (IpAddress)')
    conn.execute('CREATE INDEX idx_access_logs_status ON access_logs (StatusCode)')
    conn.execute('CREATE INDEX idx_access_logs_is_static ON access_logs (IsStatic)')

    conn.execute('''
        CREATE TABLE audit_logs (
            AuditId INTEGER PRIMARY KEY AUTOINCREMENT,
            ActorId INTEGER,
            ActorLoginId TEXT,
            IpAddress TEXT,
            UserAgent TEXT,
            TargetTable TEXT,
            TargetId INTEGER,
            Action TEXT,
            OldValue TEXT,
            NewValue TEXT,
            CreatedAt TEXT
        )
    ''')
    return conn


def make_audit_logger(actor_id: int = 1, login_id: str = 'admin'):
    """Generate standard audit callback that appends to audit_logs."""
    def audit(conn: sqlite3.Connection, action_name: str, target_id: Optional[int], data_dict: Dict[str, Any]):
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            '''
            INSERT INTO audit_logs (ActorId, ActorLoginId, IpAddress, UserAgent, TargetTable, TargetId, Action, OldValue, NewValue, CreatedAt)
            VALUES (?, ?, '127.0.0.1', 'pytest', 'access_logs', ?, ?, NULL, ?, ?)
            ''',
            (actor_id, login_id, target_id, action_name, json.dumps(data_dict, ensure_ascii=False), now_str)
        )
    return audit


class TestAccessLogCleanupSQL(unittest.TestCase):
    def setUp(self):
        self.conn = create_equipment_test_db()
        self.actor_id = 42
        self.audit = make_audit_logger(actor_id=self.actor_id, login_id='admin_operator')

    def tearDown(self):
        self.conn.close()

    def _insert_log(
        self,
        path: str = '/dashboard',
        is_static: int = 0,
        days_ago: int = 0,
        count: int = 1,
    ):
        created = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
        for _ in range(count):
            self.conn.execute(
                '''
                INSERT INTO access_logs (IpAddress, HttpMethod, RequestPath, StatusCode, UserAgent, Referer, DurationMs, IsStatic, CreatedAt)
                VALUES ('10.0.0.1', 'GET', ?, 200, 'agent', '', 15, ?, ?)
                ''',
                (path, is_static, created)
            )
        self.conn.commit()

    def test_begin_success_and_audited_start(self):
        self._insert_log('/dashboard', count=5)
        ceiling = self.conn.execute('SELECT MAX(LogId) FROM access_logs').fetchone()[0]

        res = begin(self.conn, 'all', self.actor_id, self.audit, ceiling)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['total_count'], 5)
        self.assertTrue(isinstance(res['operation_id'], str))
        self.assertIn('.', res['operation_id'])

        audit_id_str, nonce = res['operation_id'].split('.', 1)
        audit_id = int(audit_id_str)
        self.assertTrue(len(nonce) >= 16)

        # Verify audit_logs row
        audit_row = self.conn.execute('SELECT * FROM audit_logs WHERE AuditId = ?', (audit_id,)).fetchone()
        self.assertIsNotNone(audit_row)
        self.assertEqual(audit_row['Action'], 'CLEANUP_ACCESS_LOGS_START')
        self.assertEqual(audit_row['TargetTable'], 'access_logs')
        self.assertEqual(audit_row['ActorId'], self.actor_id)

        payload = json.loads(audit_row['NewValue'])
        self.assertEqual(payload['bound'], ceiling)
        self.assertEqual(payload['action'], 'all')
        self.assertEqual(payload['nonce'], nonce)
        self.assertEqual(payload['total_count'], 5)

    def test_ai_exclusion_filter_for_old_actions(self):
        # Insert various AI and non-AI logs
        self._insert_log('/assistant', count=2)
        self._insert_log('/admin/ai/providers', count=2)
        self._insert_log('/api/ai/stream', count=2)
        self._insert_log('/internal/ai/claim', count=2)
        self._insert_log('/api/admin/ai/config', count=2)
        self._insert_log('/dashboard', is_static=0, count=3)
        self._insert_log('/static/style.css', is_static=1, count=4)

        ceiling = self.conn.execute('SELECT MAX(LogId) FROM access_logs').fetchone()[0]

        # 1. Action 'all' excludes all AI paths (10 AI rows excluded, 7 normal rows eligible)
        res_all = begin(self.conn, 'all', self.actor_id, self.audit, ceiling)
        self.assertEqual(res_all['total_count'], 7)

        # 2. Action 'static_only' excludes dynamic (/dashboard) and AI (only 4 static CSS eligible)
        res_static = begin(self.conn, 'static_only', self.actor_id, self.audit, ceiling)
        self.assertEqual(res_static['total_count'], 4)

        # 3. Action 'all_including_ai' includes EVERY row up to ceiling (all 17 rows)
        res_inc_ai = begin(self.conn, 'all_including_ai', self.actor_id, self.audit, ceiling)
        self.assertEqual(res_inc_ai['total_count'], 17)

    def test_older_30d_stable_cutoff(self):
        # Insert old logs (>30 days ago) and recent logs (<30 days ago)
        self._insert_log('/dashboard', days_ago=40, count=5)
        self._insert_log('/assistant', days_ago=40, count=5)  # AI log older than 30d (must be excluded)
        self._insert_log('/dashboard', days_ago=10, count=3)   # Recent log (must be excluded)

        ceiling = self.conn.execute('SELECT MAX(LogId) FROM access_logs').fetchone()[0]

        res = begin(self.conn, 'older_30d', self.actor_id, self.audit, ceiling)
        # Only the 5 non-AI older logs are eligible
        self.assertEqual(res['total_count'], 5)

        op_id = res['operation_id']
        adv_res = advance(self.conn, 'older_30d', self.actor_id, op_id, 'direct', self.audit)
        self.assertEqual(adv_res['deleted_count'], 5)

        # Verify remaining logs: 5 AI (older) + 3 normal (recent) = 8
        rem = self.conn.execute('SELECT COUNT(*) FROM access_logs').fetchone()[0]
        self.assertEqual(rem, 8)

        # Finish succeeds
        fin_res = advance(self.conn, 'older_30d', self.actor_id, op_id, 'finish', self.audit)
        self.assertEqual(fin_res['status'], 'success')
        self.assertEqual(fin_res['deleted_count'], 5)
        self.assertEqual(fin_res['remaining_count'], 0)

    def test_ceiling_barrier_protects_subsequent_writes(self):
        self._insert_log('/dashboard', count=10)
        barrier_ceiling = 6  # Caller barriers up to LogId 6

        # Subsequent writes after barrier
        self._insert_log('/dashboard', count=5)

        res = begin(self.conn, 'all', self.actor_id, self.audit, barrier_ceiling)
        self.assertEqual(res['total_count'], 6)

        op_id = res['operation_id']
        adv_res = advance(self.conn, 'all', self.actor_id, op_id, 'direct', self.audit)
        self.assertEqual(adv_res['deleted_count'], 6)

        # All logs with LogId > 6 remain untouched
        remaining_ids = [r[0] for r in self.conn.execute('SELECT LogId FROM access_logs ORDER BY LogId').fetchall()]
        self.assertEqual(remaining_ids, [7, 8, 9, 10, 11, 12, 13, 14, 15])

        fin = advance(self.conn, 'all', self.actor_id, op_id, 'finish', self.audit)
        self.assertEqual(fin['status'], 'success')
        self.assertEqual(fin['deleted_count'], 6)
        self.assertEqual(fin['remaining_count'], 0)

    def test_delete_chunk_batching_and_ordered_removal(self):
        # Insert 600 rows to test 250-row chunking
        self._insert_log('/dashboard', count=600)
        ceiling = 600

        res = begin(self.conn, 'all', self.actor_id, self.audit, ceiling)
        self.assertEqual(res['total_count'], 600)
        op_id = res['operation_id']

        # Chunk 1: at most 250 old IDs
        c1 = advance(self.conn, 'all', self.actor_id, op_id, 'delete_chunk', self.audit)
        self.assertEqual(c1['status'], 'success')
        self.assertEqual(c1['deleted_count'], 250)
        self.assertNotIn('remaining_count', c1)

        # Lowest remaining LogId should now be 251
        min_id = self.conn.execute('SELECT MIN(LogId) FROM access_logs').fetchone()[0]
        self.assertEqual(min_id, 251)

        # Chunk 2: next 250 IDs
        c2 = advance(self.conn, 'all', self.actor_id, op_id, 'delete_chunk', self.audit)
        self.assertEqual(c2['deleted_count'], 250)
        self.assertNotIn('remaining_count', c2)
        min_id = self.conn.execute('SELECT MIN(LogId) FROM access_logs').fetchone()[0]
        self.assertEqual(min_id, 501)

        # Chunk 3: remaining 100 IDs
        c3 = advance(self.conn, 'all', self.actor_id, op_id, 'delete_chunk', self.audit)
        self.assertEqual(c3['deleted_count'], 100)
        self.assertNotIn('remaining_count', c3)

        # Chunk 4: empty chunk (0 deleted)
        c4 = advance(self.conn, 'all', self.actor_id, op_id, 'delete_chunk', self.audit)
        self.assertEqual(c4['deleted_count'], 0)
        self.assertNotIn('remaining_count', c4)

        # Finish succeeds and authoritative own sum is 600
        fin = advance(self.conn, 'all', self.actor_id, op_id, 'finish', self.audit)
        self.assertEqual(fin['status'], 'success')
        self.assertEqual(fin['deleted_count'], 600)
        self.assertEqual(fin['remaining_count'], 0)

    def test_direct_step_cleans_snapshot_and_authoritative_finish(self):
        self._insert_log('/dashboard', count=320)
        ceiling = 320

        res = begin(self.conn, 'all', self.actor_id, self.audit, ceiling)
        self.assertEqual(res['total_count'], 320)
        op_id = res['operation_id']

        adv_res = advance(self.conn, 'all', self.actor_id, op_id, 'direct', self.audit)
        self.assertEqual(adv_res['status'], 'success')
        self.assertEqual(adv_res['deleted_count'], 320)
        self.assertNotIn('remaining_count', adv_res)

        # Database rows are gone
        cnt = self.conn.execute('SELECT COUNT(*) FROM access_logs').fetchone()[0]
        self.assertEqual(cnt, 0)

        # Authoritative finish succeeds with 320
        fin = advance(self.conn, 'all', self.actor_id, op_id, 'finish', self.audit)
        self.assertEqual(fin['status'], 'success')
        self.assertEqual(fin['deleted_count'], 320)
        self.assertEqual(fin['remaining_count'], 0)

    def test_finish_fails_when_rows_remain(self):
        self._insert_log('/dashboard', count=300)
        ceiling = 300
        res = begin(self.conn, 'all', self.actor_id, self.audit, ceiling)
        op_id = res['operation_id']

        # Delete only 1 chunk of 250 rows (50 rows remain)
        advance(self.conn, 'all', self.actor_id, op_id, 'delete_chunk', self.audit)

        # Attempting finish must fail with 409
        with self.assertRaises(CleanupError) as ctx:
            advance(self.conn, 'all', self.actor_id, op_id, 'finish', self.audit)
        self.assertEqual(ctx.exception.status, 409)
        self.assertIn('50', str(ctx.exception))

    def test_finish_repeated_is_idempotent(self):
        self._insert_log('/dashboard', count=20)
        ceiling = 20
        res = begin(self.conn, 'all', self.actor_id, self.audit, ceiling)
        op_id = res['operation_id']

        advance(self.conn, 'all', self.actor_id, op_id, 'direct', self.audit)

        # First finish
        fin1 = advance(self.conn, 'all', self.actor_id, op_id, 'finish', self.audit)
        self.assertEqual(fin1['status'], 'success')
        self.assertEqual(fin1['deleted_count'], 20)
        self.assertEqual(fin1['remaining_count'], 0)

        # Repeated finish
        fin2 = advance(self.conn, 'all', self.actor_id, op_id, 'finish', self.audit)
        self.assertEqual(fin2['status'], 'success')
        self.assertEqual(fin2['deleted_count'], 20)
        self.assertEqual(fin2['remaining_count'], 0)

    def test_failed_audit_rolls_back_chunk_deletion(self):
        self._insert_log('/dashboard', count=10)
        ceiling = 10
        res = begin(self.conn, 'all', self.actor_id, self.audit, ceiling)
        op_id = res['operation_id']

        # Audit callback that fails on CLEANUP_ACCESS_LOGS
        def failing_audit(conn, action_name, target_id, data_dict):
            if action_name == 'CLEANUP_ACCESS_LOGS':
                raise RuntimeError("simulated audit failure")
            self.audit(conn, action_name, target_id, data_dict)

        with self.assertRaises(CleanupError) as ctx:
            advance(self.conn, 'all', self.actor_id, op_id, 'delete_chunk', failing_audit)
        self.assertEqual(ctx.exception.status, 500)

        # Verify access_logs were NOT deleted (rolled back!)
        cnt = self.conn.execute('SELECT COUNT(*) FROM access_logs WHERE LogId <= 10').fetchone()[0]
        self.assertEqual(cnt, 10)

    def test_failed_audit_rolls_back_direct_deletion(self):
        self._insert_log('/dashboard', count=15)
        ceiling = 15
        res = begin(self.conn, 'all', self.actor_id, self.audit, ceiling)
        op_id = res['operation_id']

        def failing_audit(conn, action_name, target_id, data_dict):
            if action_name == 'CLEANUP_ACCESS_LOGS':
                raise RuntimeError("simulated direct audit failure")
            self.audit(conn, action_name, target_id, data_dict)

        with self.assertRaises(CleanupError) as ctx:
            advance(self.conn, 'all', self.actor_id, op_id, 'direct', failing_audit)
        self.assertEqual(ctx.exception.status, 500)

        # Verify access_logs were NOT deleted (rolled back!)
        cnt = self.conn.execute('SELECT COUNT(*) FROM access_logs WHERE LogId <= 15').fetchone()[0]
        self.assertEqual(cnt, 15)

    def test_concurrent_cleanups_authoritative_accounting(self):
        # 400 rows total
        self._insert_log('/dashboard', count=400)
        ceiling = 400

        # Operator A and Operator B both begin on the snapshot
        res_a = begin(self.conn, 'all', actor_id=101, audit=make_audit_logger(101), ceiling=ceiling)
        res_b = begin(self.conn, 'all', actor_id=102, audit=make_audit_logger(102), ceiling=ceiling)

        op_a = res_a['operation_id']
        op_b = res_b['operation_id']

        # Op A deletes first chunk (250 rows)
        adv_a1 = advance(self.conn, 'all', 101, op_a, 'delete_chunk', make_audit_logger(101))
        self.assertEqual(adv_a1['deleted_count'], 250)

        # Op B deletes second chunk (remaining 150 rows)
        adv_b1 = advance(self.conn, 'all', 102, op_b, 'delete_chunk', make_audit_logger(102))
        self.assertEqual(adv_b1['deleted_count'], 150)

        # Both call finish: Op A claims exactly 250, Op B claims exactly 150
        fin_a = advance(self.conn, 'all', 101, op_a, 'finish', make_audit_logger(101))
        self.assertEqual(fin_a['deleted_count'], 250)
        self.assertEqual(fin_a['remaining_count'], 0)

        fin_b = advance(self.conn, 'all', 102, op_b, 'finish', make_audit_logger(102))
        self.assertEqual(fin_b['deleted_count'], 150)
        self.assertEqual(fin_b['remaining_count'], 0)

        # Total rows deleted across both is 400, neither overclaims
        self.assertEqual(fin_a['deleted_count'] + fin_b['deleted_count'], 400)

    def test_large_protected_prefix_is_scanned_once_per_chunk_sequence(self):
        self.conn.execute("""WITH RECURSIVE series(i) AS
            (SELECT 1 UNION ALL SELECT i+1 FROM series WHERE i<677968)
            INSERT INTO access_logs(RequestPath,CreatedAt) SELECT '/internal/ai/claim','2026-01-01' FROM series""")
        self.conn.commit()
        self._insert_log('/ordinary', count=751)
        ceiling = self.conn.execute('SELECT MAX(LogId) FROM access_logs').fetchone()[0]
        statements = []
        self.conn.set_trace_callback(statements.append)
        op = begin(self.conn,'all',self.actor_id,self.audit,ceiling)['operation_id']
        parts = [advance(self.conn,'all',self.actor_id,op,'delete_chunk',self.audit)['deleted_count'] for _ in range(4)]
        self.assertEqual(parts,[250,250,250,1])
        self.assertEqual(advance(self.conn,'all',self.actor_id,op,'finish',self.audit)['deleted_count'],751)
        self.conn.set_trace_callback(None)
        counts = [sql for sql in statements if sql.startswith('SELECT COUNT(*) FROM access_logs')]
        self.assertEqual(len(counts),2)
        chunks = [sql for sql in statements if sql.startswith('SELECT LogId FROM access_logs')]
        self.assertEqual(len(chunks),4)
        for query in chunks[1:]:
            plan = ' '.join(row[3] for row in self.conn.execute('EXPLAIN QUERY PLAN '+query))
            self.assertIn('rowid>?',plan)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM access_logs').fetchone()[0],677968)

    def test_reject_wrong_actor(self):
        self._insert_log('/dashboard', count=5)
        res = begin(self.conn, 'all', actor_id=10, audit=make_audit_logger(10), ceiling=5)
        op_id = res['operation_id']

        # Different actor attempts to advance
        with self.assertRaises(CleanupError) as ctx:
            advance(self.conn, 'all', actor_id=999, operation_id=op_id, step='delete_chunk', audit=self.audit)
        self.assertEqual(ctx.exception.status, 403)
        self.assertIn("관리자만", str(ctx.exception))

    def test_reject_wrong_scope(self):
        self._insert_log('/dashboard', count=5)
        res = begin(self.conn, 'static_only', self.actor_id, self.audit, ceiling=5)
        op_id = res['operation_id']

        # Different action passed to advance
        with self.assertRaises(CleanupError) as ctx:
            advance(self.conn, 'all', self.actor_id, op_id, 'delete_chunk', self.audit)
        self.assertEqual(ctx.exception.status, 400)
        self.assertIn("범위", str(ctx.exception))

    def test_reject_malformed_and_tampered_ids(self):
        # Malformed ids
        for bad_id in ('', 'no_dot', 'abc.nonce', '123.', '.nonce', None):
            with self.assertRaises(CleanupError) as ctx:
                advance(self.conn, 'all', self.actor_id, bad_id, 'delete_chunk', self.audit)
            self.assertEqual(ctx.exception.status, 400)

        # Unknown AuditId
        with self.assertRaises(CleanupError) as ctx:
            advance(self.conn, 'all', self.actor_id, '99999.'+'a'*32, 'delete_chunk', self.audit)
        self.assertEqual(ctx.exception.status, 404)

        # Tampered nonce on existing AuditId
        self._insert_log('/dashboard', count=2)
        res = begin(self.conn, 'all', self.actor_id, self.audit, ceiling=2)
        audit_id_str, _ = res['operation_id'].split('.', 1)

        tampered_op = audit_id_str+'.'+'a'*32
        with self.assertRaises(CleanupError) as ctx:
            advance(self.conn, 'all', self.actor_id, tampered_op, 'delete_chunk', self.audit)
        self.assertEqual(ctx.exception.status, 403)

    def test_reject_invalid_parameters(self):
        # Invalid action in begin
        with self.assertRaises(CleanupError) as ctx:
            begin(self.conn, 'invalid_action', self.actor_id, self.audit, 10)
        self.assertEqual(ctx.exception.status, 400)

        # Invalid actor_id in begin
        for bad_actor in (None, 0, -1, 'bad'):
            with self.assertRaises(CleanupError) as ctx:
                begin(self.conn, 'all', bad_actor, self.audit, 10)
            self.assertEqual(ctx.exception.status, 403)

        # Invalid ceiling in begin
        for bad_ceil in (-1, None, '10', False, True):
            with self.assertRaises(CleanupError) as ctx:
                begin(self.conn, 'all', self.actor_id, self.audit, bad_ceil)
            self.assertEqual(ctx.exception.status, 400)

        # Invalid step in advance
        res = begin(self.conn, 'all', self.actor_id, self.audit, 10)
        op_id = res['operation_id']
        with self.assertRaises(CleanupError) as ctx:
            advance(self.conn, 'all', self.actor_id, op_id, 'invalid_step', self.audit)
        self.assertEqual(ctx.exception.status, 400)

    def test_advance_count_step(self):
        self._insert_log('/dashboard', count=8)
        res = begin(self.conn, 'all', self.actor_id, self.audit, ceiling=8)
        op_id = res['operation_id']

        cnt_res = advance(self.conn, 'all', self.actor_id, op_id, 'count', self.audit)
        self.assertEqual(cnt_res['status'], 'success')
        self.assertEqual(cnt_res['total_count'], 8)
        self.assertEqual(cnt_res['remaining_count'], 8)

        # Advance with delete_chunk, then count again
        advance(self.conn, 'all', self.actor_id, op_id, 'delete_chunk', self.audit)
        cnt_res2 = advance(self.conn, 'all', self.actor_id, op_id, 'count', self.audit)
        self.assertEqual(cnt_res2['total_count'], 0)
        self.assertEqual(cnt_res2['remaining_count'], 0)


if __name__ == '__main__':
    unittest.main()
