"""[MINI-COMMENT: ASSISTANT.UPGRADE.IDLE.TESTS]
[EN rev.1]
[Role] Exercises the real release idle query and both pause gates against disposable SQLite fixtures.
[Dependencies] AST-selected helper functions, Python stdlib and mocked process/filesystem/service operations; no Flask/app/helper top-level import.
[Impact] Purged active work blocks deployment, consistent snapshots do not double-count guards and the existing state-count/success response contracts remain intact without any production operation.
"""
import ast
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call


def helper_source():
    """[Role] Reads the reviewed candidate string in the Linux runner or the local staged/merged source in standalone pure tests."""
    if 'CANDIDATE_FILES' in globals():
        source = CANDIDATE_FILES.get('tools/deploy_ai_ux_release.py')
        if not isinstance(source, str):
            raise ValueError('release guard tests require tools/deploy_ai_ux_release.py in CANDIDATE_FILES')
        return source
    root = Path(__file__).resolve().parents[1]
    candidate = root / 'tools/deploy_ai_ux_release.py'
    if not candidate.is_file():
        candidate = root / 'Staging/20261105-ai-polish/tools/deploy_ai_ux_release.py'
    return candidate.read_text(encoding='utf-8-sig')


def load_guard_functions(database):
    """[Role] Compiles only ACTIVE/active_jobs/pause, excluding imports, CLI, credentials and application startup."""
    tree = ast.parse(helper_source(), filename='<candidate-release-helper>')
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ('active_jobs', 'pause')
                or isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'ACTIVE' for target in node.targets)]
    if len(selected) != 3:
        raise ValueError('reviewed release helper extraction boundary changed')
    namespace = {'sqlite3': sqlite3, 'AI': database, 'json': json}
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<release-guard-only>', 'exec'), namespace)
    return namespace


