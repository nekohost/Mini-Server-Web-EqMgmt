// [역할] 실제 CLI의 입력·역할·실패 경계 회귀. [의존성 관계] governance-tool. [변경 시 영향도] Rule 9-1/9-3.
import test from 'node:test'; // 독립 시나리오를 집계한다.
import assert from 'node:assert/strict'; // 기대값 차이를 실패로 처리한다.
import { spawnSync } from 'node:child_process'; // 읽기 전용 CLI를 실행한다.
import { fileURLToPath } from 'node:url'; // 현재 후보 도구 위치를 기준으로 한다.
import path from 'node:path'; // 절대·상대 경로를 구성한다.
import fs from 'node:fs'; // 격리된 symlink 경계 fixture를 준비한다.
import os from 'node:os'; // 운영 저장소 밖의 전용 임시 공간을 선택한다.
import { classifyPaths } from './context-input.mjs'; // 경계 검사만 독립 실행한다.

const cli = fileURLToPath(new URL('./governance-tool.mjs', import.meta.url)); // 실행 위치에 의존하지 않는다.
const root = path.resolve(path.dirname(cli), '../..'); // 검사 대상 거버넌스 프로젝트 루트다.
// [역할] CLI 결과를 파싱한다. [의존성 관계] child process. [변경 시 영향도] 실패 pack 부재 확인.
function run(args, expected = 0) {
  const result = spawnSync(process.execPath, [cli, ...args], { encoding: 'utf8' }); // 파일 쓰기 없는 명령을 실행한다.
  const data = JSON.parse(result.stdout || result.stderr); // 성공·실패 출력 채널 모두 처리한다.
  assert.equal(result.status, expected, result.stderr || result.stdout); // 정상 종료와 의도된 실패를 구분한다.
  if (expected) { assert.equal(data.nodes, undefined); assert.equal(data.packs, undefined); } // 실패를 규칙 축소 결과로 사용할 수 없다.
  return data; // 개별 시나리오가 상세 진단을 확인한다.
}
// [역할] 특정 오류 코드를 확인한다. [의존성 관계] run. [변경 시 영향도] 진단 분류의 안정성.
function rejects(args, code) {
  const data = run(['context', ...args], 1); // 실패가 예상된 부정 입력이다.
  assert.ok(data.diagnostics.some(item => item.code === code), JSON.stringify(data)); // 미등록과 미매칭을 혼동하지 않는다.
  assert.equal(data.recovery.implementationBlocked, true); // 진단 가능성이 구현 권한으로 확대되지 않는다.
}

