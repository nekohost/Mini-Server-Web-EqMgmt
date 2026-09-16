// [역할] 도입 교차검토에서 발견한 누락을 실제 CLI와 격리 Git 저장소로 재현한다.
// [의존성 관계] Node test/assert/fs 및 Git. 운영 작업트리와 DB는 변경하지 않는다.
// [변경 시 영향도] 주석 기준선, KO 변경 범위, commit 언어 계약의 회귀를 검출한다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const body = `[MINI-COMMENT: TEST.VALUE]\n[EN rev.1]\n[Role] Returns a value.\n[Dependencies] No external dependency.\n[Impact] Changes the returned value.\n[KO rev.1]\n[역할] 값을 반환한다.\n[의존성 관계] 외부 의존성이 없다.\n[변경 시 영향도] 반환값에 영향을 준다.`;
const source = body.split('\n').map(line => `# ${line}`).join('\n') + '\n\ndef value():\n    return 1\n';
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eqmgmt-comment-review-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const put = (file, value) => { const p = path.join(root, file); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, value); };
  const get = file => fs.readFileSync(path.join(root, file), 'utf8');
  const run = (exe, args) => spawnSync(exe, args, { cwd: root, encoding: 'utf8', env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' } });
  const cli = (name, ...args) => run(process.execPath, [path.join(here, name), ...args]);
  const sync = (...args) => cli('comment-sync.mjs', ...args, `--root=${root}`, '--config=config.json', '--state=state.json');
  const guard = (...args) => cli('gemini-diff-guard.mjs', ...args, `--root=${root}`, '--snapshot=audit.json');
  const git = (...args) => { const r = run('git', args); assert.equal(r.status, 0, r.stderr); return r.stdout; };
  put('a.py', source);
  put('config.json', JSON.stringify({ schema_version: 1, roots: ['a.py'], extensions: ['.py'] }));
  const baseline = () => { const r = sync('baseline', '--accept-audited'); assert.equal(r.status, 0, r.stderr); };
  const init = () => { git('init', '-q'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.test'); git('add', '.'); git('commit', '-qm', 'fixture'); };
  return { root, put, get, cli, sync, guard, git, baseline, init };
}
function fails(r, pattern) { assert.notEqual(r.status, 0, r.stdout); if (pattern) assert.match(r.stdout + r.stderr, pattern); }

test('baseline cannot erase a source/revision violation', t => {
  const f = fixture(t); f.baseline(); const before = f.get('state.json');
  f.put('a.py', source.replace('return 1', 'return 2'));
  fails(f.sync('baseline', '--accept-audited'), /REVISION-SUSPECT/);
  assert.equal(f.get('state.json'), before);
});
test('revision rollback is rejected by check and baseline', t => {
  const f = fixture(t); f.put('a.py', source.replaceAll('rev.1', 'rev.2')); f.baseline(); f.put('a.py', source);
  fails(f.sync('check'), /REVISION-REGRESSION/); fails(f.sync('baseline', '--accept-audited'));
});
test('matching advanced revisions still require an audited baseline', t => {
  const f = fixture(t); f.baseline(); f.put('a.py', source.replaceAll('rev.1', 'rev.2').replace('return 1', 'return 2'));
  fails(f.sync('check'), /AUDIT-REQUIRED/); f.baseline(); assert.equal(f.sync('check').status, 0);
});
test('a removed ID cannot silently disappear during baseline refresh', t => {
  const f = fixture(t); f.put('a.py', source + source.replace('TEST.VALUE', 'TEST.SECOND')); f.baseline(); f.put('a.py', source);
  fails(f.sync('baseline', '--accept-audited'), /MISSING-COMMENT/);
});
test('malformed markers and empty metadata are not accepted as audited', t => {
  const f = fixture(t);
  for (const candidate of [source.replace('[EN rev.1]', '[EN rev.1]\n# [EN rev.1]'), source.replace('TEST.VALUE', 'bad id'), source.replace('[Role] Returns a value.', '[Role]')]) {
    f.put('a.py', candidate); fails(f.sync('baseline', '--accept-audited'));
  }
});
test('missing configured roots and corrupt state fail closed', t => {
  const f = fixture(t); f.put('config.json', JSON.stringify({ schema_version: 1, roots: ['missing.py'], extensions: ['.py'] })); fails(f.sync('check'));
  f.put('config.json', JSON.stringify({ schema_version: 1, roots: ['a.py'], extensions: ['.py'] }));
  f.put('state.json', '{}'); fails(f.sync('baseline', '--accept-audited'));
});
test('guard detects staged code even when the working copy is restored', t => {
  const f = fixture(t); f.init(); assert.equal(f.guard('snapshot').status, 0);
  f.put('a.py', source.replace('return 1', 'return 2')); f.git('add', 'a.py'); f.put('a.py', source);
  fails(f.guard('check'), /INDEX|index|staged/);
});
test('guard detects modification of a preexisting Korean filename', t => {
  const f = fixture(t); f.put('한글 기록.txt', 'original'); f.init(); f.put('한글 기록.txt', 'other worker');
  assert.equal(f.guard('snapshot').status, 0); f.put('한글 기록.txt', 'changed after snapshot'); fails(f.guard('check'), /한글 기록/);
});
test('guard preserves a preexisting dirty file and permits staged KO edits', t => {
  const f = fixture(t); f.put('한글 기록.txt', 'original'); f.init(); f.put('한글 기록.txt', 'other worker');
  assert.equal(f.guard('snapshot').status, 0); f.put('a.py', source.replace('값을 반환한다.', '검증된 값을 반환한다.')); f.git('add', 'a.py');
  const r = f.guard('check'); assert.equal(r.status, 0, r.stdout + r.stderr);
});
test('an assigned Python string is not a docstring translation surface', t => {
  const f = fixture(t); const data = `TEXT = """${body}"""\n`;
  f.put('a.py', data); f.init(); assert.equal(f.guard('snapshot').status, 0); f.put('a.py', data.replace('값을 반환한다.', '실행 데이터 변경'));
  fails(f.guard('check'));
});
test('comment-shaped text in a JS template is not a translation surface', t => {
  const f = fixture(t); const data = 'const text = `\n' + body.split('\n').map(line => `// ${line}`).join('\n') + '\n`;\n';
  f.put('a.js', data); f.init(); assert.equal(f.guard('snapshot').status, 0); f.put('a.js', data.replace('값을 반환한다.', '실행 데이터 변경'));
  fails(f.guard('check'));
});
test('EN-only handoff can gain a properly delimited KO section', t => {
  const f = fixture(t); const ko = source.indexOf('# [KO'); const code = source.indexOf('\n\ndef');
  f.put('a.py', source.slice(0, ko).trimEnd() + source.slice(code)); f.init(); assert.equal(f.guard('snapshot').status, 0); f.put('a.py', source);
  const r = f.guard('check'); assert.equal(r.status, 0, r.stdout + r.stderr);
});
test('source files cannot bypass the guard via allow-path', t => {
  const f = fixture(t); f.init(); assert.equal(f.guard('snapshot').status, 0); f.put('a.py', source.replace('return 1', 'return 2'));
  fails(f.guard('check', '--allow-path=a.py'));
});
test('HTML server-template expressions in KO require implementation review', t => {
  const f = fixture(t); const data = `<!--\n${body}\n-->\n<p>value</p>\n`;
  f.put('a.html', data); f.init(); assert.equal(f.guard('snapshot').status, 0); f.put('a.html', data.replace('값을 반환한다.', '{{ value() }}'));
  fails(f.guard('check'));
});
test('snapshot cannot overwrite an existing file', t => {
  const f = fixture(t); f.init(); f.put('audit.json', 'preserve'); fails(f.guard('snapshot')); assert.equal(f.get('audit.json'), 'preserve');
});
test('commit checker accepts Korean multiline message and checks body language', t => {
  const f = fixture(t);
  assert.equal(f.cli('commit-message-check.mjs', 'fix: 검사 보완\n\n검증 결과를 기록합니다.').status, 0);
  fails(f.cli('commit-message-check.mjs', 'fix: 검사 보완\n\nThis prose is English only.'));
  fails(f.cli('commit-message-check.mjs', 'Merged anything'));
});

test('normal Python docstring, JS block and HTML KO edits remain supported', t => {
  const f = fixture(t);
  const samples = { 'doc.py': `"""${body}"""\nVALUE = 1\n`, 'block.mjs': `/*\n${body}\n*/\nexport const value = 1;\n`, 'view.html': `<!--\n${body}\n-->\n<p>value</p>\n` };
  for (const [file, text] of Object.entries(samples)) f.put(file, text);
  f.init(); assert.equal(f.guard('snapshot').status, 0);
  for (const [file, text] of Object.entries(samples)) f.put(file, text.replace('값을 반환한다.', '값 하나를 반환한다.'));
  const r = f.guard('check'); assert.equal(r.status, 0, r.stdout + r.stderr);
});
test('block terminator injection is outside KO-only scope', t => {
  const f = fixture(t); const text = `/*\n${body}\n*/\nexport const value = 1;\n`;
  f.put('a.js', text); f.init(); assert.equal(f.guard('snapshot').status, 0);
  f.put('a.js', text.replace('값을 반환한다.', '*/\nexport const extra = 2;\n/* 변경'));
  fails(f.guard('check'));
});
test('invalid marker ordering and unsafe revision integers are rejected', t => {
  const f = fixture(t);
  for (const text of [source.replace('rev.1', 'rev.99999999999999999999'), source.replace('# [Impact]', '# [KO rev.1]\n# [Impact]'), source.replace('[EN rev.1]', '[EN rev.0]')]) {
    f.put('a.py', text); fails(f.sync('baseline', '--accept-audited'));
  }
});
test('guard rejects corrupted snapshots and file rename/deletion', t => {
  const f = fixture(t); f.init(); assert.equal(f.guard('snapshot').status, 0);
  const original = f.get('audit.json'); const state = JSON.parse(original); state.schema_version = 0; f.put('audit.json', JSON.stringify(state)); fails(f.guard('check'));
  f.put('audit.json', original); f.git('mv', 'a.py', 'renamed.py'); fails(f.guard('check'));
});
test('EN-only Python docstring can be translated without changing executable code', t => {
  const f = fixture(t); const en = body.slice(0, body.indexOf('[KO')).trimEnd();
  f.put('a.py', `def value():\n    """${en}\n    """\n    return 1\n`); f.init(); assert.equal(f.guard('snapshot').status, 0);
  f.put('a.py', `def value():\n    """${body}\n    """\n    return 1\n`);
  const r = f.guard('check'); assert.equal(r.status, 0, r.stdout + r.stderr);
});
test('comment-shaped data inside a Jinja string is not a KO surface', t => {
  const f = fixture(t); const text = `{{ "<!--\n${body}\n-->" }}\n`;
  f.put('a.html', text); f.init(); assert.equal(f.guard('snapshot').status, 0);
  f.put('a.html', text.replace('값을 반환한다.', '실행 문자열 수정')); fails(f.guard('check'));
});
test('baseline can record an actual auditor and existing report, never a fabricated missing report', t => {
  const f = fixture(t); fails(f.sync('baseline', '--accept-audited', '--auditor=Fixture', '--audit-report=Reports/missing.md'));
  f.put('Reports/audit.md', '# 감사 결과\n소스 대조 완료.\n');
  const r = f.sync('baseline', '--accept-audited', '--auditor=Fixture', '--audit-report=Reports/audit.md');
  assert.equal(r.status, 0, r.stderr); assert.deepEqual(JSON.parse(f.get('state.json')).audit, { auditor: 'Fixture', report: 'Reports/audit.md' });
});
test('an explicitly allowed new audit report may be staged', t => {
  const f = fixture(t); f.init(); assert.equal(f.guard('snapshot').status, 0); f.put('Reports/audit.md', '# 감사\n'); f.git('add', 'Reports/audit.md');
  const r = f.guard('check', '--allow-path=Reports/audit.md'); assert.equal(r.status, 0, r.stdout + r.stderr);
});
test('unterminated tracked Python docstring cannot become a baseline', t => {
  const f = fixture(t); f.put('a.py', `"""${body}\n`); fails(f.sync('baseline', '--accept-audited'), /unterminated/);
});
