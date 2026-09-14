// Stage only candidate source/test artifacts in a private Linux fixture directory.
import {readFileSync,readdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const baseline=JSON.parse(readFileSync(new URL('baselines.json',import.meta.url),'utf8')).baselines;
const files={};
for(const name of [...Object.keys(baseline),...readdirSync('tests').filter(n=>n.endsWith('.py')).map(n=>'tests/'+n)]) {
    const content=readFileSync(name);files[name]={content:content.toString('base64'),sha256:createHash('sha256').update(content).digest('hex')};
}
const quote=s=>"'"+s.replaceAll("'","'\\''")+"'";
const script=readFileSync(new URL('linux-check.py',import.meta.url),'utf8');
const r=spawnSync('ssh',['-o','BatchMode=yes','-o','ConnectTimeout=8','eqmgmt-backup',
    '/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python -c '+quote(script)],
    {input:JSON.stringify({baseline,files}),encoding:'utf8',timeout:180000,maxBuffer:5*1024*1024});
process.stdout.write(r.stdout||'');process.stderr.write(r.stderr||'');process.exitCode=r.status??1;
