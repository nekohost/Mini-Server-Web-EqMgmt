// [역할] 대화 기록기의 필터·시각·중복·분할·플랫폼 관계 판별을 실제 파일 단위로 검증한다.
// [의존성 관계] Node 내장 test와 staging recorder 모듈·비식별 fixture만 사용한다.
// [변경 시 영향도] 원본 스키마나 기록 형식을 바꾸면 성공·실패 fixture를 함께 갱신해야 한다.

import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { collectAntigravityEvents } from './conversation-recorder/antigravity.mjs';
import { parseCodexTranscript } from './conversation-recorder/codex.mjs';
import { COMPANION_LIMIT_BYTES, createEvent, emptyState, projectEvents, redactSecrets, splitCompanionBlocks, toKstParts, withWriterLock } from './conversation-recorder/core.mjs';
import { ensureWatcher, parseArguments, reconcileOnce, recorderStatus, shouldPersistState, verifyRecording } from './conversation-recorder.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.join(HERE, 'fixtures', 'conversation-recorder');
const FIXTURE_WORKSPACE = 'C:\\fixture\\project';

// fixture 원문을 UTF-8로 읽는다.
async function fixture(name) {
  return readFile(path.join(FIXTURES, name), 'utf8');
}

test('Codex 직접 대화는 사용자·commentary·final만 실제 시각으로 추출한다', async () => {
  const parsed = parseCodexTranscript(await fixture('codex-main.jsonl'), { workspaceRoot: FIXTURE_WORKSPACE });
  assert.equal(parsed.events.length, 3);
  assert.deepEqual(parsed.events.map((event) => event.channel), ['user', 'commentary', 'final_answer']);
  assert.equal(parsed.events[0].time.date, '2026-09-07');
  assert.equal(parsed.events[1].time.date, '2026-09-08');
  assert.ok(parsed.events.every((event) => !event.content.includes('기록 금지 도구')));
});

test('Codex 하위 에이전트는 task·status·final을 companion 대상으로 분리한다', async () => {
  const parsed = parseCodexTranscript(await fixture('codex-subagent.jsonl'), { workspaceRoot: FIXTURE_WORKSPACE });
  assert.equal(parsed.isSubagent, true);
  assert.deepEqual(parsed.events.map((event) => event.channel), ['subagent_task', 'subagent_status', 'subagent_final']);
  assert.ok(parsed.events.every((event) => event.destination === 'subagent' && event.parentThreadId === 'codex-main'));
});

test('KST 변환과 비밀 치환은 원본 시각·본문 구조를 보존한다', () => {
  assert.deepEqual(toKstParts('2026-09-07T15:00:00.001Z'), { date: '2026-09-08', year: '2026', month: '09', day: '08', header: '2026-09-08 00:00:00.001', epochMs: Date.parse('2026-09-07T15:00:00.001Z') });
  const redacted = redactSecrets('password=hunter2\nAuthorization: Bearer abcdefghijklmnop\nmail@example.com 010-1234-5678 900101-1234567\n정상 본문');
  assert.ok(!redacted.includes('hunter2'));
  assert.ok(!redacted.includes('abcdefghijklmnop'));
  assert.ok(!redacted.includes('mail@example.com'));
  assert.ok(!redacted.includes('010-1234-5678'));
  assert.ok(!redacted.includes('900101-1234567'));
  assert.ok(redacted.includes('정상 본문'));
});

test('64 KiB companion 분할은 UTF-8 경계와 전체 원문을 보존한다', () => {
  const source = `## 헤더\n\n${'한글🙂'.repeat(18000)}\n`;
  const parts = splitCompanionBlocks([source]);
  assert.ok(parts.length > 1);
  assert.ok(parts.every((part) => Buffer.byteLength(part, 'utf8') <= COMPANION_LIMIT_BYTES));
  assert.equal(parts.join(''), source);
});

