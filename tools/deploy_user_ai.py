"""Linux-only, scoped release operations for the approved equipment assistant.

[MINI-COMMENT: ASSISTANT.RELEASE]
[EN rev.2]
[Role] Prepares private settings, checks a production snapshot and activates a known release.
[Dependencies] An exact Git commit, existing private USER_AI configuration or explicit protected key input, and user-owned Python app.
[Impact] Preserves the Flask key/business rows and records backups; never controls shared model jobs.
"""
import argparse
import base64
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
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
CONFIG = Path('/home/nekohost/.config/eqmgmt/assistant-worker.env')
sys.path.insert(0, str(ROOT))


def save(path, data):
    """Create a private artifact exclusively, without following a final symlink."""
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def replace(path, data):
    """Atomically replace an owned regular configuration; its private backup is retained."""
    meta = path.lstat()
    assert stat.S_ISREG(meta.st_mode) and meta.st_uid == os.geteuid() and stat.S_IMODE(meta.st_mode) == 0o600
    pending = path.with_name(path.name + '.ai-release-' + secrets.token_hex(6))
    save(pending, data)
    os.replace(pending, path)


def private(path):
    """Validate a fixed user's private artifact directory before any write."""
    assert path.is_absolute() and path.resolve() == path
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    meta = path.stat()
    assert meta.st_uid == os.geteuid() and stat.S_IMODE(meta.st_mode) == 0o700
    return path


def git(*args):
    """Read release identity without optional index locks."""
    return subprocess.check_output(['git', '-c', 'safe.directory=' + str(ROOT), '-C', str(ROOT), *args],
                                   env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, text=True).strip()


def snapshot(source, target):
    """Create and integrity-check an online SQLite backup without exposing row contents."""
    assert not target.exists()
    with sqlite3.connect('file:' + str(source) + '?mode=ro', uri=True) as original, sqlite3.connect(target) as copied:
        original.backup(copied)
        assert copied.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not copied.execute('PRAGMA foreign_key_check').fetchall()
    os.chmod(target, 0o600)


def fingerprints(path):
    """Hash all business rows, allowing only independent runtime/audit and new AI menu metadata."""
    ignored = {'access_logs', 'audit_logs', 'auth_rate_buckets', 'sqlite_sequence'}
    values = {}
    with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
            if table in ignored:
                continue
            quoted = '"' + table.replace('"', '""') + '"'
            predicate = " WHERE MenuCode NOT IN ('equipment_ai','equipment_ai_settings')" if table in ('menus', 'role_menu_permissions') else ''
            rows = sorted(repr(tuple(r)) for r in db.execute('SELECT * FROM ' + quoted + predicate))
            values[table] = {'rows': len(rows), 'sha256': hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
    return values


def read_private_key(key_file, account_uid):
    """[MINI-COMMENT: ASSISTANT.RELEASE.KEY.INPUT]
    [EN rev.1]
    [Role] Reads one explicitly supplied owner-only plaintext key without any Nginx dependency.
    [Dependencies] Linux O_NOFOLLOW, stable file metadata and a canonical private parent.
    [Impact] Rejects symlinks, oversized/control data and unsafe permissions without exposing credentials.
    """
    path = Path(key_file)
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError('Use an absolute protected key-file path without symlinks')
    parent = path.parent.lstat()
    metadata = path.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid not in (0, account_uid) or
            stat.S_IMODE(parent.st_mode) & 0o077 or not stat.S_ISREG(metadata.st_mode) or
            metadata.st_uid not in (0, account_uid) or stat.S_IMODE(metadata.st_mode) != 0o600 or
            not 1 <= metadata.st_size <= 8192):
        raise PermissionError('Key input must be a private regular file with mode 0600 in an owner-only directory')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        actual = os.fstat(stream.fileno())
        if (actual.st_dev, actual.st_ino, actual.st_uid, actual.st_mode) != (metadata.st_dev, metadata.st_ino, metadata.st_uid, metadata.st_mode):
            raise PermissionError('Key input changed during validation')
        raw = stream.read(8193)
    key = raw.decode('ascii').rstrip('\r\n')
    if not key or len(key) > 4096 or any(not 33 <= ord(char) <= 126 for char in key):
        raise ValueError('Key input must contain one printable line')
    if key in ('REPLACE_WITH_API_KEY', '<actual-key>'):
        raise ValueError('Use the existing provider key from a protected input file')
    return key


