"""Private candidate fixture; no live app import, DB writes, mail, or listener."""
import ast, base64, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
RELEASES = Path('/home/nekohost/.local/share/mini-server-eqmgmt/releases')
data = json.load(sys.stdin)
assert ROOT.resolve() == ROOT and RELEASES.resolve() == RELEASES
assert Path('/proc/88513/cwd').resolve() == ROOT
for name, digest in data['baseline'].items():
    if digest is None: assert not (ROOT/name).exists(), name
    else: assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() == digest, name
os.umask(0o077)
candidate = Path(tempfile.mkdtemp(prefix='menu-workflows-fixture-',dir=RELEASES))
assert candidate.resolve().parent == RELEASES
for folder in ['utils','templates','static','Resources']:
    shutil.copytree(ROOT/folder,candidate/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for name, entry in data['files'].items():
    relative=Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts
    assert name in data['baseline'] or (relative.parent == Path('tests') and relative.suffix == '.py')
    content=base64.b64decode(entry['content'],validate=True)
    assert hashlib.sha256(content).hexdigest()==entry['sha256']
    target=candidate/relative; target.parent.mkdir(parents=True,exist_ok=True)
    assert target.parent.resolve().is_relative_to(candidate)
    target.write_bytes(content)
    if relative.suffix == '.py': ast.parse(content,filename=name)
manifest={'candidate':str(candidate),'files':{n:e['sha256'] for n,e in data['files'].items()}}
(candidate/'source-manifest.json').write_text(json.dumps(manifest,indent=2))
env=dict(os.environ,PYTHONPATH=str(candidate)+':'+str(candidate/'tests'),PYTHONDONTWRITEBYTECODE='1',
    DATABASE_PATH=str(candidate/'unused-default.db'),DATABASE_OPERATION_ROOT=str(candidate/'default-operations'),
    MAINTENANCE_STATE_PATH=str(candidate/'default-maintenance.json'),EQUIPMENT_ATTACHMENT_ROOT=str(candidate/'default-attachments'),
    SECRET_KEY='isolated-candidate-default-key')
result=subprocess.run([str(ROOT/'.venv/bin/python'),'-m','unittest','discover','-s','tests','-p','test_*.py'],
    cwd=candidate,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150)
(candidate/'unittest.log').write_text(result.stdout)
print(result.stdout)
manifest['test_exit_code']=result.returncode
if result.returncode == 0:
    rehearsal=subprocess.run([str(ROOT/'.venv/bin/python'),'tests/rehearse_menu_workflow_db.py'],cwd=candidate,
        env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
    (candidate/'rehearsal.log').write_text(rehearsal.stdout)
    print(rehearsal.stdout)
    manifest['rehearsal_exit_code']=rehearsal.returncode
(candidate/'check-result.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest))
sys.exit(result.returncode or manifest.get('rehearsal_exit_code',0))
