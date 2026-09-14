// Read-only comparison with the preceding release's preserved UI sources.
import {spawnSync} from 'node:child_process';
const script = `from pathlib import Path
import difflib,json,hashlib
r=Path('/home/nekohost/.local/share/mini-server-eqmgmt/releases/ui-responsive-shell-20260914T064237Z')
root=Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
result=json.loads((r/'result.json').read_text())
assert Path('/proc/84781/cwd').resolve()==root
assert all(hashlib.sha256((root/n).read_bytes()).hexdigest()==v['after'] for n,v in result['files'].items())
excluded={'static/js/navigation.js','static/js/menu_cards.js','static/js/session_timer.js','templates/miniserver_frame.html','templates/admin_center.html'}
for n in result['files']:
    if n not in excluded:
        print(''.join(difflib.unified_diff((r/'before'/n).read_text().splitlines(True),(root/n).read_text().splitlines(True),fromfile='before/'+n,tofile='current/'+n)))
`;
const quote = s => "'" + s.replaceAll("'", "'\\''") + "'";
const result = spawnSync('ssh', ['-o','BatchMode=yes','-o','ConnectTimeout=8','eqmgmt-backup','python3 -c '+quote(script)], {encoding:'utf8',timeout:20000});
process.stdout.write(result.stdout || ''); process.stderr.write(result.stderr || '');
process.exitCode=result.status ?? 1;
