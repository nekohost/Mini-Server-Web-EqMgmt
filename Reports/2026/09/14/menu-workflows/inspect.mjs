// Read-only release baselines and menu/approval structure; no identities or request bodies.
import {readFileSync, existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const files=['app.py','static/css/layout.css','static/js/menu_cards.js','static/js/session_timer.js',
    'static/js/permissions.js','static/js/my_approvals.js',
    ...['miniserver_frame','index','master_management','permissions','admin_center','audit_logs','access_logs','access_logs_error_ips','lineup_management','approvals','mypage','my_approvals'].map(n=>'templates/'+n+'.html')];
const hash=b=>createHash('sha256').update(b).digest('hex');
const local=Object.fromEntries(files.map(n=>[n,existsSync(n)?hash(readFileSync(n).toString().replaceAll('\r\n','\n')):null]));
const script=`import json,sys,hashlib,sqlite3
from pathlib import Path
root=Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
assert Path('/proc/88513/cwd').resolve()==root
data=json.load(sys.stdin)
for name,digest in data.items():
    if digest is None: assert not (root/name).exists(),name
    else: assert hashlib.sha256((root/name).read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest()==digest,name
with sqlite3.connect((root/'equipment.db').as_uri()+'?mode=ro',uri=True) as c:
    menus=c.execute('SELECT MenuCode,MenuName,Url,ParentMenuCode,SortOrder FROM menus ORDER BY MenuId').fetchall()
    permissions=c.execute('SELECT Role,MenuCode,IsAllowed FROM role_menu_permissions ORDER BY Role,MenuCode').fetchall()
    approvals=c.execute('SELECT RequestType,Status,COUNT(*) FROM approval_requests GROUP BY RequestType,Status').fetchall()
print(json.dumps({'pid':88513,'baselines':data,'menus':menus,'permissions':permissions,'approval_counts':approvals}))
`;
const quote=s=>"'"+s.replaceAll("'","'\\''")+"'";
const r=spawnSync('ssh',['-o','BatchMode=yes','-o','ConnectTimeout=8','eqmgmt-backup','python3 -c '+quote(script)],{input:JSON.stringify(local),encoding:'utf8',timeout:20000});
process.stdout.write(r.stdout||'');process.stderr.write(r.stderr||'');process.exitCode=r.status??1;