def prepare(key_file=None):
    """[MINI-COMMENT: ASSISTANT.RELEASE.KEY.PREPARE]
    [EN rev.1]
    [Role] Preserves an existing private assistant configuration or creates it from explicit protected key input.
    [Dependencies] Verified Linux sudo owner; independent USER_AI secrets and the fixed private configuration path.
    [Impact] Never reads/deletes an old Nginx include, overwrites existing keys or rotates an API key.
    """
    assert os.geteuid() == 0 and os.environ.get('SUDO_USER') == 'nekohost'
    account = pwd.getpwnam('nekohost')
    assert CONFIG.parent.resolve() == CONFIG.parent
    if CONFIG.exists() or CONFIG.is_symlink():
        parent, metadata = CONFIG.parent.lstat(), CONFIG.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != account.pw_uid or stat.S_IMODE(parent.st_mode) != 0o700 or
                not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != account.pw_uid or stat.S_IMODE(metadata.st_mode) != 0o600):
            raise PermissionError('Existing assistant configuration must remain a private owned regular file')
        return {'private_config': str(CONFIG), 'mode': '0600', 'existing_config_preserved': True,
                'key_input_read': False, 'legacy_nginx_dependency': False, 'secrets_disclosed': False}
    if key_file is None:
        raise ValueError('A new configuration requires --key-file; existing USER_AI configuration is preserved without one')
    key = read_private_key(key_file, account.pw_uid)
    created_parent = not CONFIG.parent.exists()
    CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = CONFIG.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or stat.S_IMODE(parent.st_mode) != 0o700 or parent.st_uid not in ((0,) if created_parent else (account.pw_uid,)):
        raise PermissionError('Assistant configuration directory must be private and owned by the service account')
    if created_parent:
        os.chown(CONFIG.parent, account.pw_uid, account.pw_gid)
    values = {
        'USER_AI_ENABLED': 'true', 'USER_AI_WRITE_TOOLS': 'true',
        'USER_AI_PUBLIC_ORIGIN': 'https://nekohost.org',
        'USER_AI_INTERNAL_URL': 'http://127.0.0.1:5000',
        'USER_AI_WORKER_TOKEN': secrets.token_urlsafe(48),
        'USER_AI_PROVIDER_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'USER_AI_DATABASE_EPOCH': secrets.token_hex(16),
        'USER_AI_STRATA_URL': 'http://192.168.0.14:8080', 'USER_AI_STRATA_KEY': key,
        'USER_AI_MODEL': 'qwen3.8-flash-next-iq3_xxs',
        'USER_AI_ALLOWED_ENDPOINTS': '["http://192.168.0.14:8080"]',
        'USER_AI_READ_TIMEOUT': '1800', 'USER_AI_COMPLETION_RESERVE_CHARS': '32000000',
        'USER_AI_DISPATCHERS': '8',
    }
    save(CONFIG, ''.join(name + '=' + json.dumps(value) + '\n' for name, value in values.items()).encode())
    os.chown(CONFIG, account.pw_uid, account.pw_gid)
    return {'private_config': str(CONFIG), 'mode': '0600', 'existing_config_preserved': False,
            'key_input_read': True, 'legacy_nginx_dependency': False, 'secrets_disclosed': False}


