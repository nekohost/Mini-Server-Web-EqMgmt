// Exact UI artifact release; deliberately does not commit/push unrelated local changes.
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../../../../../', import.meta.url));
const baselines = JSON.parse(readFileSync(new URL('auth-label-baselines.json', import.meta.url), 'utf8'));
const files = Object.keys(baselines);
const hash = data => createHash('sha256').update(data).digest('hex');
const gitRead = args => {
    const result = spawnSync(process.execPath, ['.agent-governance/tooling/git-readonly.mjs', '--', ...args], {cwd: root, encoding: 'utf8'});
    if (result.status !== 0) throw new Error('read-only git failed');
    return result.stdout;
};
if (!['check', 'approved'].includes(process.env.EQM_DEPLOY_AUTH_LABELS)) throw new Error('Set EQM_DEPLOY_AUTH_LABELS=check or approved for this release.');
const data = {apply: process.env.EQM_DEPLOY_AUTH_LABELS === 'approved', head: gitRead(['rev-parse', 'HEAD']).trim(), pid: 90538, files: {}};
for (const name of files) {
    const content = readFileSync(path.join(root, name));
    data.files[name] = {content: content.toString('base64'), sha256: hash(content),
        baseline: baselines[name]};
}
const script = readFileSync(new URL('deploy-auth-labels.py', import.meta.url), 'utf8');
const quote = s => "'" + s.replaceAll("'", "'\\''") + "'";
const result = spawnSync('ssh', ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'eqmgmt-backup',
    '/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python -c ' + quote(script)],
    {input: JSON.stringify(data), encoding: 'utf8', timeout: 100000, maxBuffer: 4 * 1024 * 1024});
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
