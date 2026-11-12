"""Read-only, row-by-row reconciliation after the service switch and real browser turn."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from activate_release import AI, DB, ROOT, TARGET, WORKER, digest_rows, git, run, web_pids


def ident(name):
    return '"' + name.replace('"', '""') + '"'


def file_hash(path):
    with path.open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
        return digest.hexdigest()


def table_counts(db, table):
    quoted = ident(table)
    old = list(db.execute(f'PRAGMA historical.table_info({quoted})'))
    live = list(db.execute(f'PRAGMA main.table_info({quoted})'))
    assert old == live and old, f'changed schema: {table}'
    keys = [c[1] for c in sorted(old, key=lambda c: c[5]) if c[5]] or ['rowid']
    on = ' AND '.join(f'v.{ident(k)} IS o.{ident(k)}' for k in keys)
    null_key = f'v.{ident(keys[0])} IS NULL'
    equal = ' AND '.join(f'(typeof(v.{ident(c[1])})=typeof(o.{ident(c[1])}) AND '
                         f'v.{ident(c[1])} COLLATE BINARY IS o.{ident(c[1])} COLLATE BINARY)' for c in old)
    query = (f'SELECT COUNT(*), COALESCE(SUM({null_key}), 0), '
             f'COALESCE(SUM(CASE WHEN {null_key} THEN 0 WHEN {equal} THEN 0 ELSE 1 END),0) '
             f'FROM historical.{quoted} o LEFT JOIN main.{quoted} v ON {on}')
    historical, missing, different = db.execute(query).fetchone()
    assert missing == different == 0, f'history mismatch: {table}: {missing}/{different}'
    total = db.execute(f'SELECT COUNT(*) FROM main.{quoted}').fetchone()[0]
    return dict(original=historical, missing=missing, changed=different, current=total)


def reconcile(release):
    assert socket.gethostname() == 'nkhst-pentium' and release.parent == ROOT/'instance/releases'
    def load(name):
        return json.loads((release/name).read_text())
    activation = load('activation.json')
    backup = load('backup.json')['backup']
    assert activation['status'] == 'active'
    git('merge-base','--is-ancestor',TARGET,'HEAD')
    changes = git('diff','--name-only',TARGET,'HEAD').splitlines()
    evidence_prefixes = ('Plans/2026/11/12/003_Access_Log_Production',
                         'Tasks/2026/11/12/003_Access_Log_Production',
                         'Reports/2026/11/12/003_Access_Log_Production')
    assert all(name.startswith(evidence_prefixes) for name in changes), 'deployed source changed since verification'
    report = {'status':'pass','commit':TARGET,'verified_utc':datetime.now(timezone.utc).isoformat(),
              'real_ai_test_at_comparison':load('live-ai.json')['status'] if (release/'live-ai.json').exists() else 'pending'}
    tables = {'equipment': ('access_logs', 'audit_logs', 'equipments'),
              'assistant': ('conversations', 'messages', 'jobs', 'proposals', 'message_steps', 'ai_audit_artifacts')}
    for label, current in [('equipment', DB), ('assistant', AI)]:
        snapshot = release/(label+'.snapshot.sqlite3')
        assert file_hash(snapshot) == backup[label]['sha256'], 'backup file changed'
        with closing(sqlite3.connect(current.as_uri()+'?mode=ro', uri=True, timeout=15)) as db:
            db.execute('ATTACH DATABASE ? AS historical', (snapshot.as_uri()+'?mode=ro&immutable=1',))
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            tracked = {}
            for table in tables[label]:
                if not db.execute("SELECT 1 FROM historical.sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                    assert table == 'ai_audit_artifacts'
                    tracked[table] = {'original_table_present':False}
                else:
                    tracked[table] = table_counts(db, table)
            report[label] = tracked
            if label == 'equipment':
                lo, hi = activation['initial_bound'], activation['previous_web_last_bound']
                digest = digest_rows(db.execute('SELECT * FROM access_logs WHERE LogId>? AND LogId<=? ORDER BY LogId',
                                                (lo, hi)))
                assert digest == activation['old_log_tail']
                older = db.execute('SELECT COUNT(*) FROM access_logs WHERE LogId<=?', (hi,)).fetchone()[0]
                assert older == tracked['access_logs']['original'] + digest['rows']
                added = db.execute('SELECT COUNT(*) FROM access_logs WHERE LogId>?', (hi,)).fetchone()[0]
                assert added > 0
                deletion_actions = db.execute("SELECT COUNT(*) FROM main.audit_logs WHERE "
                                              "AuditId>(SELECT MAX(AuditId) FROM historical.audit_logs) "
                                              "AND Action IN ('CLEANUP_ACCESS_LOGS_START','CLEANUP_ACCESS_LOGS')").fetchone()[0]
                assert deletion_actions == 0
                report.update(backup_file_hashes_match=True, old_process_postbackup_rows=digest['rows'],
                              old_process_postbackup_digest_matches=True, all_rows_through_cutover=older,
                              new_web_rows=added, live_cleanup_receipts=deletion_actions)
            db.rollback()
    assert web_pids() == [activation['web_new_pid']]
    assert run('systemctl','--user','is-active',WORKER) == 'active'
    assert int(run('systemctl','--user','show',WORKER,'--property=MainPID','--value')) == activation['worker_pid']
    report.update(web_and_original_worker_healthy=True)
    (release/'preservation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    os.umask(0o077)
    reconcile(Path(sys.argv[1]).resolve())