def check_copy(release):
    """Import the complete release only against fresh isolated paths and compare every business row."""
    from dotenv import dotenv_values
    copy_root = private(release / ('copy-' + secrets.token_hex(6)))
    database = copy_root / 'equipment.sqlite3'
    snapshot(ROOT / 'equipment.db', database)
    before = fingerprints(database)
    env = dotenv_values(ROOT / '.env')
    os.environ.update({k: v for k, v in env.items() if v is not None})
    os.environ.update({
        'DATABASE_PATH': str(database), 'DATABASE_OPERATION_ROOT': str(copy_root / 'operations'),
        'MAINTENANCE_STATE_PATH': str(copy_root / 'maintenance.json'),
        'EQUIPMENT_ATTACHMENT_ROOT': str(copy_root / 'equipment-files'),
        'USER_AI_ENABLED': 'true', 'USER_AI_WRITE_TOOLS': 'true',
        'USER_AI_WORKER_TOKEN': secrets.token_urlsafe(48),
        'USER_AI_PROVIDER_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'USER_AI_DATABASE': str(copy_root / 'assistant.sqlite3'),
        'USER_AI_AUDIT_ROOT': str(copy_root / 'audit-originals'),
        'USER_AI_MODEL_DISCOVERY': 'false', 'PYTHONDONTWRITEBYTECODE': '1',
    })
    spec = importlib.util.spec_from_file_location('assistant_release_copy', ROOT / 'app.py')
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        module.ACCESS_LOG_ACCEPTING.clear()
        module.shutdown_event.set()
        module.logger_thread.join(timeout=3)
        assert fingerprints(database) == before, 'Business rows changed during isolated startup'
        with sqlite3.connect(database) as db:
            users, missing = db.execute("SELECT count(*),sum(CASE WHEN CreatedAt IS NULL OR trim(CreatedAt)='' THEN 1 ELSE 0 END) FROM users").fetchone()
            assert not missing, 'Existing account identity metadata needs explicit repair'
            assert db.execute("SELECT Url FROM menus WHERE MenuCode='equipment_ai'").fetchone() == ('/assistant',)
            assert db.execute("SELECT IsAllowed FROM role_menu_permissions WHERE Role='user' AND MenuCode='equipment_ai'").fetchone() == (1,)
            assert not db.execute("SELECT 1 FROM role_menu_permissions WHERE Role='user' AND MenuCode='equipment_ai_settings' AND IsAllowed=1").fetchone()
        statuses = {}
        with module.app.test_client() as client:
            for route in ('/login', '/assistant', '/admin/ai/providers', '/api/ai/capabilities', '/internal/ai/claim'):
                response = client.get(route) if route != '/internal/ai/claim' else client.post(route, json={})
                statuses[route] = response.status_code
        assert statuses == {'/login': 200, '/assistant': 302, '/admin/ai/providers': 302, '/api/ai/capabilities': 401, '/internal/ai/claim': 403}
        result = {'status': 'pass', 'isolated_database': str(database), 'business_tables_preserved': before,
                  'existing_accounts': users, 'missing_identity_metadata': missing or 0, 'anonymous_statuses': statuses}
        save(copy_root / 'result.json', json.dumps(result, indent=2).encode())
        return result
    finally:
        if hasattr(module, 'shutdown_event'):
            module.shutdown_event.set()


