// [역할] 실제 프로필 로더의 선택·실패·확장·복구 경계를 격리 fixture로 검증한다.
// [의존성] Node test/fs, execution-profile. 운영 파일/사용자 세션/설정은 수정하지 않는다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { chooseProfile, loadProfileRegistry, observeCodexRuntime, runtimeFromMetadata, selectRuntimeProfile, validateProfilePackage } from './execution-profile.mjs';

const hash = value => crypto.createHash('sha256').update(value).digest('hex').toUpperCase();
const threadId = '00000000-0000-0000-0000-000000000001';
const cli = fileURLToPath(new URL('./governance-tool.mjs', import.meta.url));
const fields = ['AGENTS.md', '.agent-governance/tooling/execution-profile.mjs', '.agent-governance/tooling/governance-tool.mjs',
  '.agent-governance/traceability/human-rule-map.yaml', '.agent-governance/traceability/entrypoint-map.yaml', '.agent-governance/traceability/rule-section-baseline.yaml'];
const observed = model => ({ verified: true, platform: 'codex', model });

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eqmgmt-profile-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const governance = path.join(root, '.agent-governance');
  const put = (file, value) => { const absolute = path.join(root, file); fs.mkdirSync(path.dirname(absolute), { recursive: true }); fs.writeFileSync(absolute, value); };
  const get = file => fs.readFileSync(path.join(root, file));
  const entry = { id: 'profiles.gpt-6-astra', version: 1, parent: null, platform: 'codex', models: ['gpt-6-astra'], enabled: true,
    node: 'profiles/gpt-6-astra.md', capability: 'capabilities/codex.yaml', adoption_basis: 'isolated fixture' };
  const registry = { schema_version: 1, governance_version: 'test.1', fallback: 'legacy', profiles: [entry], package_files: {} };
  const manifest = { status: 'active', governance_version: 'test.1', nodes: {}, capabilities: {}, always_load: [],
    human_reference: { path: '../Rule.md' }, execution_profiles: { registry: 'execution-profiles.yaml' } };
  put('Rule.md', 'fixture policy');
  for (const file of fields) put(file, 'fixture binding');
  function node(item) {
    put(`.agent-governance/${item.node}`, `---\nid: ${item.id}\nversion: ${item.version}\nparent: null\nexecution_profile: true\nalways_load: false\nmay_relax_parent: false\n---\n# Independent fixture\n`);
    put(`.agent-governance/${item.capability}`, `platform: ${item.platform}\n`);
  }
  node(entry);
  function seal() {
    for (const item of registry.profiles) {
      manifest.nodes[item.id] = item.node;
      manifest.capabilities[item.platform] = item.capability;
      // 테스트가 경로를 변조한 경우 기존 digest를 남겨 로더의 경로 검사를 시험한다.
      for (const [field, digest] of [['node', 'node_sha256'], ['capability', 'capability_sha256']]) {
        const p = path.join(governance, item[field]);
        if (fs.existsSync(p) && fs.statSync(p).isFile()) item[digest] = hash(fs.readFileSync(p));
      }
    }
    registry.package_files = Object.fromEntries(fields.map(file => [file, hash(get(file))]));
    put('.agent-governance/execution-profiles.yaml', JSON.stringify(registry));
    manifest.human_reference.sha256 = hash(get('Rule.md'));
    manifest.execution_profiles.sha256 = hash(get('.agent-governance/execution-profiles.yaml'));
    put('.agent-governance/manifest.yaml', JSON.stringify(manifest));
  }
  function runtime(model = 'gpt-6-astra', events) {
    const codexHome = path.join(root, 'runtime');
    const relative = `runtime/sessions/2026/09/14/rollout-fixture-${threadId}.jsonl`;
    put(relative, (events || metadata(root, model)).map(r => JSON.stringify(r)).join('\n') + '\n');
    return { CODEX_HOME: codexHome, CODEX_THREAD_ID: threadId, CODEX_SESSION_ID: threadId };
  }
  seal();
  return { root, governance, put, get, entry, registry, manifest, node, seal, runtime };
}

