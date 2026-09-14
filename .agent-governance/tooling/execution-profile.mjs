// [역할] 런타임에 연결된 모델로 독립 정책을 선택한다. legacy 노드를 로드하지 않는다.
// [의존성] Node 내장 모듈, 고정 yaml 파서, 등록부/manifest/선택 노드. 파일 쓰기·네트워크 없음.
// [영향] AGENTS의 매 턴 선택 및 전체 정책 validate. 모델 추가는 데이터로, 플랫폼 추가는 어댑터로 처리한다.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import readline from 'node:readline';
import { parseDocument } from 'yaml';

export class ProfileError extends Error {
  constructor(code, message) {
    super(message);
    this.diagnostics = [{ code, message }];
  }
}
const fail = (code, message) => { throw new ProfileError(code, message); };
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex').toUpperCase();
const isHash = value => typeof value === 'string' && /^[A-F0-9]{64}$/.test(value);
const isId = value => typeof value === 'string' && /^[a-z0-9][a-z0-9._-]{0,99}$/.test(value);
const inside = (root, target) => {
  const relative = path.relative(root, target);
  return relative !== '' && !path.isAbsolute(relative) && relative !== '..' && !relative.startsWith(`..${path.sep}`);
};
const samePath = (left, right) => {
  try {
    const a = fs.realpathSync(left), b = fs.realpathSync(right);
    return process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
  } catch { return false; }
};

// YAML 중복 키/순환 별칭을 거부하고, 경로를 메시지에만 포함한다. 파일 본문은 오류에 싣지 않는다.
function parseYaml(text, label) {
  const doc = parseDocument(text, { strict: true, uniqueKeys: true });
  if (doc.errors.length) fail('PROFILE_CONFIG_INVALID', `${label}: YAML 구문/중복 키 오류`);
  try { return doc.toJS({ maxAliasCount: 0 }); }
  catch { fail('PROFILE_CONFIG_INVALID', `${label}: YAML 별칭은 지원하지 않습니다.`); }
}

// 선언 경로와 realpath 양쪽을 검사하여 ../, 절대 경로 및 외부 junction을 막는다.
function readWithin(root, relative, prefix = '') {
  if (typeof relative !== 'string' || !relative.startsWith(prefix) || !/^[a-zA-Z0-9_./-]+$/.test(relative)
      || path.posix.isAbsolute(relative) || relative.split('/').some(part => !part || part === '.' || part === '..')) {
    fail('PROFILE_PATH_INVALID', `허용되지 않은 정책 경로: ${String(relative)}`);
  }
  const absolute = path.resolve(root, relative);
  try {
    if (!inside(fs.realpathSync(root), fs.realpathSync(absolute)) || !fs.statSync(absolute).isFile()) {
      fail('PROFILE_PATH_INVALID', `정책 디렉터리 밖 또는 일반 파일 아님: ${relative}`);
    }
    const bytes = fs.readFileSync(absolute);
    return { absolute, bytes, sha256: hash(bytes) };
  } catch (error) {
    if (error instanceof ProfileError) throw error;
    fail('PROFILE_FILE_UNAVAILABLE', `정책 파일을 읽을 수 없습니다: ${relative}`);
  }
}

