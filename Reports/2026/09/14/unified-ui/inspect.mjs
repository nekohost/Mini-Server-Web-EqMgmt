// Read-only preflight for the exact UI release scope; never reads application secrets.
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const files=['static/css/layout.css','static/js/menu_cards.js','static/js/session_timer.js',
    ...['miniserver_frame','index','roadmap_equipment','master_management','users_management','permissions','admin_center','audit_logs','access_logs','access_logs_error_ips','lineup_management','approvals','portal','dashboard','mypage','maintenance_admin','backup_restore'].map(n=>'templates/'+n+'.html')];
const hash=b=>createHash('sha256').update(b).digest('hex');
const local=Object.fromEntries(files.map(n=>[n,hash(readFileSync(n).toString().replaceAll('\r\n','\n'))]));
const script=`import json,sys,hashlib
from pathlib import Path
root=Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
assert Path('/proc/86641/cwd').resolve()==root
data=json.load(sys.stdin)
for name,digest in data.items():
    assert hashlib.sha256((root/name).read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest()==digest, name
print(json.dumps({'pid':86641,'count':len(data),'baselines':data}))
`;
const quote=s=>"'"+s.replaceAll("'","'\\''")+"'";
const r=spawnSync('ssh',['-o','BatchMode=yes','-o','ConnectTimeout=8','eqmgmt-backup','python3 -c '+quote(script)],{input:JSON.stringify(local),encoding:'utf8',timeout:20000});
process.stdout.write(r.stdout||'');process.stderr.write(r.stderr||'');process.exitCode=r.status??1;