function metadata(root, model = 'gpt-6-astra', turn = 'turn-one') {
  return [
    { type: 'session_meta', payload: { id: threadId, cwd: root } },
    { type: 'event_msg', payload: { type: 'task_started', turn_id: turn } },
    { type: 'turn_context', payload: { cwd: root, model, turn_id: turn } },
    { type: 'response_item', payload: { content: 'FIXTURE-SECRET-DO-NOT-OUTPUT' } },
  ];
}
async function inRuntime(env, action) {
  const before = Object.fromEntries(Object.keys(env).map(k => [k, process.env[k]]));
  try { Object.assign(process.env, env); return await action(); }
  finally { for (const [k, v] of Object.entries(before)) { if (v === undefined) delete process.env[k]; else process.env[k] = v; } }
}
function rejected(f, code) { assert.throws(f, error => error.diagnostics?.some(d => d.code === code)); }

test('Astra exact runtime selects one independent node without ANY legacy router/nodes present', async t => {
  const f = fixture(t);
  const result = await inRuntime(f.runtime(), () => selectRuntimeProfile(f.governance, f.root));
  assert.equal(result.kind, 'dedicated');
  assert.deepEqual(result.nodes, ['profiles.gpt-6-astra']);
  assert.equal(result.legacyLoaded, false);
  assert.equal(result.observed.turnId, 'turn-one');
  assert.ok(!JSON.stringify(result).includes('FIXTURE-SECRET'));
});

test('other Codex model remains legacy, including same-model-looking prefixes and suffixes', t => {
  const f = fixture(t);
  for (const model of ['gpt-5.5', 'gpt-6-astra-preview', 'gpt-6-astra-2', 'GPT-6-Astra']) {
    assert.equal(chooseProfile(f.registry, observed(model)).kind, 'legacy');
  }
  assert.equal(chooseProfile(f.registry, { ...observed('gpt-6-astra'), platform: 'synthetic-other' }).kind, 'legacy');
});

test('unknown evidence and explicit disable fall back with different reasons', t => {
  const f = fixture(t);
  assert.equal(chooseProfile(f.registry, { verified: false, reason: 'missing-current-turn' }).reason, 'missing-current-turn');
  f.entry.enabled = false; f.seal();
  assert.equal(chooseProfile(loadProfileRegistry(f.governance).registry, observed('gpt-6-astra')).reason, 'profile-disabled');
});

test('synthetic platform/model extends by data only, then independently disables', t => {
  const f = fixture(t);
  const added = { ...f.entry, id: 'profiles.synthetic', platform: 'synthetic-platform', models: ['synthetic-model'],
    node: 'profiles/synthetic.md', capability: 'capabilities/synthetic.yaml' };
  f.registry.profiles.push(added); f.node(added); f.seal();
  assert.equal(validateProfilePackage(f.governance).profiles.length, 2);
  assert.equal(chooseProfile(f.registry, { verified: true, platform: added.platform, model: added.models[0] }).entry.id, added.id);
  added.enabled = false; f.seal();
  assert.equal(chooseProfile(f.registry, { verified: true, platform: added.platform, model: added.models[0] }).kind, 'legacy');
  assert.equal(chooseProfile(f.registry, observed('gpt-6-astra')).kind, 'dedicated');
});

test('synthetic model on supported platform needs no model-specific loader branch', t => {
  const f = fixture(t);
  const added = { ...f.entry, id: 'profiles.synthetic', models: ['synthetic-model'], node: 'profiles/synthetic.md' };
  f.registry.profiles.push(added); f.node(added); f.seal();
  assert.equal(validateProfilePackage(f.governance).profiles.length, 2);
  assert.equal(chooseProfile(f.registry, observed('synthetic-model')).entry.id, 'profiles.synthetic');
});

for (const mode of ['missing', 'corrupt']) test(`selected node ${mode} is an error, not silent fallback`, async t => {
  const f = fixture(t);
  if (mode === 'missing') fs.unlinkSync(path.join(f.governance, f.entry.node));
  else f.put(`.agent-governance/${f.entry.node}`, 'corrupt');
  await inRuntime(f.runtime(), () => assert.rejects(selectRuntimeProfile(f.governance, f.root), /정책 파일|SHA-256/));
});