// 최소 패키지 계약: manifest와 registry만 해석한다. 기존 router/map/노드 전수 로딩은 하지 않는다.
export function loadProfileRegistry(governanceRoot) {
  const manifestFile = readWithin(governanceRoot, 'manifest.yaml');
  const manifest = parseYaml(manifestFile.bytes.toString('utf8'), 'manifest.yaml');
  const binding = manifest?.execution_profiles;
  if (manifest?.status !== 'active' || binding?.registry !== 'execution-profiles.yaml' || !isHash(binding?.sha256)) {
    fail('PROFILE_PACKAGE_MISMATCH', 'manifest의 활성 실행 프로필 계약이 없거나 불완전합니다.');
  }
  const registryFile = readWithin(governanceRoot, binding.registry);
  if (binding.sha256 !== registryFile.sha256) fail('PROFILE_PACKAGE_MISMATCH', 'manifest/등록부 SHA-256 불일치');
  const registry = parseYaml(registryFile.bytes.toString('utf8'), binding.registry);
  if (registry?.schema_version !== 1 || typeof registry?.governance_version !== 'string' || !registry.governance_version.trim()
      || registry?.governance_version !== manifest.governance_version
      || registry?.fallback !== 'legacy' || !Array.isArray(registry?.profiles)) {
    fail('PROFILE_CONFIG_INVALID', '등록부 schema/version/fallback/profiles 오류');
  }
  const ids = new Set(), pairs = new Set();
  for (const entry of registry.profiles) {
    if (!isId(entry?.id) || !isId(entry?.platform) || !Array.isArray(entry?.models) || !entry.models.length
        || !entry.models.every(isId) || typeof entry.enabled !== 'boolean' || !Number.isInteger(entry.version) || entry.version < 1
        || entry.parent !== null || !isHash(entry.node_sha256) || !isHash(entry.capability_sha256)
        || typeof entry.adoption_basis !== 'string' || !entry.adoption_basis.trim()) {
      fail('PROFILE_CONFIG_INVALID', '프로필의 필수 필드/타입/독립 parent 계약 오류');
    }
    if (ids.has(entry.id)) fail('PROFILE_DUPLICATE', `중복 프로필 ID: ${entry.id}`);
    ids.add(entry.id);
    for (const model of entry.models) {
      const key = `${entry.platform}/${model}`;
      if (pairs.has(key)) fail('PROFILE_DUPLICATE', `중복 플랫폼/모델: ${key}`);
      pairs.add(key);
    }
    if (typeof entry.node !== 'string' || !entry.node.startsWith('profiles/') || !entry.node.endsWith('.md')
        || typeof entry.capability !== 'string' || !entry.capability.startsWith('capabilities/') || !entry.capability.endsWith('.yaml')
        || manifest.nodes?.[entry.id] !== entry.node || manifest.capabilities?.[entry.platform] !== entry.capability
        || (manifest.always_load || []).includes(entry.id)) {
      fail('PROFILE_PACKAGE_MISMATCH', `독립 노드/플랫폼의 manifest 연결 불일치: ${entry.id}`);
    }
    // 비선택 항목도 선언 경로 탈출은 즉시 거부한다. 파일 내용 검사는 선택 시/전체 validate에서 수행한다.
    for (const relative of [entry.node, entry.capability]) {
      if (!/^[a-zA-Z0-9_./-]+$/.test(relative) || relative.split('/').some(p => !p || p === '.' || p === '..')) {
        fail('PROFILE_PATH_INVALID', `허용되지 않은 정책 경로: ${relative}`);
      }
    }
  }
  return { governanceRoot, manifest, manifestHash: manifestFile.sha256, registry, registryHash: registryFile.sha256 };
}

// 순수 선택 함수는 fixture로 확장성을 검증할 수 있다. CLI는 사용자 --model을 신원으로 받지 않는다.
export function chooseProfile(registry, observed) {
  if (!observed?.verified) return { kind: 'legacy', reason: observed?.reason || 'runtime-unverified' };
  const entry = registry.profiles.find(p => p.platform === observed.platform && p.models.includes(observed.model));
  if (!entry) return { kind: 'legacy', reason: 'model-unregistered' };
  if (!entry.enabled) return { kind: 'legacy', reason: 'profile-disabled' };
  return { kind: 'dedicated', reason: 'verified-runtime-exact-match', entry };
}

function validateEntry(state, entry) {
  const file = readWithin(state.governanceRoot, entry.node, 'profiles/');
  if (file.sha256 !== entry.node_sha256) fail('PROFILE_PACKAGE_MISMATCH', `노드 SHA-256 불일치: ${entry.id}`);
  const text = file.bytes.toString('utf8');
  const front = text.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  if (!front) fail('PROFILE_CONFIG_INVALID', `노드 front matter 누락: ${entry.id}`);
  const meta = parseYaml(front[1], entry.node);
  if (meta?.id !== entry.id || meta.parent !== null || meta.version !== entry.version
      || meta.execution_profile !== true || meta.always_load !== false || meta.may_relax_parent !== false) {
    fail('PROFILE_CONFIG_INVALID', `독립 노드 메타데이터 오류: ${entry.id}`);
  }
  const capability = readWithin(state.governanceRoot, entry.capability, 'capabilities/');
  if (capability.sha256 !== entry.capability_sha256) fail('PROFILE_PACKAGE_MISMATCH', `capability SHA-256 불일치: ${entry.id}`);
  if (parseYaml(capability.bytes.toString('utf8'), entry.capability)?.platform !== entry.platform) {
    fail('PROFILE_CONFIG_INVALID', `capability 플랫폼 불일치: ${entry.id}`);
  }
  return { id: entry.id, path: entry.node, absolutePath: file.absolute, version: meta.version, sha256: file.sha256 };
}

