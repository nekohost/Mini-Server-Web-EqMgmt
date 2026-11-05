#!/usr/bin/env python3
"""[MINI-COMMENT: ASSISTANT.UPGRADE.RELEASE]
[EN rev.5]
[Role] Upgrades the installed equipment assistant using private snapshots and an exact Git release.
[Dependencies] The fixed Linux host/user/project, existing private settings and the reviewed v4 candidate.
[Impact] Stops only an idle local web/worker pair after snapshot-consistent jobs/orphan-guard gates; preserves secrets, business rows and every pre-existing AI row.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import time
import types
import urllib.error
import urllib.request

from dotenv import dotenv_values

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
CONFIG = Path('/home/nekohost/.config/eqmgmt/assistant-worker.env')
AI = ROOT / 'instance/ai/assistant.sqlite3'
MAINTENANCE = ROOT / 'instance/maintenance-state.json'
UNIT = Path('/home/nekohost/.config/systemd/user')
ACTIVE = ('queued', 'running', 'draining', 'recovery_required')


def save(path, content):
    """[Role] Creates one private result/backup exclusively. [Dependencies] No-follow0600 descriptor. [Impact] No overwrite or secret output."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def record(path, data):
    """[Role] Persists a release result. [Dependencies] Private save. [Impact] Keeps explicit phase evidence without replacing earlier results."""
    save(path, json.dumps(data, ensure_ascii=False, indent=2).encode())


def atomic(path, content, mode=0o600):
    """[Role] Replaces one verified runtime file. [Dependencies] Private sibling and canonical owner path. [Impact] Never follows a final symlink."""
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            raise PermissionError('runtime file must be an owned regular file')
    pending = path.with_name(path.name + '.release-' + secrets.token_hex(6))
    save(pending, content)
    os.chmod(pending, mode)
    os.replace(pending, path)


def values(path):
    """[Role] Reads private dotenv values internally. [Dependencies] Owned0600 regular file. [Impact] Values never enter printed results."""
    info = path.lstat()
    if path.resolve() != path or not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise PermissionError('private configuration boundary mismatch')
    return {k: v for k, v in dotenv_values(path).items() if v is not None}


def snapshot(source, destination):
    """[Role] Makes an online consistent SQLite backup. [Dependencies] Read-only source and private destination. [Impact] Checks integrity/FK without printing rows."""
    save(destination, b'')
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original, sqlite3.connect(destination) as copied:
        original.backup(copied)
        if copied.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or copied.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('snapshot integrity failure')


def fingerprints(path, baseline=None, business=False):
    """[Role] Hashes original columns of every preserved table. [Dependencies] Snapshot schema or prior projection. [Impact] Only the exact menu parent/timestamp may change."""
    ignored = {'access_logs', 'audit_logs', 'auth_rate_buckets', 'sqlite_sequence'} if business else {'ai_meta'}
    result = {}
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('database integrity failure')
        tables = list(baseline) if baseline is not None else [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if r[0] not in ignored]
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            columns = baseline[table]['columns'] if baseline is not None else [r[1] for r in db.execute('PRAGMA table_info(' + quoted + ')')]
            selected = ','.join('"' + c.replace('"', '""') + '"' for c in columns)
            rows = []
            for raw in db.execute('SELECT ' + selected + ' FROM ' + quoted):
                row = list(raw)
                if business and table == 'menus' and row[columns.index('MenuCode')] == 'equipment_ai_settings':
                    for column in ('ParentMenuCode', 'UpdatedAt'):
                        row[columns.index(column)] = '<approved-menu-reparent>'
                rows.append(repr(tuple(row)))
            result[table] = {'columns': columns, 'rows': len(rows), 'sha256': hashlib.sha256('\n'.join(sorted(rows)).encode()).hexdigest()}
    return result


