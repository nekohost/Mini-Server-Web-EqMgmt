"""Preflight a verified runtime on copied DBs, switch both consumers, and retain recovery state."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess as sp
import sys
import time
import urllib.request

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
BASE = 'dc60ed88a30274b22f1b752849bdd1b7e37db36d'
trial = Path(sys.argv[2]).resolve()
assert trial.parent == Path('/tmp') and trial.name.startswith('eq-provider-security-')
release = Path((trial/'release-path.txt').read_text()).resolve()
assert release.parent == ROOT/'instance/releases' and release.name.startswith('20261110-provider-security-')
runtime = ROOT/'instance/runtimes'/release.name
candidate = trial/'source'
assert socket.gethostname() == 'nkhst-pentium' and os.geteuid() == ROOT.stat().st_uid
os.umask(0o077)
sys.path.insert(0,str(ROOT/'tools'))
import deploy_ai_ux_release as deploy


def git(*args):
    return sp.check_output(['git', *args], cwd=ROOT,text=True).strip()


def web():
    found = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'cwd').resolve()==ROOT and (p/'cmdline').read_bytes().split(b'\0')[1:3]==[b'-u',b'app.py']:
                deploy.process(int(p.name))
                found.append(int(p.name))
        except (OSError, ValueError):
            continue
    return found


def copy_check():
    assert Path(sys.prefix).resolve() == runtime.resolve()
    assert git('rev-parse','HEAD')==BASE
    if not (release/'equipment-before.sqlite3').exists():
        for src,dest in [(ROOT/'.env','web.env.before'),(deploy.CONFIG,'worker.env.before')]+[(deploy.UNIT/n,n+'.before') for n in ('equipment-ai-worker.service','equipment-ai-retention.service','equipment-ai-retention.timer')]:
            deploy.save(release/dest, src.read_bytes())
        deploy.snapshot(ROOT/'equipment.db',release/'equipment-before.sqlite3')
        deploy.snapshot(deploy.AI,release/'assistant-before.sqlite3')
    sys.path.insert(0,str(candidate))
    deploy.CANDIDATE_APP_SOURCE = (candidate/'app.py').read_text()
    result=deploy.check_copy(release)
    from utils.ai_assistant import provider_trust
    assert Path(provider_trust.__file__).resolve().is_relative_to(candidate)
    (trial/'copy-result.json').write_text(json.dumps(result))
    print(json.dumps({k:result[k] for k in ('status','business_tables_preserved','ai_tables_preserved','audit_rows_preserved','lifecycle_rows_preserved','production_databases_modified')}))


def rollback(target):
    """Restore only a verified clean release checkout and the original runtime. Retain live DB writes."""
    sp.run(['systemctl','--user','stop','equipment-ai-worker.service'],check=True)
    for pid in web():
        deploy.process(pid)
        os.kill(pid,signal.SIGTERM)
    for _ in range(150):
        if not web(): break
        time.sleep(.2)
    assert not web()
    venv=ROOT/'.venv'
    if venv.is_symlink():
        assert venv.resolve()==runtime.resolve()
        venv.unlink()
    if (release/'original-venv').is_dir():
        assert not venv.exists()
        (release/'original-venv').rename(venv)
    if git('rev-parse','HEAD') == target:
        assert not git('status','--porcelain','--untracked-files=no')
        git('reset','--keep',BASE)
    assert git('rev-parse','HEAD')==BASE
    env=json.loads((release/'process-environment-before.json').read_text())
    argv=json.loads((release/'process-before.json').read_text())['argv']
    with (release/'rollback-start.log').open('ab') as stream:
        sp.Popen(argv,cwd=ROOT,env=env,stdin=sp.DEVNULL,stdout=stream,stderr=sp.STDOUT,start_new_session=True)
    for _ in range(120):
        try:
            with urllib.request.urlopen('http://127.0.0.1:5000/login',timeout=2) as response:
                if response.status==200:break
        except OSError: time.sleep(.25)
    else: raise RuntimeError('previous app health failed')
    deploy.maintenance('NORMAL')
    sp.run(['systemctl','--user','start','equipment-ai-worker.service','equipment-ai-retention.timer'],check=True)


def activate(target):
    assert len(target)==40 and target.isalnum() and git('rev-parse','HEAD')==BASE
    assert not git('status','--porcelain','--untracked-files=no') and git('branch','--show-current')=='main'
    assert json.loads((trial/'copy-result.json').read_text())['status']=='pass'
    assert [(ROOT/'.env').read_bytes(),deploy.CONFIG.read_bytes()]==[(release/'web.env.before').read_bytes(),(release/'worker.env.before').read_bytes()]
    git('fetch','origin','main')
    assert git('rev-parse','origin/main')==target
    git('merge-base','--is-ancestor',BASE,target)
    assert web() and len(web())==1 and not deploy.active_jobs()
    started = datetime.now(timezone.utc)
    try:
        deploy.pause(release,web()[0])
        git('merge','--ff-only',target)
        assert (ROOT/'.venv').is_dir() and not (ROOT/'.venv').is_symlink()
        (ROOT/'.venv').rename(release/'original-venv')
        (ROOT/'.venv').symlink_to(runtime,target_is_directory=True)
        result=deploy.activate(release)
        assert json.loads((release/'process-before.json').read_text())['pid']!=result['app_pid']
    except Exception:
        if (release/'process-before.json').exists() and (release/'maintenance-before.json').exists():
            # An admission race rejected before the original process was stopped.
            before=json.loads((release/'process-before.json').read_text())['pid']
            if web()==[before] and git('rev-parse','HEAD')==BASE:
                deploy.maintenance('NORMAL')
                sp.run(['systemctl','--user','start','equipment-ai-worker.service'],check=True)
            else:
                rollback(target)
        raise
    result.update(commit=target,window_seconds=round((datetime.now(timezone.utc)-started).total_seconds(),2),
                  runtime=runtime.name,baseline=BASE)
    (trial/'release-result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if sys.argv[1]=='copy':
    copy_check()
elif sys.argv[1]=='activate':
    activate(sys.argv[3])
else:
    raise ValueError('unknown release step')
