"""Apply the Git-pulled Strata configuration with backups and rollback on Linux."""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import signal
import socket
import sqlite3
import stat
import subprocess
import time
import urllib.request
from datetime import datetime, timezone

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
SITE = Path('/etc/nginx/sites-available/mini-server-backup')
SNIPPET = Path('/etc/nginx/snippets/eqmgmt-strata.conf')
KEY_INCLUDE = Path('/etc/nginx/private/strata-upstream-key.conf')


def insert_include(text):
    """[MINI-COMMENT: STRATA.DEPLOY.NGINX]
    [EN rev.1]
    [Role] Adds one include to the unique existing nekohost.org HTTPS server.
    [Dependencies] Balanced Nginx braces with quoted strings/comments ignored.
    [Impact] Preserves every existing directive and rejects ambiguous configurations.
    """
    cleaned = list(text)
    quote = None
    comment = False
    escaped = False
    for i, char in enumerate(text):
        if comment:
            if char == '\n':
                comment = False
            else:
                cleaned[i] = ' '
        elif quote:
            cleaned[i] = ' '
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char == '#':
            comment = True
            cleaned[i] = ' '
        elif char in ('"', "'"):
            quote = char
            cleaned[i] = ' '
    if quote:
        raise ValueError('Unterminated Nginx string')
    clean = ''.join(cleaned)
    stack, blocks = [], []
    for i, char in enumerate(clean):
        if char == '{':
            prefix = clean[:i].rstrip()
            is_server = not stack and bool(re.search(r'\bserver\Z', prefix))
            stack.append((i, is_server))
        elif char == '}':
            if not stack:
                raise ValueError('Unbalanced Nginx braces')
            start, is_server = stack.pop()
            if is_server:
                body = clean[start:i]
                if re.search(r'\blisten\s+(?:[^\s;]*:)?443\b[^;]*;', body) and re.search(r'\bserver_name\s+[^;]*\bnekohost\.org\b', body):
                    blocks.append((start, i))
    if stack or len(blocks) != 1:
        raise ValueError('Expected one unambiguous existing HTTPS server')
    if 'eqmgmt-strata.conf' in text or re.search(r'\blocation\b[^{};]*strata', clean):
        raise ValueError('A Strata location already exists; review it first')
    closing = blocks[0][1]
    return text[:closing] + '    include /etc/nginx/snippets/eqmgmt-strata.conf;\n' + text[closing:]


def command(arguments, **kwargs):
    return subprocess.run(arguments, capture_output=True, check=True, **kwargs)


def git(*arguments):
    return command(['git', '-c', 'safe.directory=' + str(ROOT), '-C', str(ROOT), *arguments],
                   env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}).stdout.decode().strip()


