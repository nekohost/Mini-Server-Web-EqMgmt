"""승인된 Git 배포: 서버 dirty 운영본 보존, ff-only pull, 격리 회귀, 동일 명령/환경 재시작."""
import hashlib, json, os, re, select, signal, socket, sqlite3, stat, subprocess, sys, tempfile, time, urllib.request  # 배포 표준 도구입니다.
from pathlib import Path  # 경로 경계를 검증합니다.
from datetime import datetime, timezone  # 실제 배포 시각입니다.
ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')  # 승인된 백업 서버 저장소입니다.
RELEASES = Path('/home/nekohost/.local/share/mini-server-eqmgmt/releases')  # Git 밖의 private 복구 위치입니다.
def digest(data):
    """[역할] 파일 비교. [의존성 관계] SHA256. [변경 시 영향도] 덮어쓰기 전 동일성 검사."""
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()  # 줄바꿈만 정규화합니다.
def git(*args):
    """[역할] 지정 저장소 Git. [의존성 관계] subprocess. [변경 시 영향도] 실패 즉시 중단."""
    return subprocess.check_output(['git', *args], cwd=ROOT, env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'), stderr=subprocess.STDOUT).decode().strip()  # 비밀 remote URL을 출력하지 않습니다.
def private(path):
    """[역할] 복구 디렉터리. [의존성 관계] 소유권. [변경 시 영향도] 백업 접근 제한."""
    assert not path.is_symlink(); path.mkdir(mode=0o700, parents=True, exist_ok=True); assert path.stat().st_uid == os.getuid(); path.chmod(0o700)  # 타인 경로는 거부합니다.
def save(path, data):
    """[역할] 새 증거 저장. [의존성 관계] O_EXCL. [변경 시 영향도] 기존 기록 보존."""
    private(path.parent)  # 비공개 디렉터리입니다.
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())  # 기존 파일을 덮지 않습니다.
def db_snapshot(source, destination):
    """[역할] 일관된 독립 DB 백업. [의존성 관계] SQLite backup. [변경 시 영향도] 원본 읽기 전용."""
    save(destination, b'')  # private 새 파일입니다.
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(destination) as dst: src.backup(dst)  # app import 없이 생성합니다.
def db_state(path):
    """[역할] 업무 데이터 보존 비교. [의존성 관계] read-only SQLite. [변경 시 영향도] 전체 DB 복원 금지."""
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as con:  # 결과에는 실제 행을 출력하지 않습니다.
        tables = ('users', 'equipments', 'equipment_options', 'lineup_nodes', 'categories', 'manufacturers', 'approval_requests', 'menus', 'role_menu_permissions', 'sys_migrations')  # 이번 배포에서 불변이어야 합니다.
        return {'integrity': con.execute('PRAGMA integrity_check').fetchone()[0], 'fk': len(con.execute('PRAGMA foreign_key_check').fetchall()), 'tables': {name: {'rows': con.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0], 'digest': digest(repr(con.execute('SELECT * FROM ' + name + ' ORDER BY rowid').fetchall()).encode())} for name in tables}}  # 내용은 해시로만 비교합니다.