def health():
    """Check the fixed local login endpoint without credentials or redirects to another host."""
    try:
        with urllib.request.urlopen('http://127.0.0.1:5000/login', timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def activate(release, pid):
    """Activate private settings and restart only the verified user-owned web app, retaining recovery artifacts."""
    from dotenv import dotenv_values
    meta = CONFIG.lstat()
    assert stat.S_ISREG(meta.st_mode) and meta.st_uid == os.geteuid() and stat.S_IMODE(meta.st_mode) == 0o600
    proc = Path('/proc') / str(pid)
    assert proc.stat().st_uid == os.geteuid() and proc.joinpath('cwd').resolve() == ROOT
    argv = [p.decode() for p in proc.joinpath('cmdline').read_bytes().split(b'\0') if p]
    assert argv == [str(ROOT / '.venv/bin/python'), '-u', 'app.py'] and health()
    environment = dict(p.decode().split('=', 1) for p in proc.joinpath('environ').read_bytes().split(b'\0') if p)
    settings = {k: v for k, v in dotenv_values(CONFIG).items() if v is not None}
    assert all(k.startswith('USER_AI_') for k in settings)
    existing = (ROOT / '.env').read_bytes()
    assert not any(k.startswith('USER_AI_') for k in dotenv_values(ROOT / '.env')), 'Review existing AI settings instead of overwriting'
    before_secret = dotenv_values(ROOT / '.env').get('SECRET_KEY')
    assert before_secret and len(before_secret) >= 32
    save(release / 'environment-at-activation.env', existing)
    save(release / 'process-environment-before.json', json.dumps(environment).encode())
    save(release / 'assistant-worker.env', CONFIG.read_bytes())
    os.kill(pid, signal.SIGTERM)
    for _ in range(100):
        if not proc.exists() or proc.joinpath('stat').read_text().split()[2] == 'Z':
            break
        time.sleep(.2)
    else:
        raise TimeoutError('Known app did not stop; no force kill was sent')
    snapshot(ROOT / 'equipment.db', release / 'equipment-at-activation.sqlite3')
    before = fingerprints(ROOT / 'equipment.db')
    candidate = existing.rstrip(b'\r\n') + b'\n\n# Equipment assistant private runtime settings\n' + CONFIG.read_bytes()
    replace(ROOT / '.env', candidate)
    assert dotenv_values(ROOT / '.env').get('SECRET_KEY') == before_secret
    environment.update(settings)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    descriptor = os.open(release / 'app-start.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        process = subprocess.Popen(argv, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, stdout=descriptor,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    finally:
        os.close(descriptor)
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError('New app exited; inspect private startup log before recovery')
        if health():
            break
        time.sleep(.2)
    else:
        raise TimeoutError('New app not healthy; inspect state before recovery')
    assert fingerprints(ROOT / 'equipment.db') == before, 'Business rows changed during activation'
    unit = Path('/home/nekohost/.config/systemd/user/equipment-ai-worker.service')
    unit.parent.mkdir(parents=True, exist_ok=True)
    assert not unit.exists(), 'Preserve existing worker unit for review'
    save(unit, (ROOT / 'systemd/equipment-ai-worker.service').read_bytes())
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', 'equipment-ai-worker.service'], check=True)
    worker = subprocess.check_output(['systemctl', '--user', 'is-active', 'equipment-ai-worker.service'], text=True).strip()
    assert worker == 'active'
    result = {'status': 'active', 'old_pid': pid, 'app_pid': process.pid, 'worker': worker,
              'release': str(release), 'business_rows_preserved': True, 'flask_key_preserved': True,
              'commit': git('rev-parse', 'HEAD'), 'activated_at': datetime.now(timezone.utc).isoformat()}
    save(release / 'activation.json', json.dumps(result, indent=2).encode())
    return result


def main():
    """Reject wrong hosts, commits and paths before executing the explicitly requested release step."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare-key', 'check-copy', 'activate'))
    parser.add_argument('--commit', required=True)
    parser.add_argument('--release', type=Path)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--key-file', type=Path, help='New configuration only: protected owner-only plaintext key file; never a Nginx include')
    args = parser.parse_args()
    assert os.name == 'posix' and socket.gethostname() == 'nkhst-pentium'
    assert re.fullmatch('[0-9a-f]{40}', args.commit) and git('rev-parse', 'HEAD') == args.commit
    assert not git('diff', '--name-only') and not git('diff', '--cached', '--name-only')
    os.chdir(ROOT)
    sys.dont_write_bytecode = True
    if args.action == 'prepare-key':
        result = prepare(args.key_file)
    else:
        assert os.geteuid() == pwd.getpwnam('nekohost').pw_uid
        assert args.release and args.release.resolve() == args.release and args.release.parent == ROOT / 'instance/releases'
        private(args.release)
        with open(args.release / 'activation.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = check_copy(args.release) if args.action == 'check-copy' else activate(args.release, args.pid)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