def active_jobs():
    """[MINI-COMMENT: ASSISTANT.UPGRADE.IDLE]
    [EN rev.1]
    [Role] Counts unfinished jobs and active execution guards whose job content was purged.
    [Dependencies] One explicit read transaction on the fixed v4 AI DB; linked guards are not counted twice.
    [Impact] Both pause gates reject orphaned running/draining/recovery work without cancelling it; the existing state-to-count mapping remains compatible.
    """
    db = sqlite3.connect(AI.as_uri() + '?mode=ro', uri=True)
    try:
        db.execute('BEGIN')
        return dict(db.execute("""SELECT state,SUM(work_count) FROM (
            SELECT state,COUNT(*) AS work_count FROM jobs WHERE state IN (?,?,?,?) GROUP BY state
            UNION ALL
            SELECT g.state,COUNT(*) AS work_count FROM ai_execution_guards g
            WHERE g.state IN ('running','draining','recovery_required')
                AND NOT EXISTS(SELECT 1 FROM jobs j WHERE j.id=g.job)
            GROUP BY g.state
        ) GROUP BY state""", ACTIVE))
    finally:
        db.close()


def audit_preserved(before, after):
    """[Role] Checks original access/audit rows as an append-only subset. [Dependencies] Read-only attached snapshot and original columns. [Impact] New release events may append but cannot hide a deleted/modified audit row."""
    with sqlite3.connect(after.as_uri() + '?mode=ro', uri=True) as db:
        db.execute('ATTACH DATABASE ? AS previous', (before.as_uri() + '?mode=ro',))
        for table in ('access_logs', 'audit_logs'):
            if not db.execute("SELECT 1 FROM previous.sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                continue
            columns = [r[1] for r in db.execute('PRAGMA previous.table_info(' + table + ')')]
            selected = ','.join('"' + c.replace('"', '""') + '"' for c in columns)
            if db.execute('SELECT ' + selected + ' FROM previous.' + table + ' EXCEPT SELECT ' + selected + ' FROM main.' + table + ' LIMIT 1').fetchone():
                raise ValueError('pre-existing audit rows changed')


def process(pid):
    """[Role] Verifies the exact owned web process. [Dependencies] Proc owner/cwd/argv. [Impact] Rejects PID reuse and unrelated services."""
    proc = Path('/proc') / str(pid)
    argv = [x.decode() for x in proc.joinpath('cmdline').read_bytes().split(b'\0') if x]
    if proc.stat().st_uid != os.geteuid() or proc.joinpath('cwd').resolve() != ROOT or argv != [str(ROOT / '.venv/bin/python'), '-u', 'app.py']:
        raise ValueError('web process identity mismatch')
    env = dict(x.decode().split('=', 1) for x in proc.joinpath('environ').read_bytes().split(b'\0') if x)
    return proc, argv, env


def maintenance(state):
    """[Role] Advances the existing public maintenance-file protocol. [Dependencies] Canonical fixed path and saved prior state. [Impact] Blocks admissions during code/DB transition."""
    previous = json.loads(MAINTENANCE.read_text()) if MAINTENANCE.exists() else {'state': 'NORMAL', 'revision': 0}
    if state == 'RESTORING' and previous['state'] != 'NORMAL':
        raise ValueError('another maintenance operation owns the server')
    data = {'state': state, 'revision': previous.get('revision', 0) + 1,
            'message': 'AI 도우미 업데이트를 적용하고 있습니다.' if state != 'NORMAL' else '',
            'expected_end_at': '', 'started_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S') if state != 'NORMAL' else '',
            'activated_by': 'release:20261105-ai-ux' if state != 'NORMAL' else ''}
    atomic(MAINTENANCE, json.dumps(data, ensure_ascii=False).encode())


