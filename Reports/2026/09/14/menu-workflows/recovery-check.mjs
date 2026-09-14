// Exercise only targeted metadata rollback on a second private rehearsal copy.
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
const helpers=readFileSync(new URL('deploy.py',import.meta.url),'utf8').split('data = json.load(sys.stdin)')[0];
const script=helpers+`
import shutil
trial = TESTED / 'rollback-rehearsal.db'
assert not trial.exists()
shutil.copy2(TESTED / 'rehearsal.db', trial)
before = metadata(TESTED / 'rehearsal-before.db')
business = db_state(trial)
rollback_metadata(trial, before)
assert metadata(trial) == before and db_state(trial) == business
rollback_metadata(trial, before)
print(json.dumps({'status':'pass','targeted_metadata_rollback':True,'repeat_noop':True,'business_counts_unchanged':True,
                  'candidate':str(TESTED),'linux':json.loads((TESTED/'check-result.json').read_text()),
                  'rehearsal':json.loads((TESTED/'rehearsal-result.json').read_text())}))
`;
const quote=s=>"'"+s.replaceAll("'","'\\''")+"'";
const r=spawnSync('ssh',['-o','BatchMode=yes','-o','ConnectTimeout=8','eqmgmt-backup',
    '/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python -c '+quote(script)],{encoding:'utf8',timeout:30000,maxBuffer:1000000});
process.stdout.write(r.stdout||'');process.stderr.write(r.stderr||'');process.exitCode=r.status??1;