test('projector는 시간순 삽입·재실행 중복 방지·하위 receipt 링크를 보장한다', async (context) => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'conversation-recorder-projector-'));
  context.after(() => rm(workspace, { recursive: true, force: true }));
  const state = emptyState();
  const late = createEvent({ provider: 'codex', threadId: 'main', sourceEventId: 'late', occurredAt: '2026-09-08T01:00:02Z', sourceOrdinal: 2, actor: 'assistant', channel: 'final_answer', speaker: 'Codex', content: '나중 답변' });
  const early = createEvent({ provider: 'codex', threadId: 'main', sourceEventId: 'early', occurredAt: '2026-09-08T01:00:01Z', sourceOrdinal: 1, actor: 'user', channel: 'user', speaker: '사용자', content: '먼저 질문' });
  const task = createEvent({ provider: 'codex', threadId: 'child', sourceEventId: 'task', occurredAt: '2026-09-08T01:00:03Z', sourceOrdinal: 3, actor: 'parent', channel: 'subagent_task', speaker: '부모 → Codex 하위 에이전트', content: '검토', destination: 'subagent', parentThreadId: 'main', agentId: 'child' });
  const final = createEvent({ provider: 'codex', threadId: 'child', sourceEventId: 'final', occurredAt: '2026-09-08T01:00:04Z', sourceOrdinal: 4, actor: 'assistant', channel: 'subagent_final', speaker: 'Codex 하위 에이전트 → 부모', content: '완료', destination: 'subagent', parentThreadId: 'main', agentId: 'child' });
  const first = await projectEvents({ workspaceRoot: workspace, state, events: [late, task, early, final] });
  assert.equal(first.written, 3);
  // Chat 쓰기 뒤 state 저장 전에 중단된 상황처럼 빈 state로 다시 투영한다.
  const second = await projectEvents({ workspaceRoot: workspace, state: emptyState(), events: [late, task, early, final] });
  assert.equal(second.written, 0);
  const main = await readFile(path.join(workspace, 'Chat', '2026', '09', '08.md'), 'utf8');
  assert.ok(main.indexOf('먼저 질문') < main.indexOf('나중 답변'));
  assert.equal((main.match(/나중 답변/g) ?? []).length, 1);
  assert.match(main, /\.\.\/\.\.\/Subagents\/2026\/09\/08\/codex_child_part-001\.md/);
});

test('Antigravity mailbox sender·recipient가 worker를 main과 연결한다', async (context) => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), 'conversation-recorder-antigravity-'));
  context.after(() => rm(temporary, { recursive: true, force: true }));
  const brain = path.join(temporary, 'brain');
  const mainId = '11111111-1111-1111-1111-111111111111';
  const workerId = '22222222-2222-2222-2222-222222222222';
  const mainLogs = path.join(brain, mainId, '.system_generated', 'logs');
  const mainMessages = path.join(brain, mainId, '.system_generated', 'messages');
  const workerLogs = path.join(brain, workerId, '.system_generated', 'logs');
  await Promise.all([mkdir(mainLogs, { recursive: true }), mkdir(mainMessages, { recursive: true }), mkdir(workerLogs, { recursive: true })]);
  await Promise.all([
    writeFile(path.join(mainLogs, 'transcript.jsonl'), await fixture('antigravity-main.jsonl'), 'utf8'),
    writeFile(path.join(workerLogs, 'transcript.jsonl'), await fixture('antigravity-worker.jsonl'), 'utf8'),
    writeFile(path.join(mainMessages, 'handoff.json'), JSON.stringify({ id: 'handoff', recipient: mainId, sender: workerId, timestamp: '2026-09-08T01:01:01.500Z', content: '중간 상태' }), 'utf8'),
  ]);
  const result = await collectAntigravityEvents({ workspaceRoot: FIXTURE_WORKSPACE, state: emptyState(), homeDirectory: temporary, roots: [brain], force: true });
  assert.equal(result.status, 'ok');
  assert.ok(result.registeredConversations.includes(mainId));
  const workerEvents = result.events.filter((event) => event.threadId === workerId);
  assert.deepEqual(workerEvents.map((event) => event.channel).sort(), ['subagent_final', 'subagent_status', 'subagent_task']);
  assert.ok(workerEvents.every((event) => event.destination === 'subagent' && event.parentThreadId === mainId));
  assert.ok(result.events.every((event) => !event.content.includes('내부 도구 원문')));
});