def check_copy(release):
    """[MINI-COMMENT: ASSISTANT.UPGRADE.COPY]
    [EN rev.2]
    [Role] Starts the complete approved app against copies of both real databases, including legitimate existing lifecycle history.
    [Dependencies] Preserved secrets for encrypted provider records; isolated instance/DB/maintenance/file paths and disabled model discovery.
    [Impact] Compares every old AI column/row and lifecycle state with its own baseline; pre-existing trash/restores are preserved rather than assumed absent.
    """
    test = release / ('copy-' + secrets.token_hex(6))
    test.mkdir(mode=0o700)
    source_equipment = release / ('equipment-quiesced.sqlite3' if (release / 'equipment-quiesced.sqlite3').exists() else 'equipment-before.sqlite3')
    source_ai = release / ('assistant-quiesced.sqlite3' if (release / 'assistant-quiesced.sqlite3').exists() else 'assistant-before.sqlite3')
    equipment, assistant = test / 'equipment.sqlite3', test / 'assistant.sqlite3'
    snapshot(source_equipment, equipment)
    snapshot(source_ai, assistant)
    business_before, ai_before = fingerprints(equipment, business=True), fingerprints(assistant)
    lifecycle_query = 'SELECT COUNT(*) FROM conversations WHERE is_deleted<>0 OR deleted_at IS NOT NULL OR purge_after IS NOT NULL OR lifecycle_revision<>0'
    with sqlite3.connect(assistant) as db:
        lifecycle_before = db.execute(lifecycle_query).fetchone()[0]
    settings = values(ROOT / '.env')
    settings.update(values(CONFIG))
    os.environ.update(settings)
    os.environ.update(DATABASE_PATH=str(equipment), USER_AI_DATABASE=str(assistant), USER_AI_MODEL_DISCOVERY='false',
                      DATABASE_OPERATION_ROOT=str(test / 'operations'), MAINTENANCE_STATE_PATH=str(test / 'maintenance.json'),
                      EQUIPMENT_ATTACHMENT_ROOT=str(test / 'files'), PYTHONDONTWRITEBYTECODE='1')
    source = globals().get('CANDIDATE_APP_SOURCE') or (ROOT / 'app.py').read_text()
    anchor = 'app = Flask(__name__)'
    if source.count(anchor) != 1:
        raise ValueError('isolated app anchor mismatch')
    source = source.replace(anchor, 'app = Flask(__name__, root_path=' + repr(str(ROOT)) + ', instance_path=' + repr(str(test / 'instance')) + ')', 1)
    module = types.ModuleType('assistant_upgrade_copy')
    module.__file__ = str(ROOT / 'app.py')
    sys.modules[module.__name__] = module
    try:
        exec(compile(source, str(ROOT / 'app.py'), 'exec'), module.__dict__)
        module.ACCESS_LOG_ACCEPTING.clear()
        module.shutdown_event.set()
        module.logger_thread.join(timeout=5)
        if fingerprints(equipment, business_before, business=True) != business_before or fingerprints(assistant, ai_before) != ai_before:
            raise ValueError('existing database rows changed during isolated upgrade')
        audit_preserved(source_equipment, equipment)
        with sqlite3.connect(assistant) as db:
            if db.execute('SELECT version FROM ai_meta').fetchall() != [(4,)]:
                raise ValueError('copy did not activate v4')
            lifecycle_after = db.execute(lifecycle_query).fetchone()[0]
            if lifecycle_after != lifecycle_before:
                raise ValueError('existing conversation lifecycle history changed during isolated upgrade')
        with sqlite3.connect(equipment) as db:
            if db.execute("SELECT ParentMenuCode FROM menus WHERE MenuCode='equipment_ai_settings'").fetchone() != ('admin_center',):
                raise ValueError('admin menu reparent missing')
        with module.app.test_client() as client:
            statuses = {p: client.get(p).status_code for p in ('/login', '/assistant', '/admin/ai/providers', '/api/ai/capabilities')}
            statuses['/internal/ai/claim'] = client.post('/internal/ai/claim', json={}).status_code
        if statuses != {'/login': 200, '/assistant': 302, '/admin/ai/providers': 302, '/api/ai/capabilities': 401, '/internal/ai/claim': 403}:
            raise ValueError('copy authentication boundary mismatch')
        result = {'status': 'pass', 'copy': str(test), 'business_tables_preserved': len(business_before),
                  'ai_tables_preserved': len(ai_before), 'old_ai_rows': {k: v['rows'] for k, v in ai_before.items()},
                  'ai_version': 4, 'menu_parent': 'admin_center', 'anonymous_statuses': statuses,
                  'audit_rows_preserved': True, 'old_lifecycle_rows': lifecycle_before, 'lifecycle_rows_preserved': True,
                  'real_model_called': False, 'production_databases_modified': False}
        record(test / 'result.json', result)
        return result
    finally:
        if hasattr(module, 'shutdown_event'):
            module.shutdown_event.set()