def stop(pid, command):
    """[역할] 정확한 기존 서버만 종료. [의존성 관계] pidfd. [변경 시 영향도] PID 재사용/타 작업 종료 방지."""
    handle = os.pidfd_open(pid)  # 프로세스 객체를 고정합니다.
    try:  # 신호 전 경로와 명령을 다시 확인합니다.
        assert (Path('/proc') / str(pid) / 'cwd').resolve() == ROOT  # 다른 앱을 종료하지 않습니다.
        assert (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0')[:-1] == [x.encode() for x in command]  # 정확한 명령입니다.
        signal.pidfd_send_signal(handle, signal.SIGTERM)  # logger의 정상 종료 기회를 줍니다.
        if not select.select([handle], [], [], 20)[0]: raise RuntimeError('graceful stop timeout; no SIGKILL')  # 강제 종료하지 않습니다.
    finally: os.close(handle)  # 핸들을 반환합니다.
def health():
    """[역할] 실제 HTTP 확인. [의존성 관계] localhost. [변경 시 영향도] 단순 프로세스 생성과 구분."""
    try:  # 제한시간 내 응답을 요구합니다.
        with urllib.request.urlopen('http://127.0.0.1:5000/login', timeout=2) as response: return response.status == 200  # 인증 없는 화면입니다.
    except OSError: return False  # 아직 기동되지 않았습니다.
def start(command, environment, release, label):
    """[역할] 기존 명령/환경 재시작. [의존성 관계] Popen. [변경 시 영향도] systemd 중복 구동 없음."""
    with socket.socket() as probe: probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); probe.bind(('0.0.0.0', 5000))  # 다른 서버가 있으면 시작하지 않습니다.
    with os.fdopen(os.open(release / (label + '.log'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:  # 기동 로그를 private에 보존합니다.
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)  # SSH 세션 수명과 분리합니다.
    for _ in range(60):  # 최대 30초 실제 상태를 확인합니다.
        if process.poll() is not None: raise RuntimeError('app exited; see private startup log')  # 실패를 보고합니다.
        if health(): return process  # 실제 HTTP 성공입니다.
        time.sleep(.5)  # 불필요한 반복 부하를 줄입니다.
    stop(process.pid, command); raise RuntimeError('HTTP startup timeout')  # 검증에 실패한 새 프로세스만 종료합니다.
def restore_file(path, body, mode):
    """[역할] 실패 시 코드 복원. [의존성 관계] 보존본. [변경 시 영향도] 운영 DB는 복원하지 않습니다."""
    temporary = path.with_name(path.name + '.release-restore-' + str(os.getpid()))  # 충돌하지 않는 임시 파일입니다.
    with temporary.open('xb') as stream: stream.write(body); stream.flush(); os.fsync(stream.fileno())  # 원본 bytes를 복구합니다.
    os.chmod(temporary, mode); os.replace(temporary, path)  # 원자적 코드 교체입니다.
data = json.load(sys.stdin)  # controller가 hash/commit만 전달합니다. 비밀은 전달하지 않습니다.
assert ROOT.resolve() == ROOT and ROOT.is_dir() and os.getuid() == ROOT.stat().st_uid  # 승인된 저장소/소유자입니다.
assert re.fullmatch(r'[0-9a-f]{40}', data['target'])  # 임의 Git 인자를 허용하지 않습니다.
old_head = git('rev-parse', 'HEAD'); assert old_head == data['server_head']  # 다중 작업자 변경 시 중단합니다.
assert git('branch', '--show-current') == 'main'  # 다른 branch는 변경하지 않습니다.
assert not git('diff', '--cached', '--name-only')  # 타인의 stage를 건드리지 않습니다.
git('fetch', 'origin', 'refs/heads/main:refs/remotes/origin/main')  # 파일을 변경하지 않고 목표 객체를 받습니다.
assert git('rev-parse', 'origin/main') == data['target']  # 다른 원격 갱신을 무심코 배포하지 않습니다.
git('merge-base', '--is-ancestor', old_head, data['target'])  # fast-forward 가능한 배포만 허용합니다.
files = data['files']; originals = {}; previous_matches = 0  # 원본 복구를 메모리와 디스크에 보존합니다.
for name, entry in files.items():  # 전체 운영 파일 기준을 대조합니다.
    assert name in ('app.py', 'requirements.txt') or name.startswith(('static/', 'templates/', 'utils/', 'Resources/'))  # 실행 파일 허용 범위입니다.
    path = ROOT / name; assert '..' not in Path(name).parts and path.resolve().is_relative_to(ROOT) and not path.is_symlink()  # 경로 탈출 차단입니다.
    original = path.read_bytes() if path.exists() else None  # 새 파일도 구분합니다.
    actual = digest(original) if original is not None else None  # 정규화 hash입니다.
    assert actual == entry['previous'], 'unexplained runtime change: ' + name  # 전일 실배포본과 동일해야 합니다.
    assert digest(subprocess.check_output(['git', 'show', data['target'] + ':' + name], cwd=ROOT)) == entry['target']  # 원격 파일 내용도 검증합니다.
    originals[name] = (original, stat.S_IMODE(path.stat().st_mode)) if original is not None else None  # 모드도 보존합니다.
    previous_matches += int(original is not None)  # 확인된 운영 파일 수입니다.
modified = git('diff', '--name-only').splitlines()  # 추적된 미커밋 파일입니다.
untracked = [p for p in git('ls-files', '--others', '--exclude-standard').splitlines() if not p.startswith('.venv.incomplete-20260907/')]  # 기존 보존 artifact는 대상 밖입니다.
stash_paths = sorted(set(modified + untracked))  # 정확히 확인한 경로만 보관합니다.
assert set(stash_paths) <= set(files), 'unrelated uncommitted files: ' + repr(set(stash_paths) - set(files))  # 새 작업을 자동 합치지 않습니다.
proc = Path('/proc') / str(data['pid']); command = (proc / 'cmdline').read_bytes().decode().split('\0')[:-1]  # 현행 웹 프로세스입니다.
assert (proc / 'cwd').resolve() == ROOT and command == [str(ROOT / '.venv/bin/python'), '-u', 'app.py']  # 확인된 명령만 허용합니다.
environment = dict(x.decode().split('=', 1) for x in (proc / 'environ').read_bytes().split(b'\0') if x)  # 비밀을 출력/저장하지 않습니다.
database = Path(environment.get('DATABASE_PATH', str(ROOT / 'equipment.db'))).resolve(); assert database == ROOT / 'equipment.db'  # 운영 DB 경로입니다.
assert environment.get('FLASK_DEBUG') == '0' and health()  # 현재 정상 서버만 전환합니다.
if not data.get('apply'):  # 사전 점검은 서버 파일을 변경하지 않습니다.
    print(json.dumps({'status':'ready','head':old_head,'target':data['target'],'pid':data['pid'],'runtime_files':len(files),'previous_matches':previous_matches,'stash_paths':stash_paths})); sys.exit(0)  # 별도 실행에서만 적용합니다.
release = RELEASES / ('catalog-ui-git-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')); assert not release.exists(); private(release)  # 이번 배포 전용 복구 폴더입니다.
for name, original in originals.items():  # 전체 운영 코드의 원본을 보존합니다.
    if original is not None: save(release / 'before' / name, original[0])  # 기존 권한과 관계없이 사본은0600입니다.
save(release / 'git-status-before.txt', git('status', '--short', '--branch').encode())  # 원래 변경 목록입니다.
save(release / 'git-worktree-before.patch', subprocess.check_output(['git','diff','--binary'], cwd=ROOT))  # 추적 파일의 정확한 diff입니다.
save(release / 'git-index-before', (ROOT / '.git/index').read_bytes())  # index 손상 시 조사용; 자동 덮어쓰지 않습니다.
evidence = {'status':'prepared','release':str(release),'previous_head':old_head,'target':data['target'],'old_pid':data['pid'],'runtime_files':len(files),'preserved_paths':stash_paths}  # 민감한 환경값은 제외합니다.
save(release / 'manifest.json', json.dumps(evidence, indent=2).encode())  # 실제 사전 상태입니다.
stopped = False; started = None; stash_id = None  # 예외 시 처리한 단계만 복구합니다.
try:  # 이 경계 안에서만 서비스에 영향을 줍니다.
    stop(data['pid'], command); stopped = True  # 종료 확인 뒤에만 파일을 정리합니다.
    db_snapshot(database, release / 'equipment-before.db'); before = db_state(database)  # logger 종료 후 일관된 사본입니다.
    assert before['integrity'] == 'ok' and before['fk'] == 0  # 손상 DB에 배포하지 않습니다.
    if stash_paths:  # 지정된 파일만 Git의 복구 가능한 보관함으로 이동합니다.
        git('stash','push','--include-untracked','--message','catalog-ui pre-deploy '+release.name,'--',*stash_paths)  # venv/DB/비밀은 포함하지 않습니다.
        stash_id = git('rev-parse','refs/stash'); evidence['stash'] = stash_id  # stash를 삭제하지 않습니다.
    assert not git('diff','--name-only') and not git('diff','--cached','--name-only')  # 예상치 못한 변경이 남으면 중단합니다.
    pull = git('pull','--ff-only','origin','main'); save(release / 'pull.txt', pull.encode())  # 강제 reset 없이 원격 commit으로 진행합니다.
    assert git('rev-parse','HEAD') == data['target']  # 배포 대상 SHA 일치입니다.
    assert all(digest((ROOT / n).read_bytes()) == entry['target'] for n, entry in files.items())  # 모든 런타임 파일을 다시 확인합니다.
    private(release / 'fixture-temp')  # 테스트의 기본/임시 경로도 운영과 분리합니다.
    test_env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT / 'tests')+os.pathsep+str(ROOT), TMPDIR=str(release / 'fixture-temp'), DATABASE_PATH=str(release/'fixture-temp/outer.db'), DATABASE_OPERATION_ROOT=str(release/'fixture-temp/operations'), MAINTENANCE_STATE_PATH=str(release/'fixture-temp/maintenance.json'), EQUIPMENT_ATTACHMENT_ROOT=str(release/'fixture-temp/attachments'), SECRET_KEY='isolated-deploy-fixture', FLASK_DEBUG='0')  # fixture가 직접 설정해도 기본값은 안전합니다.
    with (release / 'linux-tests.log').open('xb') as log:  # 출력은 서버 private에 보존합니다.
        result = subprocess.run([command[0], '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'], cwd=ROOT, env=test_env, stdout=log, stderr=subprocess.STDOUT, timeout=120)  # 기존 전체 Python 회귀입니다.
    evidence['test_exit'] = result.returncode  # 실제 실행 결과입니다.
    assert result.returncode == 0, 'Linux regression failed'  # 실패 상태로 운영 기동하지 않습니다.
    with (release / 'catalog-http.log').open('xb') as log:  # 새 endpoint를 실제 Flask 경계로 검증합니다.
        probe = subprocess.run([command[0], '-B', 'Reports/2026/09/16/catalog-ui-release/catalog_http_probe.py'], cwd=ROOT, env=test_env, stdout=log, stderr=subprocess.STDOUT, timeout=40)  # 합성 DB만 사용합니다.
    evidence['catalog_http_exit'] = probe.returncode; assert probe.returncode == 0, 'catalog HTTP fixture failed'  # 권한/CSRF/감사 원자성입니다.
    assert before == db_state(database), 'production data changed during isolated tests'  # 테스트가 운영 DB를 건드리지 않았는지 확인합니다.
    started = start(command, environment, release, 'service-start')  # 기존과 동일한 실행 형태입니다.
    after = db_state(database); assert after['integrity'] == 'ok' and after['fk'] == 0  # 재시작 이후 DB 검증입니다.
    evidence.update(status='deployed', new_pid=started.pid, health=200, db_integrity=after['integrity'], foreign_key_violations=after['fk'], business_tables_unchanged=before['tables']==after['tables'], row_counts={name: entry['rows'] for name, entry in after['tables'].items()}, head=git('rev-parse','HEAD'))  # 사용자/업무 내용은 출력하지 않습니다.
    evidence['static_checks'] = {}  # 실제 서버가 새 정적 자산을 제공하는지 확인합니다.
    for name in ('static/css/components.css', 'static/js/catalog_requests.js', 'static/js/lineup_registration.js'):  # 이번 변경 자산입니다.
        with urllib.request.urlopen('http://127.0.0.1:5000/' + name, timeout=5) as response: body = response.read(); assert response.status == 200 and digest(body) == files[name]['target']  # 실제 응답 bytes를 대조합니다.
        evidence['static_checks'][name] = True  # 성공 여부만 기록합니다.
    evidence['git_status_after'] = git('status', '--short', '--branch')  # 보존 artifact는 남아도 정상입니다.
    save(release / 'result.json', json.dumps(evidence, indent=2).encode())  # 실제 배포 완료 증거입니다.