// 해시만 읽으며 사용자용 Rule을 지침으로 주입하지 않는다. 혼합 패키지와 검사 도중 변경을 탐지한다.
function validatePackageBoundary(state) {
  const ruleFile = path.join(state.governanceRoot, '..', 'Rule.md');
  if (state.manifest.human_reference?.path !== '../Rule.md' || !fs.existsSync(ruleFile)
      || hash(fs.readFileSync(ruleFile)) !== state.manifest.human_reference?.sha256) {
    fail('PROFILE_PACKAGE_MISMATCH', 'manifest/Rule SHA-256 불일치');
  }
  // 선택기·진입점·추적성의 부분 교체도 바이트 해시로 확인한다. legacy 정책 본문은 해석하지 않는다.
  const required = ['AGENTS.md', '.agent-governance/tooling/execution-profile.mjs', '.agent-governance/tooling/governance-tool.mjs',
    '.agent-governance/traceability/human-rule-map.yaml', '.agent-governance/traceability/entrypoint-map.yaml',
    '.agent-governance/traceability/rule-section-baseline.yaml'];
  const projectRoot = path.resolve(state.governanceRoot, '..');
  const bindings = state.registry.package_files;
  if (!bindings || typeof bindings !== 'object' || Array.isArray(bindings)
      || required.some(file => !isHash(bindings[file]))) fail('PROFILE_PACKAGE_MISMATCH', '필수 패키지 경계 해시 누락');
  for (const [file, digest] of Object.entries(bindings)) {
    if (!isHash(digest) || readWithin(projectRoot, file).sha256 !== digest) fail('PROFILE_PACKAGE_MISMATCH', `패키지 파일 불일치: ${file}`);
  }
  if (readWithin(state.governanceRoot, 'manifest.yaml').sha256 !== state.manifestHash
      || readWithin(state.governanceRoot, 'execution-profiles.yaml').sha256 !== state.registryHash) {
    fail('PROFILE_PACKAGE_CHANGED', '선택 중 정책 버전이 변경되었습니다. 새로 선택해야 합니다.');
  }
}

export function validateProfilePackage(governanceRoot) {
  const state = loadProfileRegistry(governanceRoot);
  const nodes = state.registry.profiles.map(entry => validateEntry(state, entry));
  validatePackageBoundary(state);
  return { status: 'pass', profiles: nodes, governanceVersion: state.registry.governance_version };
}

// 현재 ID와 일치하는 파일명만 찾고 그 파일만 읽는다. 다른 작업의 대화 본문은 수집하지 않는다.
function findCurrentSession(sessionsRoot, threadId) {
  if (!fs.existsSync(sessionsRoot)) return [];
  const matches = [];
  function visit(directory, depth) {
    for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
      if (item.isSymbolicLink()) continue;
      const absolute = path.join(directory, item.name);
      if (item.isDirectory() && depth < 3 && /^\d{2,4}$/.test(item.name)) visit(absolute, depth + 1);
      else if (item.isFile() && item.name.startsWith('rollout-') && item.name.endsWith(`-${threadId}.jsonl`)) matches.push(absolute);
    }
  }
  visit(sessionsRoot, 0);
  return matches;
}