def pause(release, pid):
    """[Role] Quiesces this verified idle app before pulling new templates/modules. [Dependencies] Private process/config/DB backups and current NORMAL gate. [Impact] No forced kill or shared service operation."""
    if active_jobs():
        raise ValueError('existing assistant work must finish normally before release')
    proc, argv, env = process(pid)
    save(release / 'process-environment-before.json', json.dumps(env).encode())
    record(release / 'process-before.json', {'pid': pid, 'argv': argv})
    save(release / 'maintenance-before.json', MAINTENANCE.read_bytes() if MAINTENANCE.exists() else b'null')
    maintenance('RESTORING')
    time.sleep(2)
    if active_jobs():
        maintenance('NORMAL')
        raise ValueError('work arrived before admission gate; no process stopped')
    subprocess.run(['systemctl', '--user', 'stop', 'equipment-ai-worker.service'], check=True, timeout=35)
    process(pid)
    os.kill(pid, signal.SIGTERM)
    for _ in range(100):
        if not proc.exists() or proc.joinpath('stat').read_text().split()[2] == 'Z':
            break
        time.sleep(.2)
    else:
        raise TimeoutError('verified app did not stop; no force kill sent')
    snapshot(ROOT / 'equipment.db', release / 'equipment-quiesced.sqlite3')
    snapshot(AI, release / 'assistant-quiesced.sqlite3')
    result = {'status': 'quiesced', 'old_pid': pid, 'active_jobs': 0, 'shared_model_controlled': False}
    record(release / 'quiesced.json', result)
    return result