test('Staging-only migration loads DB invariants without a pretend production target', () => {
  const data = run(['context', '--intent', 'migration', '--path', 'Staging/Official_Model_Name_20260912/utils/database_contract.py']); // 최초 실패 입력의 핵심을 재현한다.
  for (const node of ['engineering.schema-evolution', 'engineering.data-integrity', 'operations.staging']) assert.ok(data.nodes.includes(node)); // 핵심 규칙 누락을 허용하지 않는다.
  assert.equal(data.inputs.paths.length, 1); // 운영 경로를 자동 추가하지 않는다.
});
test('utils-only migration and nested Staging UI select their required nodes', () => {
  const data = run(['context', '--intent', 'migration', '--intent', 'ui', '--path', 'utils/new_schema.py', '--path', 'Staging/work/templates/new.html']); // 경로를 AND 필터로 사용하지 않는다.
  assert.ok(data.nodes.includes('engineering.frontend-responsive')); // UI 안전 규칙도 보존한다.
  assert.ok(data.nodes.includes('engineering.data-model')); // DB 규칙도 보존한다.
});
test('reference roles remain distinct and do not imply production writes', () => {
  const data = run(['context', '--intent', 'migration', '--path', 'Staging/work/candidate.py', '--reference-path', 'app.py']); // 역할을 명시한다.
  assert.deepEqual(data.inputs.paths, ['Staging/work/candidate.py']); // 원본은 작업 대상에 들어가지 않는다.
  assert.deepEqual(data.inputs.referencePaths, ['app.py']); // 참고로만 보존한다.
  assert.equal(data.pathRoles[1].role, 'reference'); // 응답도 역할을 구분한다.
});
test('unknown intent is not reported as path mismatch', () => {
  rejects(['--intent', 'unknown-intent', '--path', 'app.py'], 'UNKNOWN_INTENT'); // 잘못된 분류만 분리한다.
});
test('registered Rule intent reports expected path conditions', () => {
  const data = run(['context', '--intent', 'edit-rule', '--path', 'templates/index.html', '--section', '9-1'], 1); // 등록됐으나 잘못된 대상이다.
  const issue = data.diagnostics.find(item => item.code === 'INTENT_PATH_MISMATCH'); // 등록 사실을 보존한다.
  assert.ok(issue.routes[0].expectedPaths.includes('Rule.md')); // 필요한 실제 조건을 출력한다.
});
for (const intent of ['implement', 'question', 'migration']) test(`generic ${intent} cannot accept an unknown path`, () => {
  rejects(['--intent', intent, '--path', 'unregistered/new.file'], 'UNMATCHED_PATH'); // 독립 경로 검사를 우회할 수 없다.
});
test('known target cannot hide an unknown reference', () => {
  rejects(['--intent', 'implement', '--path', 'app.py', '--reference-path', 'unknown.file'], 'UNMATCHED_PATH'); // 모든 참고 경로도 검증한다.
});
test('reference-only change cannot create an implicit target', () => {
  rejects(['--intent', 'migration', '--reference-path', 'app.py'], 'MISSING_TARGET_PATH'); // 읽기 전용 역할을 쓰기로 승격하지 않는다.
});
test('read-only reference needs no mutation target', () => {
  const data = run(['context', '--intent', 'question', '--reference-path', 'utils/database_contract.py']); // 질문은 참고만 가능하다.
  assert.deepEqual(data.inputs.paths, []); // 허위 작업 대상을 만들지 않는다.
});
test('same normalized path cannot claim conflicting roles', () => {
  rejects(['--intent', 'implement', '--path', 'app.py', '--reference-path', './app.py'], 'PATH_ROLE_CONFLICT'); // 표기 차이로 역할 충돌을 숨기지 않는다.
});
test('external reference requires scope; explicit scope does not grant write permission', () => {
  const foreign = path.resolve(root, '../outside-governed-workspace'); // 프로젝트 경계 밖의 참조를 구성한다.
  rejects(['--intent', 'question', '--reference-path', foreign], 'EXTERNAL_SCOPE_REQUIRED'); // scope 없이 허용하지 않는다.
  const data = run(['context', '--intent', 'question', '--intent', 'external-reference', '--reference-path', foreign]); // 명시한 읽기 scope만 적용한다.
  assert.equal(data.pathRoles[0].external, true); // 외부 소유권 경계를 명시한다.
  assert.equal(data.pathRoles[0].role, 'reference'); // 쓰기 대상으로 바뀌지 않는다.
});
test('traversal is normalized before classification', () => {
  rejects(['--intent', 'implement', '--path', 'Staging/../../outside.py'], 'EXTERNAL_SCOPE_REQUIRED'); // Staging 접두사로 경계를 우회하지 않는다.
});
test('Windows separators and absolute project paths retain correct roles', () => {
  const data = run(['context', '--intent', 'migration', '--path', 'Staging\\work\\candidate.py', '--reference-path', path.join(root, 'app.py')]); // 두 경로 표현을 함께 검증한다.
  assert.equal(data.pathRoles[0].normalized, 'Staging/work/candidate.py'); // 원본을 추측하지 않고 구분자만 정규화한다.
  assert.equal(data.pathRoles[1].normalized, 'app.py'); // 내부 절대 경로를 같은 대상으로 인식한다.
});
test('blank and wildcard paths fail as inputs', () => {
  rejects(['--intent', 'implement', '--path', ''], 'INVALID_PATH'); // 빈 경로를 루트로 해석하지 않는다.
  rejects(['--intent', 'implement', '--path', 'Staging/**'], 'INVALID_PATH'); // 실제 대상 대신 glob을 받지 않는다.
});
test('Rule section omission and unknown section stay blocked', () => {
  rejects(['--intent', 'edit-rule', '--path', 'Rule.md'], 'MISSING_SECTION'); // 필수 섹션을 유지한다.
  rejects(['--intent', 'edit-rule', '--path', 'Rule.md', '--section', '999-1'], 'UNKNOWN_SECTION'); // 추적성 없는 섹션을 거부한다.
});
test('stale Rule hash blocks context itself', () => {
  rejects(['--intent', 'question', '--expected-rule-sha', '0'.repeat(64)], 'POLICY_VALIDATION_FAILED'); // 사전 validate 누락도 context가 막는다.
});
test('small packs preserve all selected nodes', () => {
  const data = run(['context', '--intent', 'plan', '--intent', 'migration', '--intent', 'ui', '--path', 'Staging/work/app.py', '--small-model']); // 복합 작업을 작게 분할한다.
  assert.ok(data.packs.every(pack => !pack.overBudget && pack.estimatedTokens <= data.budget)); // 예산을 완화하지 않는다.
  assert.deepEqual(new Set(data.packs.flatMap(pack => pack.nodes)), new Set(data.nodes)); // 누락된 규칙이 없어야 한다.
});
test('catalog labels mandatory path conditions separately from hints', () => {
  const data = run(['catalog']); // 현재 정책의 입력 계약을 확인한다.
  const schema = data.routes.find(route => route.id === 'schema-change'); // DB route를 선택한다.
  assert.deepEqual(schema.paths, []); // 힌트를 필수 AND 조건으로 오해하지 않는다.
  assert.ok(schema.pathHints.includes('Staging/**')); // 실제 후보 예시를 제공한다.
  assert.ok(data.pathOptions['--reference-path']); // 참고 역할을 안내한다.
});
test('existing symlink ancestor is treated as external', t => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'context-scope-')); // 이 테스트가 소유한 전용 fixture다.
  t.after(() => fs.rmSync(temp, { recursive: true, force: true })); // fixture만 종료 후 정리한다.
  const project = path.join(temp, 'project'), foreign = path.join(temp, 'foreign'); // 경계 양쪽을 분리한다.
  fs.mkdirSync(project); fs.mkdirSync(foreign); // 운영 저장소를 수정하지 않는다.
  fs.symlinkSync(foreign, path.join(project, 'Staging'), process.platform === 'win32' ? 'junction' : 'dir'); // 외부로 향한 후보 폴더를 재현한다.
  const router = { routing_policy: { external_path_scope_intents: ['external-reference'], registered_project_paths: ['Staging/**'] } }; // 최소 정책 fixture다.
  const result = classifyPaths({ intents: ['implement'], paths: ['Staging/new.py'] }, router, project, () => true); // 아직 없는 파일의 조상도 검사한다.
  assert.ok(result.diagnostics.some(item => item.code === 'EXTERNAL_SCOPE_REQUIRED')); // 문자열 Staging만으로 통과하지 않는다.
});