// 이벤트의 화이트리스트 필드만 유지한다. 이전 완료 턴/부모 모델/설정 기본값은 사용하지 않는다.
export function runtimeFromMetadata(records, { threadId, projectRoot }) {
  let session, activeTurn = null, context = null, malformed = false;
  for (const record of records) {
    if (record === null) { malformed = true; continue; }
    const p = record.payload || {};
    if (record.type === 'session_meta') session = p;
    if (record.type === 'event_msg' && p.type === 'task_started') { activeTurn = p.turn_id; context = null; }
    if (record.type === 'event_msg' && ['task_complete', 'turn_aborted'].includes(p.type)) { activeTurn = null; context = null; }
    if (record.type === 'turn_context' && activeTurn && p.turn_id === activeTurn) context = p;
  }
  const unknown = reason => ({ verified: false, platform: 'codex', model: null, threadId, turnId: activeTurn, reason });
  if (malformed) return unknown('runtime-record-malformed');
  if (session?.id !== threadId || !samePath(session?.cwd, projectRoot)) return unknown('runtime-session-mismatch');
  if (!activeTurn || !context) return unknown('runtime-active-turn-unavailable');
  if (!samePath(context.cwd, projectRoot) || !isId(context.model)) return unknown('runtime-context-mismatch');
  return { verified: true, platform: 'codex', model: context.model, threadId, turnId: activeTurn, reason: 'active-turn-context' };
}

export async function observeCodexRuntime(projectRoot, env = process.env) {
  const threadId = env.CODEX_THREAD_ID || env.CODEX_SESSION_ID;
  const unknown = reason => ({ verified: false, platform: 'codex', model: null, threadId: threadId || null, turnId: null, reason });
  if (!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(threadId || '')) return unknown('runtime-thread-id-unavailable');
  if (env.CODEX_THREAD_ID && env.CODEX_SESSION_ID && env.CODEX_THREAD_ID !== env.CODEX_SESSION_ID) return unknown('runtime-thread-id-conflict');
  try {
    const sessionsRoot = path.join(env.CODEX_HOME || path.join(os.homedir(), '.codex'), 'sessions');
    const matches = findCurrentSession(sessionsRoot, threadId);
    if (matches.length !== 1) return unknown(matches.length ? 'runtime-session-ambiguous' : 'runtime-session-unavailable');
    if (!inside(fs.realpathSync(sessionsRoot), fs.realpathSync(matches[0]))) return unknown('runtime-session-path-invalid');
    const metadata = [];
    const stream = readline.createInterface({ input: fs.createReadStream(matches[0]), crlfDelay: Infinity });
    for await (const line of stream) {
      // 대화 본문은 보관·출력하지 않고 필요한 메타데이터 필드만 유지한다.
      if (!line.trim()) continue;
      try {
        const record = JSON.parse(line);
        const p = record.payload || {};
        if (record.type === 'session_meta') metadata.push({ type: record.type, payload: { id: p.id, cwd: p.cwd } });
        if (record.type === 'turn_context') metadata.push({ type: record.type, payload: { turn_id: p.turn_id, cwd: p.cwd, model: p.model } });
        if (record.type === 'event_msg' && ['task_started', 'task_complete', 'turn_aborted'].includes(p.type)) {
          metadata.push({ type: record.type, payload: { type: p.type, turn_id: p.turn_id } });
        }
      } catch { metadata.push(null); }
    }
    return { ...runtimeFromMetadata(metadata, { threadId, projectRoot }), source: 'codex-current-session-active-turn' };
  } catch { return unknown('runtime-metadata-unreadable'); }
}

export async function selectRuntimeProfile(governanceRoot, projectRoot) {
  const state = loadProfileRegistry(governanceRoot);
  const observed = await observeCodexRuntime(projectRoot);
  const selection = chooseProfile(state.registry, observed);
  const result = { schemaVersion: 1, status: 'pass', governanceVersion: state.registry.governance_version,
    kind: selection.kind, reason: selection.reason, observed, profile: null, nodes: [], legacyLoaded: false };
  if (selection.entry) {
    const entry = selection.entry;
    result.profile = validateEntry(state, entry);
    result.capability = entry.capability;
    result.nodes = [entry.id];
  }
  validatePackageBoundary(state);
  result.next = result.kind === 'dedicated' ? 'read-profile-and-capability' : 'follow-AGENTS-legacy-bootstrap';
  return result;
}
