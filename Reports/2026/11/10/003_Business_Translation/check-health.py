"""Recheck public endpoints and the pre-release audit/chat rows after the two authenticated requests."""
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import sqlite3
import subprocess as sp
import sys

root=Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
release=Path(sys.argv[1]).resolve()
assert socket.gethostname()=='nkhst-pentium' and release.parent==root/'instance/releases'
sys.path.insert(0,str(root/'tools'))
import deploy_ai_ux_release as deploy

maintenance=json.loads(deploy.MAINTENANCE.read_bytes())['state']
assert maintenance=='NORMAL'
units={n:sp.check_output(['systemctl','--user','is-active',n],text=True).strip()
       for n in ('equipment-ai-worker.service','equipment-ai-retention.timer')}
assert set(units.values())=={'active'}
http={path:int(sp.check_output(['curl','--silent','--show-error','-o','/dev/null','-w','%{http_code}','https://nekohost.org'+path],text=True))
      for path in ['/login','/assistant','/api/ai/capabilities']}
assert http=={'/login':200,'/assistant':302,'/api/ai/capabilities':401}
deploy.audit_preserved(release/'equipment-quiesced.sqlite3',root/'equipment.db')
added={}
with sqlite3.connect(deploy.AI.as_uri()+'?mode=ro',uri=True) as db:
    db.execute('BEGIN')
    db.execute('ATTACH DATABASE ? AS previous',((release/'assistant-quiesced.sqlite3').as_uri()+'?mode=ro',))
    for t in ('conversations','jobs','messages','message_steps','proposals','ai_lifecycle_operations','ai_lifecycle_tombstones'):
        delta,missing=db.execute('SELECT (SELECT COUNT(*) FROM main.'+t+')-(SELECT COUNT(*) FROM previous.'+t+'),'
            'EXISTS(SELECT * FROM previous.'+t+' EXCEPT SELECT * FROM main.'+t+')').fetchone()
        assert not missing,t
        added[t]=delta
    assert db.execute('PRAGMA quick_check').fetchone()==('ok',)
result={'at_utc':datetime.now(timezone.utc).isoformat(),'head':sp.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),
        'maintenance':maintenance,'units':units,'http':http,'in_flight':deploy.active_jobs(),'net_added':added,
        'audit_preserved':True,'previous_ai_rows_preserved':True}
deploy.record(release/'final-health.json',result)
print(json.dumps(result))