def activate(release):
    """[MINI-COMMENT: ASSISTANT.UPGRADE.ACTIVATE]
    [EN rev.1]
    [Role] Starts the checked release with unchanged secrets and explicit matching AI DB paths.
    [Dependencies] A quiesced release and successful actual-DB copy check; existing worker unit and preserved process environment.
    [Impact] Validates startup row preservation before reopening admissions and enabling bounded retention.
    """
    if not (release / 'quiesced.json').is_file() or not list(release.glob('copy-*/result.json')):
        raise ValueError('quiescence and actual database copy check are required')
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('0.0.0.0', 5000))
    environment = values(ROOT / '.env')
    worker = values(CONFIG)
    if any(environment.get(k) != worker.get(k) for k in ('USER_AI_WORKER_TOKEN', 'USER_AI_PROVIDER_ENCRYPTION_KEY', 'USER_AI_DATABASE_EPOCH')):
        raise ValueError('web and worker private settings mismatch')
    for path in (ROOT / '.env', CONFIG):
        parsed = values(path)
        if parsed.get('USER_AI_DATABASE') not in (None, str(AI)):
            raise ValueError('existing AI database override requires explicit review')
        if 'USER_AI_DATABASE' not in parsed:
            old = path.read_bytes()
            save(release / (path.name + '.before-path-update'), old)
            atomic(path, old.rstrip(b'\r\n') + b'\nUSER_AI_DATABASE=' + str(AI).encode() + b'\n')
    old_env = json.loads((release / 'process-environment-before.json').read_text())
    old_env.update(values(ROOT / '.env'))
    old_env['PYTHONDONTWRITEBYTECODE'] = '1'
    argv = json.loads((release / 'process-before.json').read_text())['argv']
    descriptor = os.open(release / 'app-start.log', os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        app = subprocess.Popen(argv, cwd=ROOT, env=old_env, stdin=subprocess.DEVNULL, stdout=descriptor, stderr=subprocess.STDOUT, start_new_session=True)
    finally:
        os.close(descriptor)
    for _ in range(120):
        if app.poll() is not None:
            raise RuntimeError('new app exited; private startup log retained')
        try:
            with urllib.request.urlopen('http://127.0.0.1:5000/login', timeout=2) as response:
                if response.status == 200:
                    break
        except (OSError, urllib.error.URLError):
            time.sleep(.25)
    else:
        raise TimeoutError('startup health not confirmed; maintenance remains active')
    old_business = fingerprints(release / 'equipment-quiesced.sqlite3', business=True)
    old_ai = fingerprints(release / 'assistant-quiesced.sqlite3')
    if fingerprints(ROOT / 'equipment.db', old_business, business=True) != old_business or fingerprints(AI, old_ai) != old_ai:
        raise ValueError('startup did not preserve existing database rows; maintenance remains active')
    audit_preserved(release / 'equipment-quiesced.sqlite3', ROOT / 'equipment.db')
    with sqlite3.connect(AI) as db:
        if db.execute('SELECT version FROM ai_meta').fetchall() != [(4,)]:
            raise ValueError('production AI schema is not v4')
    if values(ROOT / '.env').get('SECRET_KEY') != environment.get('SECRET_KEY'):
        raise ValueError('Flask secret changed')
    for filename in ('equipment-ai-retention.service', 'equipment-ai-retention.timer'):
        path = UNIT / filename
        source = (ROOT / 'systemd' / filename).read_bytes()
        if path.exists() and path.read_bytes() != source:
            raise ValueError('existing retention unit differs; preserve it for review')
        if not path.exists():
            save(path, source)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    maintenance('NORMAL')
    subprocess.run(['systemctl', '--user', 'start', 'equipment-ai-worker.service'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', 'equipment-ai-retention.timer'], check=True)
    state = subprocess.check_output(['systemctl', '--user', 'is-active', 'equipment-ai-worker.service'], text=True).strip()
    if state != 'active':
        raise ValueError('worker not active')
    result = {'status': 'active', 'app_pid': app.pid, 'worker': state, 'ai_version': 4,
              'old_business_rows_preserved': True, 'old_ai_rows_preserved': True, 'secrets_preserved': True,
              'explicit_ai_database': str(AI), 'retention_timer_enabled': True,
              'activated_at_utc': datetime.now(timezone.utc).isoformat()}
    record(release / 'activated.json', result)
    return result


def main():
    """[Role] Restricts release operations to an exact owned host/path/commit. [Dependencies] Explicit phase flags and flock. [Impact] No generic file/SQL/process-control mode."""
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('check-copy', 'pause', 'activate'))
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--pid', type=int)
    args = parser.parse_args()
    if os.name != 'posix' or socket.gethostname() != 'nkhst-pentium' or os.geteuid() != 1000:
        raise PermissionError('fixed equipment deployment host/user required')
    if not re.fullmatch('[a-f0-9]{40}', args.expected_head):
        raise ValueError('exact Git release required')
    actual = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, text=True).strip()
    if actual != args.expected_head:
        raise ValueError('release commit mismatch')
    for arguments in (('diff','--quiet'),('diff','--cached','--quiet')):
        if subprocess.run(['git','-C',str(ROOT),*arguments],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).returncode:
            raise ValueError('tracked server changes must be preserved/reviewed before deployment')
    release = args.release
    if release.parent != ROOT / 'instance/releases' or release.resolve() != release or not re.fullmatch('20261105-ai-ux-[A-Za-z0-9-]+', release.name):
        raise ValueError('fixed private release directory required')
    info = release.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise PermissionError('release directory must be private and owned')
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    sys.dont_write_bytecode = True
    descriptor = os.open(release / 'upgrade.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = check_copy(release) if args.action == 'check-copy' else pause(release, args.pid) if args.action == 'pause' else activate(release)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
