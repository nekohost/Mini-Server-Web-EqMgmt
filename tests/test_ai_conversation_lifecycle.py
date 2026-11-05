"""[MINI-COMMENT: ASSISTANT.LIFECYCLE.TESTS]
[EN rev.2]
[Role] Exercises v4 lifecycle/time/ownership/ledger/guard races using synthetic Linux-only SQLite stores.
[Dependencies] unittest, temporary files and fake clocks; no production app, database, service or model call.
[Impact] Detects content resurrection, stale deletion and premature shared-group release before deployment.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import types
import sys
import unittest
from unittest.mock import patch
import uuid

from utils.ai_assistant.lifecycle import RETENTION_SECONDS
from utils.ai_assistant.policy import AssistantError, digest
from utils.ai_assistant.providers import LEGACY_GROUP, migrate as provider_migrate
from utils.ai_assistant.store import SCHEMA, Store


@unittest.skipUnless(os.name == 'posix', 'Linux-only isolated behavior fixtures')
class ConversationLifecycleTests(unittest.TestCase):
    """[Role] Covers destructive state boundaries on disposable stores. [Dependencies] No network. [Impact] Synthetic data only."""

    def setUp(self):
        """[Role] Creates one private synthetic AI store. [Dependencies] TemporaryDirectory. [Impact] No app import."""
        self.tmp = tempfile.TemporaryDirectory(prefix='eq-ai-lifecycle-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'assistant.sqlite3'
        self.epoch = 'synthetic-lifecycle-epoch-v4'
        self.store = Store(self.path, epoch=self.epoch)
        self.store.turn_limit_minute = self.store.turn_limit_day = 10000
        self.owner, self.account = 2, 'synthetic-account-two'
        self.now = 1800000000.0

    def new_conversation(self, owner=None, account=None):
        """[Role] Creates a bounded owner fixture. [Dependencies] Store API. [Impact] No business writes."""
        return self.store.create_conversation(owner or self.owner, account or self.account)

    def operation(self, cid, action, revision, operation_id=None):
        """[Role] Sends a fresh synthetic lifecycle request. [Dependencies] Store API. [Impact] Explicit revision."""
        return self.store.lifecycle(self.owner, cid, self.account, action, revision, operation_id or uuid.uuid4().hex)

    def enqueue(self, cid=None, content='Synthetic question', owner=None, account=None):
        """[Role] Creates an inert queued turn. [Dependencies] Local Store only. [Impact] Never dispatches a model."""
        cid = cid or self.new_conversation(owner, account)
        jid = self.store.enqueue(owner or self.owner, cid, content, 'medium', uuid.uuid4().hex,
                                 'synthetic-binding', time.time() + 3600, account or self.account)
        return cid, jid

    def error_status(self, expected, callback):
        """[Role] Checks safe error codes. [Dependencies] AssistantError. [Impact] Prevents existence leaks."""
        with self.assertRaises(AssistantError) as caught:
            callback()
        self.assertEqual(caught.exception.status, expected)

    def test_new_and_repeated_startup_keep_v4_guard_index(self):
        """[Role] Verifies idempotent fresh initialization. [Dependencies] SQLite metadata. [Impact] No version downgrade."""
        cid = self.new_conversation()
        Store(self.path, epoch=self.epoch)
        Store(self.path, epoch=self.epoch)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT version FROM ai_meta').fetchone()[0], 4)
            self.assertEqual(db.execute("SELECT tbl_name FROM sqlite_master WHERE name='one_group_request'").fetchone()[0], 'ai_execution_guards')
            row = self.store.conversation(self.owner, cid, db, self.account)
            self.assertEqual((row['is_deleted'], row['deleted_at'], row['purge_after'], row['lifecycle_revision']), (0, None, None, 0))

    def test_v3_additive_migration_preserves_content_and_unknown_lease(self):
        """[Role] Migrates actual source-shaped v3 tables twice. [Dependencies] Synthetic SCHEMA. [Impact] Unknown slot stays held."""
        path = Path(self.tmp.name) / 'v3.sqlite3'
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        db.executescript(SCHEMA)
        provider_migrate(db)
        cid, jid, token = uuid.uuid4().hex, uuid.uuid4().hex, 'synthetic-lease'
        db.execute('INSERT INTO conversations(id,owner,account_key,title,created,updated) VALUES(?,?,?,?,?,?)', (cid, 2, self.account, 'Preserved title', 100, 100))
        db.execute('''INSERT INTO jobs(id,conversation,owner,client_key,input_hash,binding,expires,level,state,queue_order,
            resource_group,lease_hash,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (jid, cid, 2, uuid.uuid4().hex, 'hash', 'binding', 9999999999, 'medium', 'recovery_required', 1,
             LEGACY_GROUP, digest([self.epoch, token]), 100, 100))
        db.execute("INSERT INTO messages(conversation,job,role,content,reasoning,created) VALUES(?,?,'assistant','kept answer','kept reasoning',100)", (cid, jid))
        db.commit()
        self.assertEqual(db.execute('SELECT version FROM ai_meta').fetchone()[0], 3)
        db.close()
        migrated = Store(path, epoch=self.epoch)
        Store(path, epoch=self.epoch)
        with migrated.db() as db:
            self.assertEqual(db.execute('SELECT content,reasoning FROM messages').fetchone()[:], ('kept answer', 'kept reasoning'))
            self.assertEqual(db.execute('SELECT is_deleted,lifecycle_revision FROM conversations').fetchone()[:], (0, 0))
            self.assertEqual(db.execute('SELECT job,state,lease_hash FROM ai_execution_guards').fetchone()[:], (jid, 'recovery_required', digest([self.epoch, token])))
            self.assertEqual(db.execute('SELECT used_chars FROM storage_accounts').fetchone()[0], len('kept answerkept reasoning'))

    def test_partial_v4_index_or_control_column_fails_closed(self):
        """[Role] Rejects weakened slot predicates and missing controls. [Dependencies] Startup validator. [Impact] No silent repair."""
        with self.store.db(True) as db:
            db.execute('DROP INDEX one_group_request')
            db.execute("CREATE UNIQUE INDEX one_group_request ON ai_execution_guards(resource_group) WHERE state IN ('recovery_required')")
        with self.assertRaises(ValueError):
            Store(self.path, epoch=self.epoch)
        with self.store.db(True) as db:
            db.execute('DROP INDEX one_group_request')
            db.execute("CREATE UNIQUE INDEX one_group_request ON ai_execution_guards(resource_group) WHERE state IN ('running','draining','recovery_required')")
            db.execute('ALTER TABLE ai_execution_guards DROP COLUMN heartbeat')
        with self.assertRaises(ValueError):
            Store(self.path, epoch=self.epoch)

    def test_trash_restore_retrash_replay_and_stale_revision(self):
        """[Role] Checks server-clock retention and durable replay. [Dependencies] Fake clock. [Impact] Old retries never retrash."""
        cid = self.new_conversation()
        op = uuid.uuid4().hex
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now):
            first = self.operation(cid, 'trash', 0, op)
        self.assertEqual(first['conversation']['purge_after'], self.now + RETENTION_SECONDS)
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now + 10):
            same = self.operation(cid, 'trash', 1)
            self.assertEqual(same['conversation']['deleted_at'], self.now)
            self.assertEqual(same['conversation']['lifecycle_revision'], 1)
            self.operation(cid, 'restore', 1)
            replay = self.operation(cid, 'trash', 0, op)
            self.assertTrue(replay['replayed'])
            self.assertEqual(replay['conversation']['is_deleted'], 0)
            self.error_status(409, lambda: self.operation(cid, 'trash', 0))
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now + 20):
            second = self.operation(cid, 'trash', 2)
        self.assertEqual(second['conversation']['deleted_at'], self.now + 20)
        self.assertEqual(second['conversation']['purge_after'], self.now + 20 + RETENTION_SECONDS)

    def test_lifecycle_owner_account_and_operation_validation(self):
        """[Role] Verifies account reuse and malformed input rejection. [Dependencies] Store auth predicates. [Impact] Foreign state hidden."""
        cid = self.new_conversation()
        self.error_status(404, lambda: self.store.lifecycle(3, cid, self.account, 'trash', 0, uuid.uuid4().hex))
        self.error_status(404, lambda: self.store.lifecycle(2, cid, 'reused-account', 'trash', 0, uuid.uuid4().hex))
        self.error_status(400, lambda: self.operation(cid, 'trash', True))
        # Project opaque() deliberately returns 404 for every malformed public/client identifier.
        self.error_status(404, lambda: self.operation(cid, 'trash', 0, 'not-an-operation'))
        self.error_status(404, lambda: self.operation(cid, 'trash', 0, ['0' * 32]))
        self.error_status(404, lambda: self.operation(cid, 'trash', 0, 'A' * 32))
        self.error_status(409, lambda: self.operation(cid, 'purge', 0))
        operation_id = uuid.uuid4().hex
        self.operation(cid, 'trash', 0, operation_id)
        other = self.new_conversation()
        self.error_status(409, lambda: self.operation(other, 'trash', 0, operation_id))

    def test_expiry_exact_boundary_is_unreadable_and_unrestorable(self):
        """[Role] Rejects expired reads before timer cleanup. [Dependencies] Server UTC only. [Impact] No retention extension."""
        cid = self.new_conversation()
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now):
            self.operation(cid, 'trash', 0)
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now + RETENTION_SECONDS - 0.001):
            self.assertTrue(self.store.snapshot(2, cid, self.account, view='trash')['read_only'])
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now + RETENTION_SECONDS):
            self.error_status(410, lambda: self.store.snapshot(2, cid, self.account, view='trash'))
            self.error_status(410, lambda: self.operation(cid, 'restore', 1))
            self.assertEqual(self.store.conversations(2, self.account, view='trash')['conversations'], [])
            self.assertEqual(self.store.purge_expired()['purged'], 1)

    def test_active_trash_pagination_and_view_cursor_binding(self):
        """[Role] Keeps history cursors bound to one view. [Dependencies] 51 synthetic titles. [Impact] No state crossing."""
        ids = [self.new_conversation() for _ in range(52)]
        page = self.store.conversations(2, self.account)
        self.assertEqual(len(page['conversations']), 50)
        self.assertTrue(page['next_cursor'])
        self.error_status(400, lambda: self.store.conversations(2, self.account, page['next_cursor'], view='trash'))
        moved = self.operation(ids[0], 'trash', 0)['conversation']
        self.assertNotIn(ids[0], {r['id'] for r in self.store.conversations(2, self.account)['conversations']})
        trash = self.store.conversations(2, self.account, view='trash')
        self.assertEqual(trash['conversations'][0]['lifecycle_revision'], moved['lifecycle_revision'])
        self.assertTrue(trash['conversations'][0]['read_only'])

    def test_trash_queued_cancels_proposals_and_restore_does_not_restart(self):
        """[Role] Cancels queued work and pending cards at movement. [Dependencies] Same writer. [Impact] Restore is read-only history recovery."""
        cid, jid = self.enqueue()
        with self.store.db(True) as db:
            db.execute("INSERT INTO proposals(id,job,owner,operation,payload,before_json,signature,expires,created) VALUES(?,?,2,'equipment_create','{}','{}','synthetic',?,?)", (uuid.uuid4().hex, jid, time.time() + 900, time.time()))
        self.operation(cid, 'trash', 0)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT state,cancel,reserved_chars FROM jobs WHERE id=?', (jid,)).fetchone()[:], ('cancelled', 1, 0))
            self.assertEqual(db.execute('SELECT state FROM proposals').fetchone()[0], 'cancelled')
        self.operation(cid, 'restore', 1)
        self.assertIsNone(self.store.claim('fixture-worker'))
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT state FROM jobs WHERE id=?', (jid,)).fetchone()[0], 'cancelled')

    def test_purge_active_request_keeps_guard_until_known_finish(self):
        """[Role] Purges live content without releasing its group. [Dependencies] Detached finish lease. [Impact] No concurrent upstream replay."""
        cid, jid = self.enqueue()
        running = self.store.claim('fixture-worker')
        self.store.append(jid, running['lease'], reasoning='kept-before-trash', content='before')
        self.operation(cid, 'trash', 0)
        self.operation(cid, 'purge', 1)
        other_cid, other_jid = self.enqueue()
        self.assertIsNone(self.store.claim('other-worker'))
        event = self.store.guard_event(jid, running['lease'])
        self.assertEqual((event['accepted'], event['cancel']), (False, True))
        self.assertEqual(self.store.guard_finish(jid, running['lease'], 'recovery_required'), 'recovery_required')
        self.assertIsNone(self.store.claim('other-worker'))
        self.assertEqual(self.store.guard_finish(jid, running['lease'], 'complete'), 'cancelled')
        self.assertEqual(self.store.claim('other-worker')['id'], other_jid)
        self.assertEqual(self.store.guard_finish(jid, running['lease'], 'recovery_required'), 'cancelled')
        with self.store.db() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM conversations WHERE id=?', (cid,)).fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM jobs WHERE id=?', (jid,)).fetchone())

    def test_trashed_then_restored_cancelled_job_never_saves_late_output(self):
        """[Role] Stops output across restore while preserving earlier text. [Dependencies] Cancel state survives. [Impact] No request resurrection."""
        cid, jid = self.enqueue()
        running = self.store.claim('fixture-worker')
        self.store.append(jid, running['lease'], content='before')
        self.operation(cid, 'trash', 0)
        self.operation(cid, 'restore', 1)
        self.assertTrue(self.store.append(jid, running['lease'], content='late'))
        self.store.reconcile(jid, running['lease'], content='beforelate')
        self.assertFalse(self.store.guard_event(jid, running['lease'])['accepted'])
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT content FROM messages WHERE job=? AND role='assistant'", (jid,)).fetchone()[0], 'before')

    def test_guard_finish_preserves_non_user_failure_state_and_original_cause(self):
        """[Role] Preserves processing/maintenance failure classification after a cancel flag is set.
        [Dependencies] Stored first error and the same final-state rule as Store.finish.
        [Impact] A discarded stream ACK or late completion cannot relabel an actual failure as user cancellation.
        """
        for error_code, outcome in (('PROCESSING_FAILED', 'failed'), ('PROCESSING_FAILED', 'complete'), ('INVALID_RESPONSE', 'cancelled')):
            with self.subTest(error_code=error_code, outcome=outcome):
                cid, jid = self.enqueue()
                running = self.store.claim('fixture-worker')
                self.store.cancel(self.owner, jid, error='Original cause', error_code=error_code)
                self.assertFalse(self.store.guard_event(jid, running['lease'])['accepted'])
                self.assertEqual(self.store.guard_finish(jid, running['lease'], outcome), 'failed')
                with self.store.db() as db:
                    row = self.store.job(jid, db)
                    self.assertEqual((row['state'], row['error'], row['error_code'], row['reserved_chars']), ('failed', 'Original cause', error_code, 0))
                    self.assertEqual(db.execute('SELECT state FROM ai_execution_guards WHERE job=?', (jid,)).fetchone()[0], 'released')

    def test_guard_finish_keeps_user_and_auth_cancellation_terminal_state(self):
        """[Role] Keeps explicit user/auth stops classified as cancellation after output is discarded.
        [Dependencies] Existing error-code policy. [Impact] Restoring failure classification does not turn user cancellation into failure.
        """
        for error_code in ('USER_CANCELLED', 'AUTH_EXPIRED', None):
            with self.subTest(error_code=error_code):
                cid, jid = self.enqueue()
                running = self.store.claim('fixture-worker')
                self.store.cancel(self.owner, jid, error='Original cancellation', error_code=error_code)
                self.assertEqual(self.store.guard_finish(jid, running['lease'], 'complete'), 'cancelled')
                with self.store.db() as db:
                    row = self.store.job(jid, db)
                    self.assertEqual((row['state'], row['error'], row['error_code']), ('cancelled', 'Original cancellation', error_code or 'USER_CANCELLED'))

    def test_guard_finish_unknown_then_known_preserves_failure_without_reopening_released_guard(self):
        """[Role] Holds unknown failures and preserves their actual terminal state across late report retries.
        [Dependencies] Content-free lease plus first error. [Impact] Completion releases one group once and never reopens it.
        """
        cid, jid = self.enqueue()
        running = self.store.claim('fixture-worker')
        self.store.cancel(self.owner, jid, error='Original maintenance cause', error_code='PROCESSING_FAILED')
        self.assertEqual(self.store.guard_finish(jid, running['lease'], 'recovery_required'), 'recovery_required')
        other, other_jid = self.enqueue()
        self.assertIsNone(self.store.claim('waiting-worker'))
        self.assertEqual(self.store.guard_finish(jid, running['lease'], 'complete'), 'failed')
        self.assertEqual(self.store.claim('waiting-worker')['id'], other_jid)
        self.assertEqual(self.store.guard_finish(jid, running['lease'], 'recovery_required'), 'failed')
        with self.store.db() as db:
            row = self.store.job(jid, db)
            self.assertEqual((row['state'], row['error'], row['error_code']), ('failed', 'Original maintenance cause', 'PROCESSING_FAILED'))
            self.assertEqual(db.execute('SELECT state FROM ai_execution_guards WHERE job=?', (jid,)).fetchone()[0], 'released')

    def test_operator_ack_can_release_detached_unknown_guard(self):
        """[Role] Confirms explicit own-request recovery after purge. [Dependencies] Trusted method boundary. [Impact] No timeout unlock."""
        cid, jid = self.enqueue()
        running = self.store.claim('fixture-worker')
        self.operation(cid, 'trash', 0)
        self.operation(cid, 'purge', 1)
        self.store.guard_finish(jid, running['lease'], 'recovery_required')
        self.store.acknowledge_finished(jid)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT state FROM ai_execution_guards WHERE job=?', (jid,)).fetchone()[0], 'released')

    def test_purge_clears_dependencies_charges_once_and_preserves_independent_tables(self):
        """[Role] Checks exact message/handoff/draft accounting and dependency deletion. [Dependencies] One AI transaction. [Impact] Settings/audit/revocations remain."""
        cid, jid = self.enqueue(content='question')
        job = self.store.claim('fixture-worker')
        self.store.append(jid, job['lease'], reasoning='reason', content='answer')
        with self.store.db(True) as db:
            db.execute('INSERT INTO ai_task_drafts VALUES(?,1,?,1,?)', (cid, 'draft-data', time.time()))
            db.execute('UPDATE jobs SET handoff_chars=7 WHERE id=?', (jid,))
            db.execute('UPDATE storage_accounts SET used_chars=used_chars+17 WHERE owner=2 AND account_key=?', (self.account,))
            db.execute('INSERT INTO ai_selection_events(conversation,selection,level,revision,created) VALUES(?,NULL,\'medium\',1,?)', (cid, time.time()))
            db.execute("INSERT INTO revocations VALUES('kept-revocation',1)")
            db.execute('CREATE TABLE ai_audit_artifacts(id TEXT PRIMARY KEY,content TEXT)')
            db.execute("INSERT INTO ai_audit_artifacts VALUES('kept-audit','preserved by separate audit policy')")
        self.operation(cid, 'trash', 0)
        operation_id = uuid.uuid4().hex
        result = self.operation(cid, 'purge', 1, operation_id)
        self.assertTrue(result['purged'])
        self.assertTrue(self.operation(cid, 'purge', 1, operation_id)['replayed'])
        with self.store.db() as db:
            for table in ('conversations', 'jobs', 'messages', 'message_steps', 'proposals', 'ai_task_drafts', 'ai_selection_events'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0, table)
            self.assertEqual(db.execute('SELECT used_chars FROM storage_accounts').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_audit_artifacts').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM revocations').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_resource_groups').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_lifecycle_tombstones').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_lifecycle_operations WHERE purged=1').fetchone()[0], 1)

    def test_failed_purge_rolls_back_content_ledger_and_operation_receipt(self):
        """[Role] Forces a real FK-order deletion failure. [Dependencies] SQLite trigger. [Impact] No false successful purge."""
        cid, jid = self.enqueue()
        self.operation(cid, 'trash', 0)
        before = self.store.storage_status(2, self.account)
        operation_id = uuid.uuid4().hex
        with self.store.db(True) as db:
            db.execute("CREATE TRIGGER reject_test_purge BEFORE DELETE ON messages BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.operation(cid, 'purge', 1, operation_id)
        self.assertEqual(self.store.storage_status(2, self.account), before)
        with self.store.db() as db:
            self.assertIsNotNone(db.execute('SELECT 1 FROM jobs WHERE id=?', (jid,)).fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM ai_lifecycle_operations WHERE operation_id=?', (operation_id,)).fetchone())
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_lifecycle_tombstones').fetchone()[0], 0)

    def test_stale_gc_candidate_cannot_delete_restored_or_retrashed_conversation(self):
        """[Role] Rechecks old scan revisions at the writer. [Dependencies] Saved synthetic candidate. [Impact] New 30-day window preserved."""
        cid = self.new_conversation()
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now):
            self.operation(cid, 'trash', 0)
        with self.store.db() as db:
            candidate = dict(db.execute('SELECT id,lifecycle_revision,purge_after FROM conversations WHERE id=?', (cid,)).fetchone())
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now + 10):
            self.operation(cid, 'restore', 1)
            self.operation(cid, 'trash', 2)
        with self.store.db(True) as db:
            self.assertFalse(self.store._purge_candidate(db, candidate, self.now + RETENTION_SECONDS + 1))
        self.assertEqual(self.store.snapshot(2, cid, self.account, view='trash')['conversation']['lifecycle_revision'], 3)

    def test_cleanup_batch_is_bounded_and_next_run_catches_up(self):
        """[Role] Exercises indexed bounded catch-up. [Dependencies] Fake expiry clock. [Impact] Work never grows unbounded per timer run."""
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now):
            for _ in range(5):
                self.operation(self.new_conversation(), 'trash', 0)
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now + RETENTION_SECONDS):
            first = self.store.purge_expired(batch_size=2, max_batches=1)
            self.assertEqual(first, {'purged': 2, 'batches': 1, 'more_expired': True})
            self.assertEqual(self.store.purge_expired(batch_size=2, max_batches=3)['purged'], 3)

    def test_confirm_gate_serializes_trash_after_entered_business_operation(self):
        """[Role] Runs actual competing AI writers around a fake business commit. [Dependencies] Two threads/events. [Impact] Gate ordering is concrete."""
        cid = self.new_conversation()
        entered, allow_commit, trash_attempted = threading.Event(), threading.Event(), threading.Event()
        outcomes = []

        def confirm():
            """[Role] Emulates a short entered business transaction. [Dependencies] Same AI gate. [Impact] No real equipment write."""
            with self.store.execution_gate(2, cid, self.account) as db:
                entered.set()
                self.assertTrue(allow_commit.wait(3))
                db.execute("INSERT INTO revocations VALUES('synthetic-business-commit-marker',1)")
                outcomes.append('confirmed')

        def trash():
            """[Role] Attempts concurrent lifecycle entry. [Dependencies] Competing writer. [Impact] Waits for prior commit."""
            self.assertTrue(entered.wait(3))
            trash_attempted.set()
            self.operation(cid, 'trash', 0)
            outcomes.append('trashed')

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(confirm), pool.submit(trash)
            self.assertTrue(trash_attempted.wait(3))
            self.assertFalse(second.done())
            allow_commit.set()
            first.result(timeout=5)
            second.result(timeout=5)
        self.assertEqual(outcomes, ['confirmed', 'trashed'])
        self.error_status(404, lambda: self._try_enter_gate(cid))

    def _try_enter_gate(self, cid):
        """[Role] Exercises rejected post-trash business entry. [Dependencies] Store gate. [Impact] No mutation allowed."""
        with self.store.execution_gate(2, cid, self.account):
            self.fail('trashed conversation entered business gate')

    def test_pure_probe_hidden_and_mixed_chat_history_preserved_without_probe_rows(self):
        """[Role] Separates diagnostic rows by purpose. [Dependencies] Real jobs purpose field. [Impact] Titles never decide visibility."""
        pure, pure_job = self.enqueue(content='Diagnostic nonce')
        mixed, mixed_job = self.enqueue(content='Normal question')
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET state='done',purpose='probe' WHERE id=?", (pure_job,))
            db.execute("UPDATE jobs SET state='done' WHERE id=?", (mixed_job,))
        _, probe_job = self.enqueue(mixed, content='Mixed diagnostic nonce')
        with self.store.db(True) as db:
            db.execute("UPDATE jobs SET state='done',purpose='probe' WHERE id=?", (probe_job,))
        ids = {r['id'] for r in self.store.conversations(2, self.account)['conversations']}
        self.assertNotIn(pure, ids)
        self.assertIn(mixed, ids)
        snapshot = self.store.snapshot(2, mixed, self.account)
        self.assertIn('Normal question', [m['content'] for m in snapshot['messages']])
        self.assertNotIn('Mixed diagnostic nonce', [m['content'] for m in snapshot['messages']])
        self.error_status(409, lambda: self.store.snapshot(2, pure, self.account))
        self.error_status(409, lambda: self.enqueue(pure))

    def test_mutation_rate_cap_keeps_existing_operation_replay_available(self):
        """[Role] Bounds new operation ledger admissions. [Dependencies] Owner/time index. [Impact] Reliable retries remain usable."""
        cid, operation_id = self.new_conversation(), uuid.uuid4().hex
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now):
            self.operation(cid, 'trash', 0, operation_id)
            for _ in range(59):
                self.operation(cid, 'trash', 1)
            self.error_status(429, lambda: self.operation(cid, 'trash', 1))
            self.assertTrue(self.operation(cid, 'trash', 0, operation_id)['replayed'])

    def test_offline_restore_reconciles_latest_deletion_ledger_without_resurrection(self):
        """[Role] Restores an older synthetic backup then reapplies retained deletions. [Dependencies] SQLite online backup. [Impact] Purged text stays unavailable."""
        cid, _ = self.enqueue(content='do not resurrect this text')
        other = self.new_conversation(owner=3, account='synthetic-account-three')
        backup_path = Path(self.tmp.name) / 'restored.sqlite3'
        with self.store.db() as source:
            destination = sqlite3.connect(backup_path)
            source.backup(destination)
            destination.close()
        self.operation(cid, 'trash', 0)
        operation_id = uuid.uuid4().hex
        self.operation(cid, 'purge', 1, operation_id)
        ledger = self.store.export_deletion_ledger()
        self.assertEqual(set(ledger['tombstones'][0]), {'conversation', 'owner', 'account_key', 'lifecycle_revision', 'operation_id', 'purged_at'})
        self.assertNotIn('do not resurrect', str(ledger))
        restored = Store(backup_path, epoch='new-synthetic-restored-epoch')
        result = restored.reconcile_deletion_ledger(ledger)
        self.assertEqual(result, {'reconciled': 1, 'purged_restored': 1})
        self.assertEqual(restored.reconcile_deletion_ledger(ledger)['purged_restored'], 0)
        self.assertTrue(restored.lifecycle(2, cid, self.account, 'purge', 1, operation_id)['replayed'])
        with restored.db() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM conversations WHERE id=?', (cid,)).fetchone())
            self.assertIsNotNone(db.execute('SELECT 1 FROM conversations WHERE id=?', (other,)).fetchone())
            self.assertEqual(db.execute('SELECT used_chars FROM storage_accounts WHERE owner=2').fetchone()[0], 0)

    def test_restore_ledger_rejects_owner_account_revision_and_duplicate_identity_collisions(self):
        """[Role] Checks closed offline deletion metadata before any mutation. [Dependencies] Synthetic import. [Impact] Foreign/current content preserved on rejection."""
        cid = self.new_conversation()
        item = {'conversation': cid, 'owner': 2, 'account_key': self.account, 'lifecycle_revision': 2,
                'operation_id': uuid.uuid4().hex, 'purged_at': self.now}
        for replacement in ({'owner': 3}, {'account_key': 'reused-account'}, {'lifecycle_revision': 0}, {'lifecycle_revision': True}, {'purged_at': float('nan')}, {'title': 'forbidden body field'}):
            candidate = {**item, **replacement}
            with self.assertRaises(ValueError):
                self.store.reconcile_deletion_ledger({'format': 'assistant-deletion-ledger-v1', 'tombstones': [candidate]})
        with self.assertRaises(ValueError):
            self.store.reconcile_deletion_ledger({'format': 'assistant-deletion-ledger-v1', 'tombstones': [item, item]})
        with self.store.db() as db:
            self.assertIsNotNone(db.execute('SELECT 1 FROM conversations WHERE id=?', (cid,)).fetchone())

    def test_restore_export_includes_expired_rows_even_before_gc_has_collected_them(self):
        """[Role] Exports logical expiry even during a delayed cleanup cycle. [Dependencies] Server-clock predicate. [Impact] Old backups cannot revive expired trash."""
        cid = self.new_conversation()
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now):
            self.operation(cid, 'trash', 0)
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=self.now + RETENTION_SECONDS):
            ledger = self.store.export_deletion_ledger()
        self.assertEqual(ledger['tombstones'][0]['conversation'], cid)
        self.assertEqual(ledger['tombstones'][0]['lifecycle_revision'], 2)
        self.assertEqual(ledger['tombstones'][0]['purged_at'], self.now + RETENTION_SECONDS)
        with self.store.db() as db:
            self.assertIsNotNone(db.execute('SELECT 1 FROM conversations WHERE id=?', (cid,)).fetchone())

    def test_detached_guard_still_counts_toward_owner_admission(self):
        """[Role] Includes detached unknown work in existing owner admission caps. [Dependencies] Minimal guard identity. [Impact] Purge cannot bypass queue limits."""
        cid, jid = self.enqueue()
        self.store.claim('fixture-worker')
        self.operation(cid, 'trash', 0)
        self.operation(cid, 'purge', 1)
        self.enqueue()
        self.error_status(429, lambda: self.enqueue())

    def test_normal_plus_trash_count_keeps_the_200_conversation_limit(self):
        """[Role] Keeps trash in the existing retention count. [Dependencies] Explicit purge. [Impact] Moving alone frees no quota."""
        ids = [self.new_conversation() for _ in range(200)]
        self.operation(ids[0], 'trash', 0)
        self.error_status(429, lambda: self.new_conversation())
        self.operation(ids[0], 'purge', 1)
        self.assertTrue(self.new_conversation())

    def test_cross_conversation_message_reference_aborts_purge_without_deleting_foreign_content(self):
        """[Role] Rejects malformed non-FK message job links. [Dependencies] Purge preflight. [Impact] Foreign ledger/content untouched."""
        cid, jid = self.enqueue()
        other = self.new_conversation(owner=3, account='synthetic-account-three')
        with self.store.db(True) as db:
            db.execute("INSERT INTO messages(conversation,job,role,content,created) VALUES(?,?,'assistant','foreign-content',?)", (other, jid, time.time()))
            db.execute('UPDATE storage_accounts SET used_chars=15 WHERE owner=3')
        self.operation(cid, 'trash', 0)
        with self.assertRaises(ValueError):
            self.operation(cid, 'purge', 1)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT content FROM messages WHERE conversation=?', (other,)).fetchone()[0], 'foreign-content')
            self.assertEqual(db.execute('SELECT used_chars FROM storage_accounts WHERE owner=3').fetchone()[0], 15)


@unittest.skipUnless(os.name == 'posix', 'Linux-only isolated retention CLI fixtures')
class RetentionCliTests(unittest.TestCase):
    """[Role] Tests the actual cleanup CLI in memory. [Dependencies] Parent-packed candidate source. [Impact] No installed tool execution."""

    def setUp(self):
        """[Role] Loads the candidate CLI and creates a synthetic v4 DB. [Dependencies] Memory source and tempdir. [Impact] No server files touched."""
        self.tmp = tempfile.TemporaryDirectory(prefix='eq-ai-retention-cli-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'assistant.sqlite3'
        self.epoch = 'synthetic-retention-cli-epoch'
        self.store = Store(self.path, epoch=self.epoch)
        source = globals().get('CANDIDATE_FILES', {}).get('tools/ai_retention_cleanup.py')
        self.assertIsNotNone(source, 'Linux runner must pack the reviewed retention CLI source')
        self.cli = types.ModuleType('synthetic_retention_cli')
        self.cli.__file__ = str(self.root / 'tools' / 'ai_retention_cleanup.py')
        previous_path = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), previous_path))
        exec(compile(source, self.cli.__file__, 'exec'), self.cli.__dict__)

    def run_cli(self, *args):
        """[Role] Captures structured maintenance output. [Dependencies] Real candidate main(). [Impact] No shell/SSH/model call."""
        output = io.StringIO()
        with redirect_stdout(output):
            code = self.cli.main(['--database', str(self.path), '--epoch', self.epoch, *args])
        return code, json.loads(output.getvalue())

    def test_timer_cli_refuses_v3_before_constructing_store_or_running_ddl(self):
        """[Role] Proves the timer cannot activate a migration. [Dependencies] Read-only version check. [Impact] Partial deployment fails closed."""
        with self.store.db(True) as db:
            db.execute('UPDATE ai_meta SET version=3')
        with patch.object(self.cli, 'Store', side_effect=AssertionError('must not migrate')) as constructor:
            code, result = self.run_cli()
        self.assertEqual((code, result['status']), (1, 'failed'))
        constructor.assert_not_called()
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT version FROM ai_meta').fetchone()[0], 3)

    def test_real_flock_prevents_second_cleanup_and_releases_after_exit(self):
        """[Role] Exercises actual Linux advisory-lock contention. [Dependencies] Two separate descriptors. [Impact] Single cleanup process enforced."""
        lock = self.path.with_name(self.path.name + '.retention.lock')
        with self.cli.cleanup_lock(lock) as acquired:
            self.assertTrue(acquired)
            code, result = self.run_cli()
            self.assertEqual((code, result['status']), (0, 'already_running'))
        code, result = self.run_cli()
        self.assertEqual((code, result['status']), (0, 'ok'))

    def test_cli_runs_bounded_expiration_without_model_or_login(self):
        """[Role] Runs the cleanup command on actual expired synthetic rows. [Dependencies] Fake UTC and Store. [Impact] Independent bounded catch-up."""
        now = 1800000000.0
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=now):
            for _ in range(2):
                cid = self.store.create_conversation(2, 'synthetic-account')
                self.store.lifecycle(2, cid, 'synthetic-account', 'trash', 0, uuid.uuid4().hex)
        with patch('utils.ai_assistant.lifecycle.time.time', return_value=now + RETENTION_SECONDS):
            code, result = self.run_cli('--batch-size', '1', '--max-batches', '1')
        self.assertEqual((code, result['purged'], result['more_expired']), (0, 1, True))

    def test_cli_exports_only_content_free_ledger_and_rejects_duplicate_json_keys(self):
        """[Role] Exercises real export and closed JSON import. [Dependencies] Private temporary ledger. [Impact] No ambiguous identity or copied chat content."""
        cid = self.store.create_conversation(2, 'synthetic-account')
        self.store.lifecycle(2, cid, 'synthetic-account', 'trash', 0, uuid.uuid4().hex)
        self.store.lifecycle(2, cid, 'synthetic-account', 'purge', 1, uuid.uuid4().hex)
        code, ledger = self.run_cli('--export-deletions')
        self.assertEqual((code, ledger['format']), (0, 'assistant-deletion-ledger-v1'))
        self.assertEqual(ledger['tombstones'][0]['conversation'], cid)
        path = self.root / 'malformed-ledger.json'
        path.write_text('{"format":"assistant-deletion-ledger-v1","format":"ambiguous","tombstones":[]}', encoding='utf-8')
        os.chmod(path, 0o600)
        code, result = self.run_cli('--reconcile-deletions', str(path))
        self.assertEqual((code, result['status']), (1, 'failed'))


if __name__ == '__main__':
    unittest.main()
