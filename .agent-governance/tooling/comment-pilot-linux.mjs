// [역할] 로컬 파일럿을 메모리로 전송해 지정된 Linux의 격리 Python fixture에서 검증한다.
// [의존성 관계] 사용자 설정 SSH alias와 Python3, Git 읽기 보호 wrapper. 원격 파일 쓰기 없음.
// [변경 시 영향도] 앱 import/DB 연결/서비스 재시작 없이 주석 계약과 실행 AST 보존을 확인한다.
import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../../', import.meta.url));
const before = spawnSync(process.execPath, ['.agent-governance/tooling/git-readonly.mjs', '--', 'show', 'HEAD:utils/lineup_node_service.py'], { cwd: root, encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 });
if (before.status !== 0) throw new Error(before.stderr);
const fixture = fs.readFileSync(new URL('./comment-pilot.test.py', import.meta.url)).toString('base64');
const result = spawnSync('ssh', ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', process.argv[2] ?? 'eqmgmt-backup',
  `python3 -B -c "import base64; exec(compile(base64.b64decode('${fixture}'), '<isolated-audit>', 'exec'))" --stdin`], {
  cwd: root, encoding: 'utf8', timeout: 30000,
  input: JSON.stringify({ source: fs.readFileSync(new URL('../../utils/lineup_node_service.py', import.meta.url), 'utf8'), before: before.stdout }),
});
process.stdout.write(result.stdout ?? '');
process.stderr.write(result.stderr ?? '');
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