except BaseException as error:  # 실행 실패 시 서비스 복구를 시도합니다.
    evidence.update(status='failed', error_type=type(error).__name__, error=str(error)[:300])  # 비밀 없는 배포 오류만 요약합니다.
    if started is not None and started.poll() is None: stop(started.pid, command)  # 이번 새 프로세스만 종료합니다.
    if stopped:  # 기존 프로세스를 내렸을 때만 복구합니다.
        for name, original in originals.items():  # 보존된 코드의 정확한 원문을 복구합니다.
            path = ROOT / name  # 허용된 운영 파일입니다.
            if path.exists(): assert digest(path.read_bytes()) in (files[name]['previous'], files[name]['target']), 'concurrent change prevents rollback: '+name  # 타인 변경을 폐기하지 않습니다.
            if original is None:  # 새 코드도 삭제 대신 실패 증거로 보존합니다.
                if path.exists(): private((release/'failed-new'/name).parent); os.replace(path, release/'failed-new'/name)  # 예상된 새 파일만 이동합니다.
            else: restore_file(path, *original)  # 기존 코드 bytes/모드를 복구합니다.
        recovered = start(command, environment, release, 'service-rollback')  # DB 전체를 되돌리지 않고 이전 앱을 복구합니다.
        evidence.update(rollback_pid=recovered.pid, rollback_health=200, git_status_after=git('status','--short','--branch'))  # HEAD와 코드가 다르면 그대로 보고합니다.
    save(release/'failure.json', json.dumps(evidence, indent=2).encode()); print(json.dumps(evidence)); sys.exit(1)  # 실패를 PASS로 위장하지 않습니다.
print(json.dumps(evidence))  # controller가 최종 결과를 수신합니다.
