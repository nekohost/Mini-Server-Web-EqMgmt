// Read-only final audit; output booleans/counts, never user rows or credentials.
import {readFileSync,writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const release=JSON.parse(readFileSync(new URL('deployment.json',import.meta.url),'utf8'));
const labels=JSON.parse(readFileSync(new URL('auth-label-deployment.json',import.meta.url),'utf8'));
const expected={...release.files,...labels.files};
for(const [name,hashes] of Object.entries(expected))
    assert.equal(createHash('sha256').update(readFileSync(name)).digest('hex'),hashes.after,name+': local source changed');
const helpers=readFileSync(new URL('deploy.py',import.meta.url),'utf8').split('data = json.load(sys.stdin)')[0];
const script=helpers+`
import re
release = Path(${JSON.stringify(release.release)})
labels = Path(${JSON.stringify(labels.release)})
first = json.loads((release/'result.json').read_text())
last = json.loads((labels/'result.json').read_text())
files = dict(first['files'],**last['files'])
proc = Path('/proc/'+str(last['new_pid']))
live = sqlite3.connect((ROOT/'equipment.db').as_uri()+'?mode=ro',uri=True)
old = sqlite3.connect((release/'equipment-before.db').as_uri()+'?mode=ro',uri=True)
tables = ('categories','manufacturers','equipment','equipments','equipment_options','lineup_nodes',
          'equipment_files','equipment_imports','equipment_notification_log','approval_requests','equipments_audit_log',
          'email_verifications','password_resets')
same = {name:live.execute('SELECT * FROM '+name+' ORDER BY rowid').fetchall()==old.execute('SELECT * FROM '+name+' ORDER BY rowid').fetchall() for name in tables}
columns = 'UserId,LoginId,Role,Password,Name,NickName,Email'
identities = live.execute('SELECT '+columns+' FROM users ORDER BY UserId').fetchall()==old.execute('SELECT '+columns+' FROM users ORDER BY UserId').fetchall()
before = {row[0]:json.loads(row[1] or '{}') for row in old.execute('SELECT UserId,PreferencesJSON FROM user_settings')}
after = {row[0]:json.loads(row[1] or '{}') for row in live.execute('SELECT UserId,PreferencesJSON FROM user_settings')}
def effective(value):
    return dict(value,theme=value.get('theme','system'),layout_skin=value.get('layout_skin','standard'),deadline_email_opt_in=value.get('deadline_email_opt_in',False))
settings = all(effective(before.get(uid,{}))==effective(after.get(uid,{})) for uid in before.keys()|after.keys())
migration = verify_metadata(metadata(release/'equipment-before.db'),metadata(ROOT/'equipment.db'))
stable_metadata = metadata(labels/'equipment-before.db')==metadata(ROOT/'equipment.db')
result = {'pid':last['new_pid'],'cwd_matches':(proc/'cwd').resolve()==ROOT,
          'files_match':all(sha((ROOT/n).read_bytes())==v['after'] for n,v in files.items()),'file_count':len(files),
          'integrity':live.execute('PRAGMA integrity_check').fetchone()[0],
          'foreign_key_violations':len(live.execute('PRAGMA foreign_key_check').fetchall()),
          'business_rows_identical':same,'user_identity_role_password_unchanged':identities,
          'all_users_effective_preferences_restored':settings,'migration':migration,'second_start_metadata_unchanged':stable_metadata,
          'startup_error_markers':sum(len(re.findall(r'Traceback|ERROR|Fatal',(folder/'service-start.log').read_text())) for folder in (release,labels))}
assert all(same.values()) and identities and settings and stable_metadata
assert result['cwd_matches'] and result['files_match'] and result['integrity']=='ok' and result['foreign_key_violations']==0 and result['startup_error_markers']==0
print(json.dumps(result))
`;
const quote=s=>"'"+s.replaceAll("'","'\\''")+"'";
const r=spawnSync('ssh',['-o','BatchMode=yes','-o','ConnectTimeout=8','eqmgmt-backup',
    '/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python -c '+quote(script)],{encoding:'utf8',timeout:30000,maxBuffer:1000000});
if(r.status!==0)throw new Error('Postflight failed: '+(r.stderr||r.error));
const evidence=JSON.parse(r.stdout);
evidence.domainLabels={};
for(const [route,label] of [['/register','회원가입'],['/reset_password','비밀번호 재설정']]) {
    const response=await fetch('https://nekohost.org'+route);
    assert.equal(response.status,200);
    const html=await response.text();
    assert.ok(html.includes('<title>'+label+' -'));
    assert.ok(!/<title>[^<]*Staging|<h1[^>]*>[^<]*Staging/.test(html));
    evidence.domainLabels[route]=true;
}
for(const path of ['/api/my_approvals','/api/permissions']) assert.equal((await fetch('https://nekohost.org'+path)).status,401);
evidence.unauthenticatedApiDenied=true;
writeFileSync(new URL('postflight.json',import.meta.url),JSON.stringify(evidence,null,2)+'\n');
console.log(JSON.stringify(evidence));
