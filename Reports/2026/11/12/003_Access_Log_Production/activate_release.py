"""Activate the verified access-log release on its existing single-process Linux web service."""
from contextlib import closing
from datetime import datetime, timezone
import fcntl
import hashlib
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
import urllib.request

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
BASE = '75829b30d3584aed02d9f6571f322a09cfa2dbab'
TARGET = '8f4df67521d31edd9b9f33b4b75d1b2f2b75af8d'
DB = ROOT / 'equipment.db'
AI = ROOT / 'instance/ai/assistant.sqlite3'
SPOOL = ROOT / 'instance/http-audit/pending.sqlite3'
WORKER = 'equipment-ai-worker.service'


def run(*argv):
    return subprocess.run(argv, cwd=ROOT, capture_output=True, check=True, text=True).stdout.strip()


def git(*args):
    return run('git', '--no-optional-locks', *args)


def web_pids():
    result = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if proc.stat().st_uid == os.geteuid() and (proc/'cwd').resolve() == ROOT:
                args = (proc/'cmdline').read_bytes().split(b'\0')
                if args[:3] == [os.fsencode(ROOT/'.venv/bin/python'), b'-u', b'app.py']:
                    result.append(int(proc.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return result


def make_request(marker=''):
    req = urllib.request.Request('http://127.0.0.1:5000/login', headers={
        'Referer': 'https://nekohost.org'+marker, 'Accept': 'text/html'})
    with urllib.request.urlopen(req, timeout=3) as resp:
        return resp.status == 200 and b'loginForm' in resp.read()


def wait_until(predicate, seconds, label):
    limit = time.monotonic() + seconds
    while time.monotonic() < limit:
        try:
            if predicate():
                return
        except (ConnectionError, TimeoutError, urllib.error.URLError):
            pass
        time.sleep(.15)
    raise RuntimeError(label)


def ro(path):
    return sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=10)


def digest_rows(rows):
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        data = repr(tuple(row)).encode('utf-8')
        digest.update(len(data).to_bytes(8, 'big'))
        digest.update(data)
        count += 1
    return {'rows': count, 'sha256': digest.hexdigest()}


def marker_saved(marker):
    with closing(ro(DB)) as db:
        return bool(db.execute("SELECT 1 FROM (SELECT RequestPath,Referer,StatusCode FROM access_logs "
                               "ORDER BY LogId DESC LIMIT 500) WHERE RequestPath='/login' AND Referer=? "
                               "AND StatusCode=200", (marker,)).fetchone())


def sessions():
    with closing(ro(DB)) as db:
        return digest_rows(db.execute('SELECT UserId,SessionToken FROM users ORDER BY UserId'))


def stop_web(pid):
    if web_pids() != [pid]:
        raise RuntimeError('web identity changed')
    proc = Path('/proc')/str(pid)
    caught = int(re.search(r'^SigCgt:\s*([a-fA-F0-9]+)', (proc/'status').read_text(), re.M)[1], 16)
    if not caught & (1 << (signal.SIGINT - 1)):
        raise RuntimeError('Python interrupt handler unavailable')
    # The installed Flask/Werkzeug launcher returns on KeyboardInterrupt. Its atexit hook drains the old queue.
    os.kill(pid, signal.SIGINT)
    wait_until(lambda: not web_pids(), 25, 'old web did not exit gracefully')


def launch(release, argv, env, log_name):
    if web_pids():
        raise RuntimeError('another web process owns the port')
    with (release/log_name).open('ab') as stream:
        child = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=stream,
                                 stderr=stream, start_new_session=True)
    wait_until(lambda: child.poll() is None and web_pids() == [child.pid] and make_request(), 45,
               'web readiness failed')
    return child.pid


