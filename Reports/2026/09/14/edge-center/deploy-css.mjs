// One-file correction of the previously approved Edge deployment. No restart/DB writes.
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const content = readFileSync(new URL('../../../../../static/css/layout.css', import.meta.url));
const sha256 = createHash('sha256').update(content).digest('hex');
if (process.env.EQM_DEPLOY_EDGE_CENTER !== 'approved') throw new Error('Approved correction required');
const script = [
    'import base64,hashlib,json,os,stat,sys,urllib.request',
    'from pathlib import Path',
    'from datetime import datetime,timezone',
    'p=Path("/home/nekohost/services/Mini-Server-Web-EqMgmt/static/css/layout.css")',
    'base=Path("/home/nekohost/.local/share/mini-server-eqmgmt/releases")',
    'assert p.resolve()==p and base.resolve()==base and p.stat().st_uid==os.getuid()',
    'data=json.load(sys.stdin)',
    'old=p.read_bytes(); new=base64.b64decode(data["content"],validate=True)',
    'sha=lambda b:hashlib.sha256(b).hexdigest()',
    'assert sha(old)=="afc2f89aaf6648b335a0c7597ebc5f5b1cb2c6947a985546419068ffb1a0e06e", "previous deployment mismatch"',
    'assert sha(new)==data["sha256"]',
    'mode=stat.S_IMODE(p.stat().st_mode)',
    'release=base/("edge-center-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))',
    'release.mkdir(mode=0o700)',
    'def private(name,b):',
    '    with os.fdopen(os.open(release/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),"wb") as f: f.write(b)',
    'private("layout.before.css",old); private("layout.after.css",new)',
    'def replace(b):',
    '    tmp=p.with_name("layout.css.edge-center-"+str(os.getpid()))',
    '    with os.fdopen(os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode),"wb") as f:',
    '        f.write(b); f.flush(); os.fsync(f.fileno())',
    '    os.chmod(tmp,mode); os.replace(tmp,p)',
    'try:',
    '    replace(new)',
    '    with urllib.request.urlopen("http://127.0.0.1:5000/static/css/layout.css",timeout=5) as response:',
    '        assert response.status==200 and sha(response.read())==data["sha256"]',
    'except BaseException:',
    '    if sha(p.read_bytes())==data["sha256"]: replace(old)',
    '    raise',
    'result={"status":"deployed","release":str(release),"before_sha256":sha(old),"after_sha256":sha(new),"restart":False,"db_write":False}',
    'private("result.json",json.dumps(result,indent=2).encode()); print(json.dumps(result))'
].join('\n');
const quote = s => "'" + s.replaceAll("'", "'\\''") + "'";
const result = spawnSync('ssh', ['-o','BatchMode=yes','-o','ConnectTimeout=8','eqmgmt-backup',
    '/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python -c ' + quote(script)],
    {input: JSON.stringify({content: content.toString('base64'), sha256}), encoding:'utf8', timeout:20000});
if (result.status !== 0) {
    process.stderr.write(result.stderr || 'release failed');
    process.exitCode = 1;
} else {
    const evidence = JSON.parse(result.stdout);
    writeFileSync(new URL('deployment.json',import.meta.url),JSON.stringify(evidence,null,2)+'\n');
    console.log(JSON.stringify(evidence));
}