for (const mutation of ['duplicate-id', 'duplicate-pair', 'duplicate-model', 'parent', 'disabled-duplicate']) test(`registry rejects ${mutation}`, t => {
  const f = fixture(t);
  if (mutation === 'parent') f.entry.parent = 'core.kernel';
  else if (mutation === 'duplicate-model') f.entry.models.push('gpt-6-astra');
  else f.registry.profiles.push({ ...f.entry, id: mutation === 'duplicate-id' ? f.entry.id : 'profiles.other', enabled: mutation !== 'disabled-duplicate' });
  f.seal(); rejected(() => loadProfileRegistry(f.governance), mutation === 'parent' ? 'PROFILE_CONFIG_INVALID' : 'PROFILE_DUPLICATE');
});

for (const target of ['profiles/../../outside.md', '/absolute.md', 'profiles/../gpt-6-astra.md', 'profiles/escape\\node.md']) test(`path escape rejected: ${target}`, t => {
  const f = fixture(t); f.entry.node = target; f.seal();
  assert.throws(() => loadProfileRegistry(f.governance));
});

test('junction/symlink cannot make selected node leave governance root', t => {
  const f = fixture(t);
  const external = path.join(f.root, 'outside'); fs.mkdirSync(external);
  fs.writeFileSync(path.join(external, 'node.md'), 'outside');
  fs.symlinkSync(external, path.join(f.governance, 'profiles', 'linked'), process.platform === 'win32' ? 'junction' : 'dir');
  f.entry.node = 'profiles/linked/node.md'; f.seal();
  rejected(() => validateProfilePackage(f.governance), 'PROFILE_PATH_INVALID');
});

test('node parent cycle and duplicate YAML keys are rejected even with updated hash', t => {
  const f = fixture(t);
  f.put(`.agent-governance/${f.entry.node}`, f.get(`.agent-governance/${f.entry.node}`).toString().replace('parent: null', `parent: ${f.entry.id}`));
  f.seal(); rejected(() => validateProfilePackage(f.governance), 'PROFILE_CONFIG_INVALID');
  f.put('.agent-governance/execution-profiles.yaml', 'schema_version: 1\nschema_version: 1\n');
  f.manifest.execution_profiles.sha256 = hash(f.get('.agent-governance/execution-profiles.yaml'));
  f.put('.agent-governance/manifest.yaml', JSON.stringify(f.manifest));
  rejected(() => loadProfileRegistry(f.governance), 'PROFILE_CONFIG_INVALID');
});

for (const changed of ['Rule.md', 'AGENTS.md', '.agent-governance/traceability/human-rule-map.yaml', '.agent-governance/tooling/execution-profile.mjs', '.agent-governance/execution-profiles.yaml', '.agent-governance/capabilities/codex.yaml']) test(`partial package detected and original restored: ${changed}`, t => {
  const f = fixture(t); const original = f.get(changed);
  f.put(changed, 'partial replacement');
  assert.throws(() => validateProfilePackage(f.governance));
  f.put(changed, original);
  assert.equal(validateProfilePackage(f.governance).status, 'pass');
});

test('policy version change is not retained from an earlier selection', t => {
  const f = fixture(t);
  assert.equal(validateProfilePackage(f.governance).governanceVersion, 'test.1');
  f.registry.governance_version = 'test.2'; f.manifest.governance_version = 'test.2'; f.seal();
  assert.equal(validateProfilePackage(f.governance).governanceVersion, 'test.2');
});

test('manifest/registry version mismatch and missing package binding fail closed', t => {
  const f = fixture(t);
  f.registry.governance_version = 'test.2'; f.seal();
  rejected(() => loadProfileRegistry(f.governance), 'PROFILE_CONFIG_INVALID');
  f.manifest.governance_version = 'test.2'; f.seal();
  delete f.registry.package_files['AGENTS.md'];
  f.put('.agent-governance/execution-profiles.yaml', JSON.stringify(f.registry));
  f.manifest.execution_profiles.sha256 = hash(f.get('.agent-governance/execution-profiles.yaml'));
  f.put('.agent-governance/manifest.yaml', JSON.stringify(f.manifest));
  rejected(() => validateProfilePackage(f.governance), 'PROFILE_PACKAGE_MISMATCH');
});