def activate(release):
    assert socket.gethostname() == 'nkhst-pentium' and ROOT.stat().st_uid == os.geteuid()
    assert release.resolve() == release and release.parent == ROOT/'instance/releases'
    assert stat.S_IMODE(release.stat().st_mode) == 0o700
    backup = json.loads((release/'backup.json').read_text())
    assert backup['baseline'] == BASE and backup['backup']['equipment']['integrity'] == 'ok'
    qa = json.loads((release/'linux-release.json').read_text())
    assert qa['success'] and qa['baseline_commit'] == TARGET and not (qa['errors'] or qa['failures'] or qa['skips'])
    clone = json.loads((release/'clone-passed.json').read_text())
    assert clone['status'] == 'pass' and clone['commit'] == TARGET
    assert clone['access_rows'] == backup['backup']['equipment']['counts']['access_logs']
    assert clone['equipment_snapshot_sha256'] == backup['backup']['equipment']['sha256']
    assert git('rev-parse','HEAD') == BASE and git('rev-parse','origin/main') == TARGET
    assert not git('status','--porcelain','--untracked-files=no') and git('branch','--show-current') == 'main'
    assert json.loads((ROOT/'instance/maintenance-state.json').read_text())['state'] == 'NORMAL'
    prior = web_pids()
    assert len(prior) == 1 and run('systemctl','--user','is-active',WORKER) == 'active'
    old = prior[0]
    sys.path.insert(0,str(ROOT/'tools'))
    from deploy_ai_ux_release import process
    proc, argv, env = process(old)
    assert Path(env['DATABASE_PATH']).resolve()==DB and Path(env['USER_AI_DATABASE']).resolve()==AI
    old_log = (proc/'fd/2').resolve()
    old_offset = old_log.stat().st_size if old_log.is_file() else None
    worker = int(run('systemctl','--user','show',WORKER,'--property=MainPID','--value'))
    assert worker > 0 and not SPOOL.exists() and not any(SPOOL.parent.glob('pending.sqlite3-*'))
    before_sessions = sessions()
    marker = '/release-check/access-log-'+secrets.token_hex(8)
    assert make_request(marker)
    wait_until(lambda: marker_saved(marker), 15, 'old queue marker did not commit')
    if (release/'activation.json').exists():
        raise FileExistsError('activation already recorded')
    at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    try:
        # Fence dispatch/admission just for the old web shutdown. Queued or in-flight work is never cancelled.
        with closing(sqlite3.connect(AI.as_uri()+'?mode=rw', uri=True, timeout=10)) as ai:
            ai.execute('BEGIN IMMEDIATE')
            inflight = ai.execute("SELECT COUNT(*) FROM jobs WHERE state IN "
                                  "('queued','running','draining','recovery_required')").fetchone()[0]
            guards = ai.execute("SELECT COUNT(*) FROM ai_execution_guards WHERE state IN "
                                "('running','draining','recovery_required')").fetchone()[0]
            if inflight or guards:
                raise RuntimeError('AI job was admitted before the release')
            stop_web(old)
            ai.rollback()
        assert not SPOOL.exists() and not any(SPOOL.parent.glob('pending.sqlite3-*'))
        assert 'LISTEN' not in run('ss','-ltnH','sport = :5000')
        if old_offset is not None:
            with old_log.open('rb') as f:
                f.seek(old_offset)
                tail = f.read()
            assert all(x not in tail for x in (b'HTTP access audit could not be stored',
                       b'AI access audit retry pending', b'Ordinary access log batch could not be stored'))
        low = backup['backup']['equipment']['log_upper']
        with closing(ro(DB)) as db:
            high = db.execute('SELECT COALESCE(MAX(LogId),0) FROM access_logs').fetchone()[0]
            counts = digest_rows(db.execute('SELECT * FROM access_logs WHERE LogId>? AND LogId<=? ORDER BY LogId',(low,high)))
        git('merge','--ff-only',TARGET)
        assert git('rev-parse','HEAD')==TARGET
        new = launch(release, argv, env, 'web-start.log')
        elapsed = round(time.monotonic()-started,3)
        assert marker_saved(marker) and before_sessions == sessions()
        assert worker == int(run('systemctl','--user','show',WORKER,'--property=MainPID','--value'))
    except BaseException:
        # Restore only this clean source tree. Both real DBs, historical logs, and sessions stay in place.
        if git('rev-parse','HEAD') == TARGET:
            if SPOOL.exists() or any(SPOOL.parent.glob('pending.sqlite3-*')):
                raise RuntimeError('recovery needs legacy spool isolation')
            current = web_pids()
            if current:
                stop_web(current[0])
            assert not git('status','--porcelain','--untracked-files=no')
            git('reset','--keep',BASE)
        if not web_pids():
            launch(release,argv,env,'rollback-web.log')
        raise
    result = {'status':'active','commit':TARGET,'baseline':BASE,'utc':at,'web_old_pid':old,
              'web_new_pid':new,'worker_pid':worker,'worker_restart':False,'ports_without_overlap':True,
              'switch_to_readiness_seconds':elapsed,'normal_queue_marker_persisted':True,
              'old_atexit_error_signatures':0 if old_offset is not None else None,
              'unchanged_session_tokens':before_sessions['rows'],'initial_bound':low,'previous_web_last_bound':high,
              'old_log_tail':counts,'legacy_spool_at_switch':'absent','active_jobs_at_switch':inflight}
    with (release/'activation.json').open('x') as f:
        json.dump(result,f,indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    os.umask(0o077)
    folder=Path(sys.argv[1]).resolve()
    assert folder.parent==ROOT/'instance/releases' and folder.name.startswith('access-separation-')
    with (folder/'activate.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        activate(folder)