def save(path, data, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def replace(path, data, metadata=None):
    temporary = path.with_name(path.name + '.strata-' + str(os.getpid()))
    save(temporary, data, stat.S_IMODE(metadata.st_mode) if metadata else 0o600)
    if metadata:
        os.chown(temporary, metadata.st_uid, metadata.st_gid)
    os.replace(temporary, path)


def database_state(database):
    ignored = {'menus', 'role_menu_permissions', 'access_logs', 'audit_logs',
               'auth_rate_buckets', 'sqlite_sequence'}
    with sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        result = {}
        for table in sorted(set(tables) - ignored):
            query = 'SELECT * FROM "' + table.replace('"', '""') + '"'
            rows = sorted(repr(tuple(row)) for row in connection.execute(query))
            result[table] = (len(rows), hashlib.sha256('\n'.join(rows).encode()).hexdigest())
    return result


def stop(pid):
    os.kill(pid, signal.SIGTERM)
    for _ in range(75):
        proc = Path('/proc') / str(pid)
        if not proc.exists() or proc.joinpath('stat').read_text().split()[2] == 'Z':
            return
        time.sleep(0.2)
    raise TimeoutError('Application did not stop after SIGTERM')


def healthy():
    try:
        with urllib.request.urlopen('http://127.0.0.1:5000/login', timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def start(argv, environment, account, release, label):
    descriptor = os.open(release / (label + '.log'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.fchown(descriptor, account.pw_uid, account.pw_gid)

    def drop_privileges():
        os.initgroups(account.pw_name, account.pw_gid)
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)

    try:
        process = subprocess.Popen(argv, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=descriptor, stderr=subprocess.STDOUT,
                                   start_new_session=True, preexec_fn=drop_privileges)
    finally:
        os.close(descriptor)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('New application process exited; see protected startup log')
            if healthy():
                return process
            time.sleep(0.2)
        raise TimeoutError('New application did not become healthy')
    except BaseException:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        raise


def main():
    """[MINI-COMMENT: STRATA.DEPLOY.APPLY]
    [EN rev.1]
    [Role] Applies configuration only after the exact approved commit is pulled.
    [Dependencies] Root sudo session, private existing key, healthy known Python PID.
    [Impact] Backs up config/DB, preserves business rows, and restores on failure.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--previous-commit', required=True)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--release', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0 and os.environ.get('SUDO_USER') == 'nekohost'
    assert socket.gethostname() == 'nkhst-pentium'
    assert re.fullmatch('[0-9a-f]{40}', args.commit) and re.fullmatch('[0-9a-f]{40}', args.previous_commit)
    account = pwd.getpwnam('nekohost')
    assert ROOT.resolve() == ROOT and ROOT.stat().st_uid == account.pw_uid
    assert git('rev-parse', 'HEAD') == args.commit and not git('diff', '--name-only') and not git('diff', '--cached', '--name-only')
    release = args.release
    assert release.resolve() == release and release.parent == Path(account.pw_dir) / '.local/share/mini-server-eqmgmt/releases'
    assert release.stat().st_uid == account.pw_uid and stat.S_IMODE(release.stat().st_mode) == 0o700
    key = release / 'strata-key.txt'
    assert key.is_file() and not key.is_symlink() and key.stat().st_uid == account.pw_uid and stat.S_IMODE(key.stat().st_mode) == 0o600
    proc = Path('/proc') / str(args.pid)
    assert proc.stat().st_uid == account.pw_uid and proc.joinpath('cwd').resolve() == ROOT
    argv = [part.decode() for part in proc.joinpath('cmdline').read_bytes().split(b'\0') if part]
    assert argv == [str(ROOT / '.venv/bin/python'), '-u', 'app.py'] and healthy()
    old_environment = dict(part.decode().split('=', 1) for part in proc.joinpath('environ').read_bytes().split(b'\0') if part)
    database = Path(old_environment.get('DATABASE_PATH', str(ROOT / 'equipment.db'))).resolve()
    assert database == ROOT / 'equipment.db'
    environment = {**old_environment, 'STRATA_ENABLED': 'true', 'STRATA_PUBLIC_ORIGIN': 'https://nekohost.org',
                   'STRATA_UPSTREAM_URL': 'http://192.168.0.14:8080'}
    site_metadata, env_metadata = SITE.lstat(), (ROOT / '.env').lstat()
    assert stat.S_ISREG(site_metadata.st_mode) and stat.S_ISREG(env_metadata.st_mode)
    assert not SNIPPET.exists() and not KEY_INCLUDE.exists()
    original_site, original_env = SITE.read_bytes(), (ROOT / '.env').read_bytes()
    candidate_site = insert_include(original_site.decode()).encode()
    candidate_env = original_env.decode()
    for name in ('STRATA_ENABLED', 'STRATA_PUBLIC_ORIGIN', 'STRATA_UPSTREAM_URL'):
        pattern = r'(?m)^\s*(?:export\s+)?' + name + r'=[^\n]*$'
        assert len(re.findall(pattern, candidate_env)) <= 1
        candidate_env = re.sub(pattern, '', candidate_env).rstrip('\r\n') + '\n' + name + '=' + environment[name] + '\n'
    backup = Path('/var/backups/mini-server-eqmgmt')
    backup.mkdir(mode=0o700, exist_ok=True)
    assert backup.stat().st_uid == 0 and not stat.S_IMODE(backup.stat().st_mode) & 0o077
    backup = backup / ('strata-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(mode=0o700)
    save(backup / 'nginx-site.before', original_site)
    save(backup / 'environment.before', original_env)
    result = {'status': 'prepared', 'commit': args.commit, 'old_pid': args.pid,
              'backup': str(backup), 'release': str(release), 'key_logged': False}
    lock = open('/run/lock/eqmgmt-strata-deploy.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    spec = importlib.util.spec_from_file_location('strata_key_writer', ROOT / 'tools/write_strata_nginx_key.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    pending_key = backup / 'strata-upstream-key.conf'
    helper.write_key_include(pending_key, key.read_text().rstrip('\r\n'))
    stopped, started, configured = False, None, False
    try:
        if not KEY_INCLUDE.parent.exists():
            KEY_INCLUDE.parent.mkdir(mode=0o700)
        assert KEY_INCLUDE.parent.stat().st_uid == 0 and stat.S_IMODE(KEY_INCLUDE.parent.stat().st_mode) == 0o700
        save(KEY_INCLUDE, pending_key.read_bytes())
        save(SNIPPET, (ROOT / 'systemd/nginx-strata.conf.example').read_bytes(), 0o644)
        replace(SITE, candidate_site, site_metadata)
        configured = True
        command(['/usr/sbin/nginx', '-t'])
        stop(args.pid)
        stopped = True
        with sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True) as source:
            with sqlite3.connect(backup / 'equipment-before.db') as destination:
                source.backup(destination)
        os.chmod(backup / 'equipment-before.db', 0o600)
        before = database_state(database)
        with sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True) as connection:
            menu_existed = bool(connection.execute("SELECT 1 FROM menus WHERE MenuCode='strata'").fetchone())
        replace(ROOT / '.env', candidate_env.encode(), env_metadata)
        started = start(argv, environment, account, release, 'service-start')
        assert before == database_state(database), 'Business data changed during startup'
        with sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True) as connection:
            assert connection.execute("SELECT Url FROM menus WHERE MenuCode='strata'").fetchone() == ('/ai',)
            assert connection.execute("SELECT IsAllowed FROM role_menu_permissions WHERE Role='admin' AND MenuCode='strata'").fetchone() == (1,)
        command(['systemctl', 'reload', 'nginx'])
        statuses = {}
        for path, expected in (('/login', 200), ('/ai', 302), ('/api/strata/status', 401),
                               ('/strata/health', 401), ('/api/strata/access', 404), ('/_eqmgmt_strata_auth', 404)):
            query = command(['curl', '--resolve', 'nekohost.org:443:127.0.0.1', '--silent', '--max-time', '8',
                             '--output', '/dev/null', '--write-out', '%{http_code}', 'https://nekohost.org' + path])
            statuses[path] = int(query.stdout.decode())
            assert statuses[path] == expected, 'Unexpected production access boundary'
        result.update(status='deployed', new_pid=started.pid, nginx_test=True,
                      nginx_reloaded=True, business_tables_unchanged=len(before), http=statuses,
                      feature_enabled=True)
    except BaseException as error:
        result.update(status='failed', error_type=type(error).__name__)
        if started is not None and started.poll() is None:
            stop(started.pid)
        replace(ROOT / '.env', original_env, env_metadata)
        if configured:
            replace(SITE, original_site, site_metadata)
        for path in (SNIPPET, KEY_INCLUDE):
            if path.exists():
                path.unlink()
        command(['/usr/sbin/nginx', '-t'])
        command(['systemctl', 'reload', 'nginx'])
        if stopped:
            if not locals().get('menu_existed', True):
                with sqlite3.connect(database) as connection:
                    connection.execute("UPDATE role_menu_permissions SET IsAllowed=0 WHERE MenuCode='strata'")
            command(['runuser', '-u', account.pw_name, '--', 'git', '-C', str(ROOT), 'switch', '--detach', args.previous_commit])
            recovered = start(argv, old_environment, account, release, 'service-rollback')
            result.update(rollback_pid=recovered.pid, rollback_head=args.previous_commit)
        save(backup / 'failure.json', json.dumps(result, indent=2).encode())
        print(json.dumps(result))
        raise SystemExit(1)
    save(backup / 'result.json', json.dumps(result, indent=2).encode())
    print(json.dumps(result))


if __name__ == '__main__':
    main()
