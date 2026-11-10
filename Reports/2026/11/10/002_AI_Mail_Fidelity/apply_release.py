"""Apply this exact reviewed code release with the existing production deployment helper."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def main():
    root = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
    release = Path(sys.argv[1]).resolve()
    target = sys.argv[2]
    if socket.gethostname() != 'nkhst-pentium' or release.parent != root/'instance/releases' or not release.name.startswith('20261105-ai-ux-mail-fidelity-'):
        raise RuntimeError('wrong release destination')
    os.chdir(root)
    sys.path.insert(0,str(root/'tools'))
    import deploy_ai_ux_release as deploy
    manifest = json.loads((release/'source-manifest.json').read_bytes())
    def git(*args):
        return subprocess.check_output(['git','-C',str(root),*args],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},stderr=subprocess.PIPE)
    before = git('rev-parse','HEAD').decode().strip()
    assert before==manifest['base'] and len(target)==40 and before!=target
    assert not git('status','--porcelain','--untracked-files=no')
    git('fetch','--quiet','origin','main')
    assert git('rev-parse','FETCH_HEAD').decode().strip()==target and git('rev-parse',target+'^').decode().strip()==before
    assert set(git('diff','--name-only',before,target).decode().splitlines())==set(manifest['files'])
    assert all(hashlib.sha256(git('show',target+':'+n)).hexdigest()==h for n,h in manifest['files'].items())
    def settings_unchanged():
        pairs = [(root/'.env','web.env.before'),(deploy.CONFIG,'worker.env.before')]
        for name in ('equipment-ai-worker.service','equipment-ai-retention.service','equipment-ai-retention.timer'):
            pairs.append((deploy.UNIT/name,name+'.before'))
        return all(src.read_bytes()==(release/backup).read_bytes() for src,backup in pairs)
    assert settings_unchanged() and json.loads((release/'final-copy-summary.json').read_bytes())['status']=='pass'
    pids = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            try:
                deploy.process(int(entry.name))
            except (FileNotFoundError,PermissionError,ProcessLookupError,ValueError):
                continue
            pids.append(int(entry.name))
    assert len(pids)==1, 'exactly one verified web process required'
    if deploy.active_jobs():
        raise RuntimeError('admissions busy; retry after the current work finishes')
    start=time.monotonic()
    started=datetime.now(timezone.utc).isoformat()
    deploy.pause(release,pids[0])
    try:
        git('merge','--ff-only',target)
    except Exception:
        if git('rev-parse','HEAD').decode().strip()==before:
            deploy.activate(release)
        raise
    state=deploy.activate(release)
    assert settings_unchanged() and all(hashlib.sha256((root/n).read_bytes()).hexdigest()==h for n,h in manifest['files'].items())
    result={'base':before,'code':target,'started_utc':started,'activated_utc':state['activated_at_utc'],
            'window_seconds':round(time.monotonic()-start,2),'old_business_rows_preserved':state['old_business_rows_preserved'],
            'old_ai_rows_preserved':state['old_ai_rows_preserved'],'settings_unchanged':True,
            'worker':state['worker'],'retention_timer_enabled':state['retention_timer_enabled'],'db_schema':state['ai_version'],
            'recovery_directory':release.name}
    deploy.record(release/'release-result.json',result)
    print(json.dumps(result))


if __name__=='__main__':
    main()