test('Antigravity workspace registry는 새 직접 conversation 첫 턴을 식별한다', async (context) => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), 'conversation-recorder-antigravity-registry-'));
  context.after(() => rm(temporary, { recursive: true, force: true }));
  const conversationId = '33333333-3333-3333-3333-333333333333';
  const brain = path.join(temporary, '.gemini', 'antigravity', 'brain');
  const logs = path.join(brain, conversationId, '.system_generated', 'logs');
  const cache = path.join(temporary, '.gemini', 'antigravity-cli', 'cache');
  await Promise.all([mkdir(logs, { recursive: true }), mkdir(cache, { recursive: true })]);
  const oneTurn = `${JSON.stringify({ source: 'USER_EXPLICIT', type: 'USER_INPUT', status: 'DONE', step_index: 1, created_at: '2026-09-08T02:00:00.000Z', content: '<USER_REQUEST>\n첫 턴\n</USER_REQUEST>' })}\n`;
  await Promise.all([
    writeFile(path.join(logs, 'transcript.jsonl'), oneTurn, 'utf8'),
    writeFile(path.join(cache, 'conversation_metadata.json'), JSON.stringify({ [FIXTURE_WORKSPACE]: conversationId }), 'utf8'),
  ]);
  const result = await collectAntigravityEvents({ workspaceRoot: FIXTURE_WORKSPACE, state: emptyState(), homeDirectory: temporary, roots: [brain], force: true });
  assert.equal(result.status, 'ok');
  assert.ok(result.registeredConversations.includes(conversationId));
  assert.equal(result.events.length, 1);
  assert.equal(result.events[0].channel, 'user');
});

test('writer lock은 동시 writer와 살아 있는 PID lock을 거부한다', async (context) => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), 'conversation-recorder-lock-'));
  context.after(() => rm(temporary, { recursive: true, force: true }));
  const lockPath = path.join(temporary, 'writer.lock');
  let release;
  const held = withWriterLock(lockPath, () => new Promise((resolve) => { release = resolve; }));
  while (!release) await new Promise((resolve) => setTimeout(resolve, 1));
  await assert.rejects(() => withWriterLock(lockPath, async () => {}), /writer가 실행 중/);
  release();
  await held;
});

test('손상 JSONL은 cursor 전진 대신 명시적 오류가 된다', () => {
  assert.throws(() => parseCodexTranscript('{not-json}\n', { workspaceRoot: FIXTURE_WORKSPACE }), /JSON 파싱 실패/);
});

test('reconcile은 fs.watch 알림 없이 stat 변화로 새 이벤트를 반영하고 verify가 일치를 확인한다', async (context) => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'conversation-recorder-integration-'));
  context.after(() => rm(workspace, { recursive: true, force: true }));
  const home = path.join(workspace, 'home');
  const sessions = path.join(home, '.codex', 'sessions', '2026', '09', '07');
  await mkdir(sessions, { recursive: true });
  const source = path.join(sessions, 'rollout.jsonl');
  const rows = [
    { timestamp: '2026-09-08T03:00:00.000Z', type: 'session_meta', payload: { id: 'integration-main', cwd: workspace, thread_source: 'user', source: 'vscode' } },
    { timestamp: '2026-09-08T03:00:01.000Z', type: 'response_item', payload: { id: 'integration-user', type: 'message', role: 'user', content: [{ type: 'input_text', text: '통합 질문' }], internal_chat_message_metadata_passthrough: { content_item_kinds: ['user.text'] } } },
    { timestamp: '2026-09-08T03:00:02.000Z', type: 'response_item', payload: { id: 'integration-final', type: 'message', role: 'assistant', phase: 'final_answer', content: [{ type: 'output_text', text: '통합 답변' }] } },
  ];
  await writeFile(source, `${rows.map((row) => JSON.stringify(row)).join('\n')}\n`, 'utf8');
  const options = { workspaceRoot: workspace, chatRoot: path.join(workspace, 'Chat'), homeDirectory: home, platforms: ['codex'], dryRun: false, force: false, intervalMs: 1500 };
  const first = await reconcileOnce(options);
  assert.equal(first.projection.written, 2);
  rows.push({ timestamp: '2026-09-08T03:00:03.000Z', type: 'response_item', payload: { id: 'integration-commentary', type: 'message', role: 'assistant', phase: 'commentary', content: [{ type: 'output_text', text: '추가 안내' }] } });
  await writeFile(source, `${rows.map((row) => JSON.stringify(row)).join('\n')}\n`, 'utf8');
  const started = Date.now();
  const second = await reconcileOnce(options);
  assert.equal(second.projection.written, 1);
  assert.equal(second.statePersisted, true);
  assert.ok(Date.now() - started < 5000);
  const statePath = path.join(workspace, 'Chat', '.state', 'conversation-recorder.json');
  const stateBeforeIdlePoll = await stat(statePath);
  const third = await reconcileOnce(options);
  const stateAfterIdlePoll = await stat(statePath);
  assert.equal(third.statePersisted, false);
  assert.equal(stateAfterIdlePoll.mtimeMs, stateBeforeIdlePoll.mtimeMs);
  const verified = await verifyRecording(options);
  assert.equal(verified.ok, true);
  assert.equal(verified.sourceEvents, 3);
});