test('invalid runtime record cannot leave a previously selected model trusted', async t => {
  const f = fixture(t); const env = f.runtime();
  const file = `runtime/sessions/2026/09/14/rollout-fixture-${threadId}.jsonl`;
  f.put(file, f.get(file).toString() + 'incomplete-or-corrupt\n');
  assert.equal((await observeCodexRuntime(f.root, env)).reason, 'runtime-record-malformed');
});

test('runtime reads only exact current file and ignores other-session dialogue', async t => {
  const f = fixture(t); const env = f.runtime();
  f.put('runtime/sessions/2026/09/14/rollout-other.jsonl', 'invalid unrelated private dialogue');
  const actual = await observeCodexRuntime(f.root, env);
  assert.equal(actual.verified, true); assert.equal(actual.model, 'gpt-6-astra');
  assert.ok(!JSON.stringify(actual).includes('FIXTURE-SECRET'));
});

test('completed or aborted previous turn and default model env are not evidence', async t => {
  const f = fixture(t);
  for (const event of ['task_complete', 'turn_aborted']) {
    const records = metadata(f.root); records.push({ type: 'event_msg', payload: { type: event, turn_id: 'turn-one' } });
    const env = f.runtime('gpt-6-astra', records);
    assert.equal((await observeCodexRuntime(f.root, { ...env, CODEX_MODEL: 'gpt-6-astra' })).verified, false);
  }
  assert.equal((await observeCodexRuntime(f.root, { CODEX_MODEL: 'gpt-6-astra' })).verified, false);
});

test('new turn/model/subworker never inherits earlier Astra context', t => {
  const f = fixture(t); const records = metadata(f.root);
  records.push({ type: 'event_msg', payload: { type: 'task_started', turn_id: 'turn-two' } });
  assert.equal(runtimeFromMetadata(records, { threadId, projectRoot: f.root }).verified, false);
  records.push({ type: 'turn_context', payload: { cwd: f.root, model: 'synthetic-worker', turn_id: 'turn-two' } });
  const second = runtimeFromMetadata(records, { threadId, projectRoot: f.root });
  assert.equal(second.model, 'synthetic-worker'); assert.equal(chooseProfile(f.registry, second).kind, 'legacy');
  assert.equal(runtimeFromMetadata(records, { threadId: 'different-worker', projectRoot: f.root }).verified, false);
});

test('cwd mismatch, conflicting IDs, missing and ambiguous files fail safely', async t => {
  const f = fixture(t); const env = f.runtime();
  assert.equal((await observeCodexRuntime(os.tmpdir(), env)).verified, false);
  assert.equal((await observeCodexRuntime(f.root, { ...env, CODEX_SESSION_ID: 'other' })).reason, 'runtime-thread-id-conflict');
  assert.equal((await observeCodexRuntime(f.root, { ...env, CODEX_THREAD_ID: '../escape', CODEX_SESSION_ID: '../escape' })).verified, false);
  f.put(`runtime/sessions/2026/09/14/rollout-duplicate-${threadId}.jsonl`, '');
  assert.equal((await observeCodexRuntime(f.root, env)).reason, 'runtime-session-ambiguous');
});

test('CLI refuses self-declared model instead of activating a profile', () => {
  const result = spawnSync(process.execPath, [cli, 'profile', '--model', 'gpt-6-astra'], { encoding: 'utf8' });
  assert.equal(result.status, 1); assert.equal(JSON.parse(result.stderr).status, 'fail');
});

test('real registry keeps exactly one adopted model and no future placeholder', () => {
  const state = loadProfileRegistry(path.resolve(path.dirname(cli), '..'));
  assert.deepEqual(state.registry.profiles.map(p => ({ platform: p.platform, models: p.models })), [{ platform: 'codex', models: ['gpt-6-astra'] }]);
});
