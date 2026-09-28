"""검증된 공통 배포 도구로 장비 모달 템플릿 한 파일만 적용하고 재시작한다."""
import sys
from pathlib import Path

root = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
shared = root / 'Reports/2026/09/16/catalog-ui-release/backup_release.py'
source = shared.read_text(encoding='utf-8')
marker = 'data = json.load(sys.stdin)'
assert source.count(marker) == 1
exec(compile(source.split(marker, 1)[0], str(shared), 'exec'), globals())

from jinja2 import Environment

target, expected_head, raw_pid = sys.argv[1:]
assert re.fullmatch(r'[0-9a-f]{40}', target)
assert re.fullmatch(r'[0-9a-f]{40}', expected_head)
pid = int(raw_pid)
assert ROOT == root and ROOT.resolve() == ROOT and ROOT.stat().st_uid == os.getuid()
assert git('branch', '--show-current') == 'main'
assert git('rev-parse', 'HEAD') == expected_head
assert not git('diff', '--name-only') and not git('diff', '--cached', '--name-only')
git('fetch', 'origin', 'main')
assert git('rev-parse', 'FETCH_HEAD') == target
git('merge-base', '--is-ancestor', expected_head, target)
assert set(git('diff', '--name-only', expected_head, target).splitlines()) == {
    'templates/index.html', 'tests/test_proposal047_registration.mjs'
}

template = ROOT / 'templates/index.html'
assert not template.is_symlink() and template.resolve().is_relative_to(ROOT)
original = template.read_bytes()
original_mode = stat.S_IMODE(template.stat().st_mode)
assert digest(original) == digest(subprocess.check_output(['git', 'show', expected_head + ':templates/index.html'], cwd=ROOT))
candidate = subprocess.check_output(['git', 'show', target + ':templates/index.html'], cwd=ROOT)
Environment().parse(candidate.decode('utf-8'))

proc = Path('/proc') / str(pid)
command = (proc / 'cmdline').read_bytes().decode().split('\0')[:-1]
assert (proc / 'cwd').resolve() == ROOT
assert command == [str(ROOT / '.venv/bin/python'), '-u', 'app.py']
environment = dict(x.decode().split('=', 1) for x in (proc / 'environ').read_bytes().split(b'\0') if x)
database = Path(environment.get('DATABASE_PATH', str(ROOT / 'equipment.db'))).resolve()
assert database == ROOT / 'equipment.db' and environment.get('FLASK_DEBUG') == '0' and health()

release = RELEASES / ('lineup-modal-scroll-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
assert not release.exists()
private(release)
save(release / 'index-before.html', original)
save(release / 'git-status-before.txt', git('status', '--short', '--branch').encode())
db_snapshot(database, release / 'equipment-before.db')
before = db_state(database)
assert before['integrity'] == 'ok' and before['fk'] == 0
evidence = dict(status='prepared', previous_head=expected_head, target=target, old_pid=pid,
                release=str(release), template_parse='pass')
save(release / 'manifest.json', json.dumps(evidence, indent=2).encode())
stopped = False
started = None
try:
    stop(pid, command)
    stopped = True
    save(release / 'pull.txt', git('pull', '--ff-only', 'origin', 'main').encode())
    assert git('rev-parse', 'HEAD') == target
    assert digest(template.read_bytes()) == digest(candidate)
    started = start(command, environment, release, 'service-start')
    after = db_state(database)
    assert after['integrity'] == 'ok' and after['fk'] == 0
    evidence.update(status='deployed', head=git('rev-parse', 'HEAD'), new_pid=started.pid,
                    health=200, db_integrity=after['integrity'], foreign_key_violations=after['fk'],
                    business_tables_unchanged=before['tables'] == after['tables'],
                    template_sha256=hashlib.sha256(template.read_bytes()).hexdigest(),
                    git_status_after=git('status', '--short', '--branch'))
    save(release / 'result.json', json.dumps(evidence, indent=2).encode())
except BaseException as error:
    evidence.update(status='failed', error_type=type(error).__name__, error=str(error)[:300])
    if started is not None and started.poll() is None:
        stop(started.pid, command)
    if stopped:
        assert digest(template.read_bytes()) in (digest(original), digest(candidate))
        restore_file(template, original, original_mode)
        recovered = start(command, environment, release, 'service-rollback')
        evidence.update(rollback_pid=recovered.pid, rollback_health=200)
    save(release / 'failure.json', json.dumps(evidence, indent=2).encode())
    print(json.dumps(evidence))
    raise SystemExit(1)
print(json.dumps(evidence))
