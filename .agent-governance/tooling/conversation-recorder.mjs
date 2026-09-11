#!/usr/bin/env node
// [역할] 플랫폼 원본 대화를 Chat Markdown에 정확히 한 번 투영하고 watcher 상태를 관리하는 CLI다.
// [의존성 관계] conversation-recorder 하위 core와 Codex·Antigravity·Claude 어댑터만 사용한다.
// [변경 시 영향도] 명령 의미나 상태 경로를 바꾸면 세 진입점, 운영 가이드, fixture와 capability를 함께 갱신해야 한다.

import { readFileSync, watch as watchFileSystem } from 'node:fs';
import { mkdir, readFile, readdir, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { collectAntigravityEvents, defaultAntigravityRoots } from './conversation-recorder/antigravity.mjs';
import { collectClaudeEvents } from './conversation-recorder/claude.mjs';
import { collectCodexEvents } from './conversation-recorder/codex.mjs';
import { CURRENT_PROCESS_STARTED_AT, emptyState, eventAlreadyRecorded, isRecordedProcessAlive, normalizeNewlines, projectEvents, readState, withWriterLock, writeFileAtomic, writeState } from './conversation-recorder/core.mjs';
import { ingestRoutedEnvelope } from './conversation-recorder/routed-ingest.mjs';

const CLI_PATH = fileURLToPath(import.meta.url);
const DEFAULT_POLL_INTERVAL_MS = 1500;
const STATE_HEARTBEAT_INTERVAL_MS = 60_000;
const ACTIVE_PLATFORMS = ['codex', 'antigravity'];

// 폴링 시각만 달라진 상태는 논리적으로 같은 상태로 취급한다.
function persistentStateView(state) {
  const copy = structuredClone(state);
  delete copy.updatedAt;
  for (const health of Object.values(copy.health ?? {})) {
    if (health && typeof health === 'object') {
      delete health.checkedAt;
      delete health.lastReconcileAt;
    }
  }
  return copy;
}

// 논리 상태가 바뀌거나 heartbeat 기한이 지난 경우에만 디스크 저장을 허용한다.
export function shouldPersistState(previousState, nextState, nowMs = Date.now(), heartbeatMs = STATE_HEARTBEAT_INTERVAL_MS) {
  if (JSON.stringify(persistentStateView(previousState)) !== JSON.stringify(persistentStateView(nextState))) return true;
  const lastWriteMs = Date.parse(previousState.updatedAt ?? '');
  return !Number.isFinite(lastWriteMs) || nowMs - lastWriteMs >= heartbeatMs;
}

// 단순하고 예측 가능한 --key value CLI 인자를 해석한다.
export function parseArguments(argv) {
  // 첫 위치 인자는 명령이며 생략 시 status로 둔다.
  const options = { command: argv[0] && !argv[0].startsWith('--') ? argv[0] : 'status', platforms: [...ACTIVE_PLATFORMS], json: false, dryRun: false, force: false, intervalMs: DEFAULT_POLL_INTERVAL_MS };
  const start = options.command === argv[0] ? 1 : 0;
  for (let index = start; index < argv.length; index += 1) {
    const token = argv[index];
    // 값 없는 boolean 옵션은 즉시 반영한다.
    if (token === '--json') options.json = true;
    else if (token === '--dry-run') options.dryRun = true;
    else if (token === '--force') options.force = true;
    else {
      // 나머지 옵션은 다음 값을 반드시 요구한다.
      const value = argv[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`${token} 옵션 값이 없습니다.`);
      index += 1;
      if (token === '--workspace') options.workspaceRoot = path.resolve(value);
      else if (token === '--chat-root') options.chatRoot = path.resolve(value);
      else if (token === '--home') options.homeDirectory = path.resolve(value);
      else if (token === '--platform') options.platforms = value === 'all' ? [...ACTIVE_PLATFORMS] : value.split(',').map((item) => item.trim()).filter(Boolean);
      else if (token === '--interval-ms') options.intervalMs = Number(value);
      else throw new Error(`알 수 없는 옵션: ${token}`);
    }
  }
  // 환경에 따라 달라지는 경로는 실행 시점에 확정한다.
  options.workspaceRoot ??= process.cwd();
  options.chatRoot ??= path.join(options.workspaceRoot, 'Chat');
  options.homeDirectory ??= os.homedir();
  // Windows 권고 범위를 벗어난 폴링 설정은 조용히 허용하지 않는다.
  if (!Number.isInteger(options.intervalMs) || options.intervalMs < 1000 || options.intervalMs > 2000) throw new Error('--interval-ms는 1000~2000 사이 정수여야 합니다.');
  // 지원하지 않는 이름으로 다른 원본을 잘못 읽지 않는다.
  const allowed = new Set(['codex', 'antigravity', 'claude']);
  for (const platform of options.platforms) if (!allowed.has(platform)) throw new Error(`지원하지 않는 플랫폼: ${platform}`);
  return options;
}

// 상태와 잠금 파일의 고정 경로를 한 곳에서 계산한다.
function recorderPaths(options) {
  const stateRoot = path.join(options.chatRoot, '.state');
  return { stateRoot, statePath: path.join(stateRoot, 'conversation-recorder.json'), writerLockPath: path.join(stateRoot, 'recorder.lock'), startLockPath: path.join(stateRoot, 'watcher-start.lock'), pidPath: path.join(stateRoot, 'recorder.pid.json'), errorLogPath: path.join(stateRoot, 'recorder-errors.log') };
}

// 선택한 플랫폼 어댑터를 같은 state 기준으로 실행한다.
async function collectPlatforms(options, state, force = options.force) {
  const calls = options.platforms.map(async (platform) => {
    if (platform === 'codex') return collectCodexEvents({ workspaceRoot: options.workspaceRoot, state, homeDirectory: options.homeDirectory, force });
    if (platform === 'antigravity') return collectAntigravityEvents({ workspaceRoot: options.workspaceRoot, state, homeDirectory: options.homeDirectory, roots: defaultAntigravityRoots(options.homeDirectory), force });
    return collectClaudeEvents();
  });
  return Promise.all(calls);
}

// 원문 내용을 포함하지 않는 짧은 장애 로그를 append 대신 원자적 교체로 유지한다.
async function recordFailure(paths, message) {
  let previous = '';
  try {
    previous = await readFile(paths.errorLogPath, 'utf8');
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  // 로그가 무한히 커지지 않도록 최근 200줄만 남긴다.
  const line = `${new Date().toISOString()} ${String(message).replaceAll(/\r?\n/g, ' ')}\n`;
  const bounded = `${previous}${line}`.split('\n').slice(-201).join('\n');
  await writeFileAtomic(paths.errorLogPath, bounded);
}

// writer 잠금 안에서 수집·투영·receipt/cursor 저장을 하나의 순서로 수행한다.
export async function reconcileOnce(options) {
  const paths = recorderPaths(options);
  await mkdir(paths.stateRoot, { recursive: true });
  return withWriterLock(paths.writerLockPath, async () => {
    const state = await readState(paths.statePath);
    const previousState = structuredClone(state);
    const results = await collectPlatforms(options, state, options.force);
    const failed = results.filter((result) => result.status === 'error' || (result.status === 'unsupported' && options.platforms.length === 1));
    // 실패한 플랫폼은 snapshot과 cursor를 전진시키지 않고 원인만 health에 남긴다.
    for (const result of results) state.health[result.platform] = { status: result.status, errors: result.errors, checkedAt: new Date().toISOString() };
    if (failed.length > 0) {
      if (!options.dryRun) {
        if (shouldPersistState(previousState, state)) await writeState(paths.statePath, state);
        await recordFailure(paths, failed.flatMap((result) => result.errors).join(' | '));
      }
      throw new Error(failed.map((result) => `${result.platform}: ${result.errors.join(' | ')}`).join('; '));
    }
    // 성공 플랫폼의 이벤트만 하나의 결정적 배열로 합친다.
    const successful = results.filter((result) => result.status === 'ok');
    const events = successful.flatMap((result) => result.events);
    const projection = await projectEvents({ workspaceRoot: options.workspaceRoot, chatRoot: options.chatRoot, state, events, dryRun: options.dryRun, trustReceipts: !options.force });
    if (!options.dryRun) {
      // Chat 반영이 완료된 뒤에만 source fingerprint와 conversation registry를 전진시킨다.
      for (const result of successful) Object.assign(state.sources, result.snapshots);
      for (const result of successful) {
        if (result.platform === 'antigravity' && result.registeredConversations) state.registeredConversations.antigravity = result.registeredConversations;
      }
      state.health.recorder = { status: 'ok', lastReconcileAt: new Date().toISOString(), platforms: options.platforms };
      const statePersisted = shouldPersistState(previousState, state);
      if (statePersisted) await writeState(paths.statePath, state);
      return { command: 'reconcile', workspace: options.workspaceRoot, dryRun: options.dryRun, statePersisted, platforms: results.map((result) => ({ platform: result.platform, status: result.status, events: result.events.length, errors: result.errors })), projection };
    }
    return { command: 'reconcile', workspace: options.workspaceRoot, dryRun: options.dryRun, platforms: results.map((result) => ({ platform: result.platform, status: result.status, events: result.events.length, errors: result.errors })), projection };
  }, { waitMs: 5000 });
}

// Chat 트리의 모든 provenance 표식을 세어 중복을 검출한다.
async function countProvenanceFiles(root, counts = new Map()) {
  let entries;
  try {
    entries = await readdir(root, { withFileTypes: true });
  } catch (error) {
    if (error.code === 'ENOENT') return counts;
    throw error;
  }
  for (const entry of entries) {
    if (entry.name === '.state') continue;
    const candidate = path.join(root, entry.name);
    if (entry.isDirectory()) await countProvenanceFiles(candidate, counts);
    else if (entry.isFile() && entry.name.endsWith('.md')) {
      const text = await readFile(candidate, 'utf8');
      for (const match of text.matchAll(/<!-- conversation-event: ([A-F0-9]{64}) -->/g)) counts.set(match[1], (counts.get(match[1]) ?? 0) + 1);
    }
  }
  return counts;
}

// 원본 전체와 receipt·Chat provenance를 대조한다.
export async function verifyRecording(options) {
  const paths = recorderPaths(options);
  const state = await readState(paths.statePath);
  const results = await collectPlatforms(options, state, true);
  const failures = results.filter((result) => result.status === 'error');
  if (failures.length) throw new Error(failures.map((result) => `${result.platform}: ${result.errors.join(' | ')}`).join('; '));
  const events = results.filter((result) => result.status === 'ok').flatMap((result) => result.events);
  const missing = [];
  for (const event of events) {
    if (event.destination === 'main') {
      const target = path.join(options.chatRoot, event.time.year, event.time.month, `${event.time.day}.md`);
      let markdown = '';
      try { markdown = await readFile(target, 'utf8'); } catch (error) { if (error.code !== 'ENOENT') throw error; }
      if (!eventAlreadyRecorded(normalizeNewlines(markdown), event).matched) missing.push({ eventId: event.eventId, file: path.relative(options.chatRoot, target) });
    } else {
      // companion receipt가 가리키는 순번 파일 전체에서 provenance를 찾는다.
      const receipt = state.receipts[event.eventId];
      let found = false;
      if (receipt?.file) {
        const count = Number(receipt.parts ?? 1);
        for (let index = 1; index <= count; index += 1) {
          const relative = count === 1 ? receipt.file : receipt.file.replace(/part-001\.md$/, `part-${String(index).padStart(3, '0')}.md`);
          try {
            if ((await readFile(path.join(options.chatRoot, relative), 'utf8')).includes(`<!-- conversation-event: ${event.eventId} -->`)) found = true;
          } catch (error) {
            if (error.code !== 'ENOENT') throw error;
          }
        }
      }
      if (!found) missing.push({ eventId: event.eventId, file: receipt?.file ?? null });
    }
  }
  // 가상 하위 작업 receipt까지 dry-run projection으로 확인한다.
  const projected = await projectEvents({ workspaceRoot: options.workspaceRoot, chatRoot: options.chatRoot, state: structuredClone(state), events, dryRun: true, trustReceipts: false });
  const counts = await countProvenanceFiles(options.chatRoot);
  const duplicates = [...counts].filter(([, count]) => count > 1).map(([eventId, count]) => ({ eventId, count }));
  return { command: 'verify', ok: missing.length === 0 && projected.planned.length === 0 && duplicates.length === 0, sourceEvents: events.length, missing, missingReceipts: projected.planned, duplicates, platforms: results.map((result) => ({ platform: result.platform, status: result.status, errors: result.errors })) };
}

// watcher PID와 마지막 health를 기계 판독 가능한 형태로 반환한다.
export async function recorderStatus(options) {
  const paths = recorderPaths(options);
  const state = await readState(paths.statePath);
  let pidInfo = null;
  try { pidInfo = JSON.parse(await readFile(paths.pidPath, 'utf8')); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  const alive = Boolean(pidInfo?.pid && isRecordedProcessAlive(pidInfo));
  return { command: 'status', workspace: options.workspaceRoot, watcher: { running: alive, pid: alive ? Number(pidInfo.pid) : null, startedAt: alive ? pidInfo.startedAt : null, intervalMs: alive ? pidInfo.intervalMs : null }, state: { updatedAt: state.updatedAt, health: state.health, receipts: Object.keys(state.receipts).length, trackedSources: Object.keys(state.sources).length, registeredConversations: state.registeredConversations } };
}

// 이미 실행 중인 watcher를 재사용하거나 숨김 백그라운드 watcher 하나를 시작한다.
export async function ensureWatcher(options) {
  // 먼저 즉시 재조정하여 이전 watcher 중단 구간을 복구한다.
  const reconcile = await reconcileOnce({ ...options, dryRun: false });
  const paths = recorderPaths(options);
  const watcher = await withWriterLock(paths.startLockPath, async () => {
    let current = null;
    try { current = JSON.parse(await readFile(paths.pidPath, 'utf8')); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (current?.pid && isRecordedProcessAlive(current)) return { started: false, pid: Number(current.pid) };
    // 현재 node 실행 파일과 고정된 절대 경로를 사용해 shell 해석을 거치지 않는다.
    const args = [CLI_PATH, 'watch', '--workspace', options.workspaceRoot, '--chat-root', options.chatRoot, '--home', options.homeDirectory, '--platform', options.platforms.join(','), '--interval-ms', String(options.intervalMs), '--json'];
    const child = spawn(process.execPath, args, { detached: true, stdio: 'ignore', windowsHide: true });
    child.unref();
    await writeFileAtomic(paths.pidPath, `${JSON.stringify({ pid: child.pid, startedAt: new Date().toISOString(), intervalMs: options.intervalMs, platforms: options.platforms }, null, 2)}\n`);
    return { started: true, pid: child.pid };
  });
  return { command: 'ensure', reconcile, watcher };
}

// 파일 이벤트는 빠른 깨우기 신호로만 쓰고 매 1.5초 stat reconcile을 정확성 기준으로 유지한다.
export async function runWatcher(options) {
  const paths = recorderPaths(options);
  await mkdir(paths.stateRoot, { recursive: true });
  let current = null;
  try { current = JSON.parse(await readFile(paths.pidPath, 'utf8')); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (current?.pid && Number(current.pid) !== process.pid && isRecordedProcessAlive(current)) return { command: 'watch', running: false, reason: `watcher가 이미 실행 중입니다. PID=${current.pid}` };
  await writeFileAtomic(paths.pidPath, `${JSON.stringify({ pid: process.pid, processStartedAt: CURRENT_PROCESS_STARTED_AT, startedAt: new Date().toISOString(), intervalMs: options.intervalMs, platforms: options.platforms }, null, 2)}\n`);
  let wakeRequested = true;
  let wakeResolver = null;
  let stopping = false;
  const watchers = [];
  const roots = [path.join(options.homeDirectory, '.codex', 'sessions'), ...defaultAntigravityRoots(options.homeDirectory)];
  for (const root of roots) {
    try {
      // recursive watch 지원 여부와 상관없이 폴링은 항상 계속된다.
      const notify = () => {
        // 대기 중이면 타이머를 즉시 깨우고, reconcile 중이면 다음 반복을 예약한다.
        if (wakeResolver) wakeResolver();
        else wakeRequested = true;
      };
      const watcher = watchFileSystem(root, { recursive: process.platform === 'win32' }, notify);
      watcher.on('error', notify);
      watchers.push(watcher);
    } catch {
      // 존재하지 않거나 감시를 지원하지 않는 경로는 stat 폴링이 보완한다.
    }
  }
  const stop = () => { stopping = true; };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
  try {
    while (!stopping) {
      // 알림이 없어도 매 주기 수집하여 fs.watch 누락을 복구한다.
      wakeRequested = false;
      try { await reconcileOnce({ ...options, dryRun: false }); } catch (error) { await recordFailure(paths, error.message); }
      await new Promise((resolve) => {
        // reconcile 중 알림이 왔으면 대기 없이 다시 검사한다.
        if (wakeRequested) {
          wakeRequested = false;
          resolve();
          return;
        }
        // 폴링 타이머와 fs.watch 신호 중 먼저 온 쪽이 다음 reconcile을 시작한다.
        const timer = setTimeout(() => {
          wakeResolver = null;
          resolve();
        }, options.intervalMs);
        wakeResolver = () => {
          clearTimeout(timer);
          wakeResolver = null;
          resolve();
        };
      });
    }
  } finally {
    for (const watcher of watchers) watcher.close();
    let latest = null;
    try { latest = JSON.parse(await readFile(paths.pidPath, 'utf8')); } catch {}
    if (Number(latest?.pid) === process.pid) await rm(paths.pidPath, { force: true });
  }
  return { command: 'watch', running: false, reason: '종료 신호' };
}

// CLI 결과는 --json에서 안정 JSON, 기본 모드에서 같은 내용을 들여써 출력한다.
async function main() {
  const options = parseArguments(process.argv.slice(2));
  let result;
  if (options.command === 'ingest-routed') {
    const envelope = JSON.parse(readFileSync(0, 'utf8').replace(/^\uFEFF/, ''));
    result = await ingestRoutedEnvelope(envelope, { workspaceRoot: options.workspaceRoot, chatRoot: options.chatRoot });
  } else if (options.command === 'reconcile') result = await reconcileOnce(options);
  else if (options.command === 'ensure') result = await ensureWatcher(options);
  else if (options.command === 'watch') result = await runWatcher(options);
  else if (options.command === 'status') result = await recorderStatus(options);
  else if (options.command === 'verify') result = await verifyRecording(options);
  else throw new Error(`알 수 없는 명령: ${options.command}`);
  process.stdout.write(`${JSON.stringify(result, null, options.json ? 0 : 2)}\n`);
  if (options.command === 'verify' && !result.ok) process.exitCode = 2;
}

// import 기반 테스트에서는 실행하지 않고 직접 호출 시에만 CLI를 시작한다.
if (path.resolve(process.argv[1] ?? '') === path.resolve(CLI_PATH)) {
  main().catch((error) => {
    process.stderr.write(`${JSON.stringify({ ok: false, error: error.message })}\n`);
    process.exitCode = 1;
  });
}
