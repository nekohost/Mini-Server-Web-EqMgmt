#!/usr/bin/env node
// [역할] 감사 전 작업트리와 index를 기준으로 KO-only 변경을 검사한다.
// [의존성 관계] Git NUL-delimited 출력, 공유 주석 판독기, SHA-256 snapshot.
// [변경 시 영향도] 접근 제어 장벽이 아닌 작업 검증 도구다. HEAD/기존 수정/스테이징을 보존한다.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { maskKo } from './comment-format.mjs';

const args = process.argv.slice(2);
const option = name => args.find(value => value.startsWith(name + '='))?.slice(name.length + 1);
const root = path.resolve(option('--root') ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..'));
const command = args.find(value => !value.startsWith('--')) ?? 'check';
const snapshotPath = option('--snapshot') ? path.resolve(root, option('--snapshot')) : null;
const sourceExtensions = new Set(['.py', '.js', '.mjs', '.html']);
const defaultAllowed = new Set(['.agent-governance/comment-sync/state.json', 'docs/COMMENT_GLOSSARY.md']);
const extraAllowed = new Set(args.filter(value => value.startsWith('--allow-path=')).map(value => value.slice(13).replaceAll('\\', '/')));
const hash = bytes => bytes === null ? null : crypto.createHash('sha256').update(bytes).digest('hex');
function git(...argv) {
  return execFileSync('git', argv, { cwd: root, encoding: null, maxBuffer: 64 * 1024 * 1024, env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' }, stdio: ['ignore', 'pipe', 'pipe'] });
}
function safePath(file) {
  const absolute = path.resolve(root, file);
  const rel = path.relative(root, absolute);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel) || file.includes('\0')) throw new Error('GUARD: invalid path');
  let current = root;
  for (const component of rel.split(path.sep)) {
    current = path.join(current, component);
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) throw new Error('GUARD: symlink path not supported');
  }
  return absolute;
}
function bytes(file) {
  const absolute = safePath(file);
  if (!fs.existsSync(absolute)) return null;
  if (!fs.lstatSync(absolute).isFile()) throw new Error('GUARD: non-regular file');
  return fs.readFileSync(absolute);
}
function statusFiles() {
  // -z는 한글·개행·화살표를 포함한 이름도 보존한다. rename은 D/A로 분리한다.
  return git('status', '--porcelain=v1', '-z', '--no-renames', '--untracked-files=all').toString('utf8').split('\0').filter(Boolean).map(row => row.slice(3));
}
function indexEntries() {
  const entries = {};
  for (const row of git('ls-files', '--stage', '-z').toString('utf8').split('\0').filter(Boolean)) {
    const tab = row.indexOf('\t');
    const [mode, oid, stage] = row.slice(0, tab).split(' ');
    if (stage !== '0' || !['100644', '100755'].includes(mode)) throw new Error('GUARD: unmerged/non-regular index entry');
    entries[row.slice(tab + 1)] = { mode, oid };
  }
  return entries;
}
function blob(oid) { return oid ? git('cat-file', 'blob', oid) : null; }
function headBytes(file) {
  try { return git('show', 'HEAD:' + file); } catch { return null; }
}
function allowedDocument(file) {
  return defaultAllowed.has(file) || extraAllowed.has(file);
}
function validateAllowedPaths() {
  for (const file of extraAllowed) {
    safePath(file);
    if (!/^Reports\/.*\.md$/.test(file)) throw new Error('GUARD: --allow-path only accepts an explicit Reports/*.md audit report');
  }
}
function snapshot() {
  if (fs.existsSync(snapshotPath)) throw new Error('GUARD: snapshot already exists; use a new audit filename');
  const state = { schema_version: 2, created_at: new Date().toISOString(), root, head: git('rev-parse', 'HEAD').toString().trim(), index: indexEntries(), files: {} };
  for (const file of statusFiles()) {
    const content = bytes(file);
    state.files[file] = { sha256: hash(content), content_base64: content?.toString('base64') ?? null };
  }
  if (state.head !== git('rev-parse', 'HEAD').toString().trim()) throw new Error('GUARD: HEAD-CHANGED during snapshot');
  fs.mkdirSync(path.dirname(snapshotPath), { recursive: true });
  fs.writeFileSync(snapshotPath, JSON.stringify(state, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  console.log('Guard snapshot written: ' + path.relative(root, snapshotPath).replaceAll('\\', '/'));
  return 0;
}
function loadSnapshot() {
  const state = JSON.parse(fs.readFileSync(snapshotPath, 'utf8'));
  if (state.schema_version !== 2 || state.root !== root || !state.files || !state.index || typeof state.head !== 'string') throw new Error('GUARD: invalid snapshot schema/root');
  for (const [file, entry] of Object.entries(state.files)) {
    safePath(file);
    if (!entry || !(entry.content_base64 === null || typeof entry.content_base64 === 'string')
        || hash(entry.content_base64 === null ? null : Buffer.from(entry.content_base64, 'base64')) !== entry.sha256) throw new Error('GUARD: snapshot integrity mismatch');
  }
  for (const [file, entry] of Object.entries(state.index)) {
    safePath(file);
    if (!entry || !/^[a-f0-9]{40,64}$/.test(entry.oid) || !['100644', '100755'].includes(entry.mode)) throw new Error('GUARD: invalid index snapshot');
  }
  return state;
}
function check() {
  const state = loadSnapshot();
  const head = git('rev-parse', 'HEAD').toString().trim();
  if (head !== state.head) throw new Error('GUARD: HEAD-CHANGED ' + state.head + ' -> ' + head);
  const snapshotRel = path.relative(root, snapshotPath).replaceAll('\\', '/');
  const accepted = [], violations = [];
  const inspect = (file, before, after, surface) => {
    if (hash(before) === hash(after)) return;
    if (allowedDocument(file)) { accepted.push(file + ' (' + surface + ': allowed document)'); return; }
    const ext = path.extname(file).toLowerCase();
    if (!sourceExtensions.has(ext) || before === null || after === null) { violations.push(file + ': ' + surface + ' path/type/create/delete not allowed'); return; }
    try {
      const decode = content => new TextDecoder('utf-8', { fatal: true }).decode(content);
      if (maskKo(decode(before), ext) !== maskKo(decode(after), ext)) violations.push(file + ': ' + surface + ' execution code or EN/non-KO content changed');
      else accepted.push(file + ' (' + surface + ': KO-only)');
    } catch (error) { violations.push(file + ': ' + surface + ' ' + error.message); }
  };
  const currentIndex = indexEntries();
  for (const file of new Set([...Object.keys(state.index), ...Object.keys(currentIndex)])) {
    const before = state.index[file], after = currentIndex[file];
    if (before?.mode !== after?.mode) {
      if ((!before || !after) && allowedDocument(file)) inspect(file, blob(before?.oid), blob(after?.oid), 'INDEX');
      else violations.push(file + ': INDEX mode/create/delete changed');
      continue;
    }
    if (before?.oid !== after?.oid) inspect(file, blob(before?.oid), blob(after?.oid), 'INDEX');
  }
  for (const file of new Set([...Object.keys(state.files), ...statusFiles()])) {
    if (file === snapshotRel) continue;
    const old = state.files[file];
    const before = old ? (old.content_base64 === null ? null : Buffer.from(old.content_base64, 'base64')) : headBytes(file);
    inspect(file, before, bytes(file), 'WORKTREE');
  }
  if (head !== git('rev-parse', 'HEAD').toString().trim() || JSON.stringify(currentIndex) !== JSON.stringify(indexEntries())) violations.push('HEAD/INDEX changed during check; retry with a quiescent worktree');
  console.log('Guard accepted changes: ' + accepted.length);
  for (const item of accepted) console.log('ALLOW ' + item);
  if (!violations.length) { console.log('GEMINI-DIFF-GUARD: OK'); return 0; }
  console.log('GEMINI-DIFF-GUARD: ' + violations.length + ' violation(s)');
  for (const item of violations) console.log('BLOCK ' + item);
  return 1;
}
try {
  validateAllowedPaths();
  if (['help', '--help', '-h'].includes(command)) console.log('gemini-diff-guard.mjs snapshot|check --snapshot=PATH [--allow-path=Reports/...md] [--root=PATH]');
  else {
    if (!snapshotPath) throw new Error(command + ' requires --snapshot=PATH');
    const rel = path.relative(root, snapshotPath);
    if (!rel.startsWith('..') && !path.isAbsolute(rel)) safePath(rel);
    if (command === 'snapshot') process.exitCode = snapshot();
    else if (command === 'check') process.exitCode = check();
    else throw new Error('Unknown command: ' + command);
  }
} catch (error) { console.error(error.message); process.exitCode = 1; }
