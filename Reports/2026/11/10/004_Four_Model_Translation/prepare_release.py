"""Verify the selected sources on an isolated copy of both databases and preserve rollback material."""
from datetime import datetime, timezone
import hashlib, json, os, secrets
from pathlib import Path
import socket, subprocess, sys

root=Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
trial=Path(sys.argv[1]).resolve()
candidate=trial/'selected/candidate'
assert socket.gethostname()=='nkhst-pentium' and os.geteuid()==root.stat().st_uid
manifest=json.loads((trial/'source-manifest.json').read_bytes())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==manifest['base']
for name,value in manifest['files'].items():assert hashlib.sha256((candidate/name).read_bytes()).hexdigest()==value
os.umask(0o077)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
release=root/'instance/releases'/('20261105-ai-ux-mail-fidelity-'+stamp+'-'+secrets.token_hex(3))
release.mkdir(mode=0o700)
sys.path.insert(0,str(root/'tools'))
import deploy_ai_ux_release as deploy
assert not deploy.active_jobs()
deploy.record(release/'source-manifest.json',manifest)
for source,dest in [(root/'.env','web.env.before'),(deploy.CONFIG,'worker.env.before')]+[(deploy.UNIT/n,n+'.before') for n in ('equipment-ai-worker.service','equipment-ai-retention.service','equipment-ai-retention.timer')]:
    deploy.save(release/dest,source.read_bytes())
deploy.snapshot(root/'equipment.db',release/'equipment-before.sqlite3')
deploy.snapshot(deploy.AI,release/'assistant-before.sqlite3')
sys.path.insert(0,str(candidate))
deploy.CANDIDATE_APP_SOURCE=(candidate/'app.py').read_text()
res=deploy.check_copy(release)
import utils.ai_assistant.translation as live_test_module
assert Path(live_test_module.__file__).resolve().is_relative_to(candidate)
assert res['status']=='pass' and res['production_databases_modified'] is False
summary={k:v for k,v in res.items() if k!='copy'}
deploy.record(release/'final-copy-summary.json',summary)
(trial/'release-path.txt').write_text(str(release))
print(release)
