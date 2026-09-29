"""실명 선택화의 지정 파일만 Git fast-forward 배포하고, 실패 시 원본 코드로 복구한다."""
import ast
import sys
from pathlib import Path

root = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
shared = root / 'Reports/2026/09/16/catalog-ui-release/backup_release.py'
source = shared.read_text(encoding='utf-8')
marker = 'data = json.load(sys.stdin)'
assert source.count(marker) == 1
exec(compile(source.split(marker, 1)[0], str(shared), 'exec'), globals())

from jinja2 import Environment

RUNTIME = ('app.py', 'utils/roadmap_auth.py', 'utils/roadmap_routes.py',
           'templates/register.html', 'templates/mypage.html')
FILES = set(RUNTIME) | {'tests/test_optional_real_name.py', 'docs/user-guide/사용자_가이드.md',
                       'Reports/2026/09/29/optional-real-name-release/deploy_optional_name.py'}


def main():
    action, target, expected_head, raw_pid = sys.argv[1:]
    assert action in ('check', 'apply')
    assert re.fullmatch(r'[0-9a-f]{40}', target) and re.fullmatch(r'[0-9a-f]{40}', expected_head)
    pid = int(raw_pid)
    assert ROOT == root and ROOT.resolve() == ROOT and ROOT.stat().st_uid == os.getuid()
    assert git('branch', '--show-current') == 'main' and git('rev-parse', 'HEAD') == expected_head
    assert not git('diff', '--name-only') and not git('diff', '--cached', '--name-only')
    untracked = git('ls-files', '--others', '--exclude-standard').splitlines()
    assert all(name.startswith('.venv.incomplete-20260907/') for name in untracked)
    git('fetch', 'origin', 'main')
    assert git('rev-parse', 'FETCH_HEAD') == target
    git('merge-base', '--is-ancestor', expected_head, target)
    changed = set(subprocess.check_output(['git', 'diff', '--name-only', '-z', expected_head, target], cwd=ROOT,
                                        env=dict(os.environ, GIT_OPTIONAL_LOCKS='0')).decode().strip('\0').split('\0'))
    assert changed == FILES, 'release file set differs'
    originals, candidates = {}, {}
    for name in RUNTIME:
        path = ROOT / name
        assert not path.is_symlink() and path.resolve().is_relative_to(ROOT)
        body = path.read_bytes()
        baseline = subprocess.check_output(['git', 'show', expected_head + ':' + name], cwd=ROOT)
        assert digest(body) == digest(baseline), 'unexpected source change: ' + name
        originals[name] = (body, stat.S_IMODE(path.stat().st_mode))
        candidate = subprocess.check_output(['git', 'show', target + ':' + name], cwd=ROOT)
        candidates[name] = candidate
        if name.endswith('.py'):
            ast.parse(candidate.decode('utf-8'), filename=name)
        else:
            Environment().parse(candidate.decode('utf-8'))
    proc = Path('/proc') / str(pid)
    command = (proc / 'cmdline').read_bytes().decode().split('\0')[:-1]
    assert (proc / 'cwd').resolve() == ROOT
    assert command == [str(ROOT / '.venv/bin/python'), '-u', 'app.py']
    environment = dict(item.decode().split('=', 1) for item in (proc / 'environ').read_bytes().split(b'\0') if item)
    database = Path(environment.get('DATABASE_PATH', str(ROOT / 'equipment.db'))).resolve()
    assert database == ROOT / 'equipment.db' and environment.get('FLASK_DEBUG') == '0' and health()
    evidence = {'status': 'ready', 'previous_head': expected_head, 'target': target, 'old_pid': pid,
                'runtime_files': len(RUNTIME), 'syntax': 'pass'}
    if action == 'check':
        print(json.dumps(evidence))
        return
    release = RELEASES / ('optional-real-name-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    assert not release.exists()
    private(release)
    for name, (body, _) in originals.items():
        save(release / 'before' / name, body)
    save(release / 'git-status-before.txt', git('status', '--short', '--branch').encode())
    save(release / 'git-index-before', (ROOT / '.git/index').read_bytes())
    evidence['release'] = str(release)
    save(release / 'manifest.json', json.dumps(evidence, indent=2).encode())
    stopped, started = False, None
    try:
        stop(pid, command)
        stopped = True
        db_snapshot(database, release / 'equipment-before.db')
        before = db_state(database)
        assert before['integrity'] == 'ok' and before['fk'] == 0
        save(release / 'pull.txt', git('pull', '--ff-only', 'origin', 'main').encode())
        assert git('rev-parse', 'HEAD') == target
        assert all(digest((ROOT / name).read_bytes()) == digest(body) for name, body in candidates.items())
        started = start(command, environment, release, 'service-start')
        after = db_state(database)
        assert after['integrity'] == 'ok' and after['fk'] == 0
        assert before['tables'] == after['tables'], 'unexpected business data change'
        with urllib.request.urlopen('http://127.0.0.1:5000/register', timeout=5) as response:
            page = response.read().decode('utf-8')
            assert response.status == 200 and '실명 (이름, 선택)' in page
            assert not re.search(r'<input[^>]*id="Name"[^>]*\brequired\b', page)
        evidence.update(status='deployed', head=git('rev-parse', 'HEAD'), new_pid=started.pid, health=200,
                        db_integrity=after['integrity'], foreign_key_violations=after['fk'],
                        business_tables_unchanged=True, register_optional=True,
                        runtime_sha256={name: digest(body) for name, body in candidates.items()})
        save(release / 'result.json', json.dumps(evidence, indent=2).encode())
    except BaseException as error:
        evidence.update(status='failed', error_type=type(error).__name__, error=str(error)[:200])
        if started is not None and started.poll() is None:
            stop(started.pid, command)
        if stopped:
            for name, (body, mode) in originals.items():
                path = ROOT / name
                assert digest(path.read_bytes()) in (digest(body), digest(candidates[name])), 'concurrent source edit prevents recovery'
                restore_file(path, body, mode)
            recovered = start(command, environment, release, 'service-rollback')
            evidence.update(rollback_pid=recovered.pid, rollback_health=200)
        save(release / 'failure.json', json.dumps(evidence, indent=2).encode())
        print(json.dumps(evidence))
        raise SystemExit(1)
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