test('상태 저장 판단은 논리 변경과 60초 heartbeat를 구분한다', () => {
  const previous = emptyState();
  previous.updatedAt = '2026-09-09T00:00:00.000Z';
  previous.health.recorder = { status: 'ok', lastReconcileAt: '2026-09-09T00:00:00.000Z', platforms: ['codex'] };
  const timestampOnly = structuredClone(previous);
  timestampOnly.health.recorder.lastReconcileAt = '2026-09-09T00:00:01.500Z';
  assert.equal(shouldPersistState(previous, timestampOnly, Date.parse('2026-09-09T00:00:30.000Z')), false);
  assert.equal(shouldPersistState(previous, timestampOnly, Date.parse('2026-09-09T00:01:00.000Z')), true);
  const changed = structuredClone(timestampOnly);
  changed.sources.example = { size: 1, mtimeMs: 1 };
  assert.equal(shouldPersistState(previous, changed, Date.parse('2026-09-09T00:00:01.500Z')), true);
});

test('CLI는 Windows 보강 폴링 범위를 1~2초로 제한한다', () => {
  assert.equal(parseArguments(['status', '--interval-ms', '1500']).intervalMs, 1500);
  assert.throws(() => parseArguments(['status', '--interval-ms', '999']), /1000~2000/);
  assert.throws(() => parseArguments(['status', '--interval-ms', '2001']), /1000~2000/);
});

test('ensure는 watcher 하나만 시작하고 다음 호출에서 같은 PID를 재사용한다', async (context) => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'conversation-recorder-watcher-'));
  let watcherPid = null;
  context.after(async () => {
    if (watcherPid) {
      try { process.kill(watcherPid, 'SIGTERM'); } catch {}
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
    await rm(workspace, { recursive: true, force: true });
  });
  const home = path.join(workspace, 'home');
  const sessions = path.join(home, '.codex', 'sessions', '2026', '09', '09');
  await mkdir(sessions, { recursive: true });
  const sourceRows = [
    { timestamp: '2026-09-09T00:00:00.000Z', type: 'session_meta', payload: { id: 'watch-main', cwd: workspace, thread_source: 'user' } },
    { timestamp: '2026-09-09T00:00:01.000Z', type: 'response_item', payload: { id: 'watch-user', type: 'message', role: 'user', content: [{ type: 'input_text', text: 'watch 질문' }], internal_chat_message_metadata_passthrough: { content_item_kinds: ['user.text'] } } },
  ];
  await writeFile(path.join(sessions, 'watch.jsonl'), `${sourceRows.map((row) => JSON.stringify(row)).join('\n')}\n`, 'utf8');
  const options = { workspaceRoot: workspace, chatRoot: path.join(workspace, 'Chat'), homeDirectory: home, platforms: ['codex'], dryRun: false, force: false, intervalMs: 1500 };
  const first = await ensureWatcher(options);
  watcherPid = first.watcher.pid;
  assert.equal(first.watcher.started, true);
  const second = await ensureWatcher(options);
  assert.equal(second.watcher.started, false);
  assert.equal(second.watcher.pid, watcherPid);
  const status = await recorderStatus(options);
  assert.equal(status.watcher.running, true);
});