class ReleaseGuardTests(unittest.TestCase):
    """[Role] Verifies true idle admission with real SQL and no real process/service/file mutation."""

    def setUp(self):
        """[Role] Creates only synthetic jobs/guards in a private temporary test directory."""
        self.temporary = tempfile.TemporaryDirectory(prefix='eq-release-guard-')
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / 'assistant.sqlite3'
        with closing(sqlite3.connect(self.database)) as db, db:
            db.executescript('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT NOT NULL);'
                             'CREATE TABLE ai_execution_guards(job TEXT PRIMARY KEY,state TEXT NOT NULL);')
        self.helper = load_guard_functions(self.database)

    def rows(self, jobs=(), guards=()):
        """[Role] Inserts synthetic state pairs without using any application or deployment API."""
        with closing(sqlite3.connect(self.database)) as db, db:
            db.executemany('INSERT INTO jobs(id,state) VALUES(?,?)', jobs)
            db.executemany('INSERT INTO ai_execution_guards(job,state) VALUES(?,?)', guards)

    def pause_context(self, sleep_hook=None):
        """[Role] Replaces every external effect reachable from the extracted pause function with an observable mock."""
        helper = self.helper
        helper.update({
            'ROOT': Path(self.temporary.name) / 'synthetic-project',
            'MAINTENANCE': SimpleNamespace(exists=lambda: False),
            'process': Mock(return_value=(SimpleNamespace(exists=lambda: False), ['synthetic-python', '-u', 'app.py'], {})),
            'save': Mock(), 'record': Mock(), 'maintenance': Mock(), 'snapshot': Mock(),
            'time': SimpleNamespace(sleep=Mock(side_effect=sleep_hook)),
            'subprocess': SimpleNamespace(run=Mock()), 'os': SimpleNamespace(kill=Mock()),
            'signal': SimpleNamespace(SIGTERM=15),
        })
        return helper

    def no_stop(self):
        """[Role] Asserts a failed gate never reaches even the mocked service stop, signal or quiesced snapshot."""
        self.helper['subprocess'].run.assert_not_called()
        self.helper['os'].kill.assert_not_called()
        self.helper['snapshot'].assert_not_called()

    def test_empty_database_returns_existing_idle_shape(self):
        """[Role] Preserves the original empty dict contract for a genuinely idle assistant."""
        self.assertEqual(self.helper['active_jobs'](), {})

    def test_terminal_jobs_and_released_orphan_guards_are_idle(self):
        """[Role] Completed/cancelled/confirmation work and released guards do not block a legitimate release."""
        self.rows(jobs=[('done', 'done'), ('failed', 'failed'), ('cancelled', 'cancelled'), ('confirm', 'waiting_confirmation')],
                  guards=[('done', 'released'), ('removed-finished-job', 'released')])
        self.assertEqual(self.helper['active_jobs'](), {})

    def test_queued_jobs_keep_the_existing_state_count_shape(self):
        """[Role] A queued own request still blocks admission and uses the old state-to-integer response."""
        self.rows(jobs=[('queued-1', 'queued'), ('queued-2', 'queued')])
        self.assertEqual(self.helper['active_jobs'](), {'queued': 2})
        helper = self.pause_context()
        with self.assertRaisesRegex(ValueError, 'existing assistant work must finish normally'):
            helper['pause'](Path(self.temporary.name) / 'release', 123)
        helper['process'].assert_not_called()
        helper['maintenance'].assert_not_called()
        self.no_stop()

    def test_mixed_jobs_and_orphan_guards_aggregate_without_double_counting_linked_guards(self):
        """[Role] Counts each live operation once while adding jobs whose content was purged through their surviving guard."""
        self.rows(jobs=[('q', 'queued'), ('r', 'running'), ('d', 'draining'), ('u', 'recovery_required')],
                  guards=[('r', 'running'), ('d', 'draining'), ('u', 'recovery_required'),
                          ('orphan-r1', 'running'), ('orphan-r2', 'running'), ('orphan-d', 'draining'),
                          ('orphan-u', 'recovery_required'), ('orphan-finished', 'released')])
        result = self.helper['active_jobs']()
        self.assertEqual(result, {'queued': 1, 'running': 3, 'draining': 2, 'recovery_required': 2})
        self.assertTrue(all(isinstance(count, int) for count in result.values()))

    def test_each_active_orphan_state_blocks_before_any_pause_effect(self):
        """[Role] jobs=0 plus an orphan running/draining/recovery guard cannot stop a service or write release files."""
        for state in ('running', 'draining', 'recovery_required'):
            with self.subTest(state=state):
                with closing(sqlite3.connect(self.database)) as db, db:
                    db.execute('DELETE FROM ai_execution_guards')
                self.rows(guards=[('purged-job', state)])
                helper = self.pause_context()
                self.assertEqual(helper['active_jobs'](), {state: 1})
                with self.assertRaisesRegex(ValueError, 'existing assistant work must finish normally'):
                    helper['pause'](Path(self.temporary.name) / 'release', 123)
                helper['process'].assert_not_called()
                helper['save'].assert_not_called()
                helper['record'].assert_not_called()
                helper['maintenance'].assert_not_called()
                self.no_stop()

    def test_orphan_arriving_after_maintenance_is_blocked_by_second_gate(self):
        """[Role] Rechecks surviving own work after closing admissions and restores NORMAL without stopping anything."""
        def arrive_after_gate(seconds):
            """[Role] Simulates a request purged during the helper's existing two-second admission settling window."""
            self.assertEqual(seconds, 2)
            self.rows(guards=[('new-purged-request', 'draining')])

        helper = self.pause_context(arrive_after_gate)
        with self.assertRaisesRegex(ValueError, 'work arrived before admission gate; no process stopped'):
            helper['pause'](Path(self.temporary.name) / 'release', 123)
        self.assertEqual(helper['maintenance'].call_args_list, [call('RESTORING'), call('NORMAL')])
        helper['process'].assert_called_once_with(123)
        helper['time'].sleep.assert_called_once_with(2)
        self.no_stop()

    def test_true_idle_pause_keeps_existing_success_response(self):
        """[Role] A real idle result still reaches only mocked owned stop operations and returns the legacy quiesced shape."""
        self.rows(jobs=[('finished', 'done')], guards=[('finished', 'released'), ('purged-finished', 'released')])
        helper = self.pause_context()
        release = Path(self.temporary.name) / 'release'
        result = helper['pause'](release, 123)
        self.assertEqual(result, {'status': 'quiesced', 'old_pid': 123, 'active_jobs': 0, 'shared_model_controlled': False})
        helper['subprocess'].run.assert_called_once_with(['systemctl', '--user', 'stop', 'equipment-ai-worker.service'], check=True, timeout=35)
        helper['os'].kill.assert_called_once_with(123, 15)
        self.assertEqual(helper['process'].call_args_list, [call(123), call(123)])
        self.assertEqual(helper['snapshot'].call_count, 2)
        helper['maintenance'].assert_called_once_with('RESTORING')

    def test_missing_guard_schema_fails_closed_before_any_pause_effect(self):
        """[Role] A damaged/non-v4 guard schema cannot be mistaken for an idle server."""
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('DROP TABLE ai_execution_guards')
        helper = self.pause_context()
        with self.assertRaises(sqlite3.OperationalError):
            helper['pause'](Path(self.temporary.name) / 'release', 123)
        helper['process'].assert_not_called()
        helper['maintenance'].assert_not_called()
        self.no_stop()

    def test_idle_read_uses_one_explicit_read_only_transaction(self):
        """[Role] Verifies the fixed mode=ro connection and that all state reads share an explicit transaction."""
        self.rows(guards=[('orphan', 'running')])
        events, connections = [], []
        real_connect = sqlite3.connect

        class ObservedConnection(sqlite3.Connection):
            """[Role] Observes transaction state before each real SELECT without replacing SQL results."""
            def execute(connection, sql, parameters=()):
                """[Role] Records actual read transaction membership and delegates to SQLite."""
                if sql.lstrip().upper().startswith('SELECT'):
                    events.append(connection.in_transaction)
                return super().execute(sql, parameters)

        def observe(*args, **kwargs):
            """[Role] Opens the real disposable DB with only a transaction-observing connection subclass."""
            connections.append((args, kwargs))
            return real_connect(*args, **kwargs, factory=ObservedConnection)

        self.helper['sqlite3'] = SimpleNamespace(connect=observe)
        self.assertEqual(self.helper['active_jobs'](), {'running': 1})
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0], ((self.database.as_uri() + '?mode=ro',), {'uri': True}))
        self.assertTrue(events)
        self.assertTrue(all(events), 'every jobs/guard read must belong to the same explicit transaction')

    def test_purge_committing_during_idle_read_cannot_double_count_the_operation(self):
        """[Role] A concurrent WAL writer can remove job content while the reader retains one coherent jobs/guard snapshot."""
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('PRAGMA journal_mode=WAL')
        self.rows(jobs=[('live', 'running')], guards=[('live', 'running')])
        real_connect = sqlite3.connect
        wrote = []
        database = self.database

        class PurgeAfterRead(sqlite3.Connection):
            """[Role] Commits a separate synthetic writer after the reader establishes its first state snapshot."""
            def execute(connection, sql, parameters=()):
                """[Role] Preserves the returned real cursor while simulating concurrent purge before any later state read."""
                cursor = super().execute(sql, parameters)
                if sql.lstrip().upper().startswith('SELECT') and not wrote:
                    with closing(real_connect(database)) as writer, writer:
                        writer.execute('DELETE FROM jobs WHERE id=?', ('live',))
                    wrote.append(True)
                return cursor

        def concurrent_reader(*args, **kwargs):
            """[Role] Substitutes only the disposable read connection; application/process code remains absent."""
            return real_connect(*args, **kwargs, factory=PurgeAfterRead)

        self.helper['sqlite3'] = SimpleNamespace(connect=concurrent_reader)
        self.assertEqual(self.helper['active_jobs'](), {'running': 1})
        self.assertEqual(wrote, [True])
        with closing(real_connect(self.database)) as db, db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 0)
        self.assertEqual(self.helper['active_jobs'](), {'running': 1}, 'the subsequent snapshot sees the same operation as one orphan guard')


if __name__ == '__main__':
    unittest.main()
