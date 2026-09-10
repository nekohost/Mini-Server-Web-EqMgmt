// [역할] 사용자 발언 수신 대상 AI 명시화 기능(Staging 후보)의 어댑터 및 코어 호환성 검증
// [의존성] candidate_core.mjs, candidate_codex.mjs, candidate_antigravity.mjs, fixture

import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { createEvent, emptyState, eventAlreadyRecorded, projectEvents, renderEventBlock } from './candidate_core.mjs';
import { parseCodexTranscript } from './candidate_codex.mjs';
import { collectAntigravityEvents } from './candidate_antigravity.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.join(HERE, '..', '.agent-governance', 'tooling', 'fixtures', 'conversation-recorder');
const FIXTURE_WORKSPACE = 'C:\\fixture\\project';

async function fixture(name) {
  return readFile(path.join(FIXTURES, name), 'utf8');
}

test('[Staging] Codex 어댑터는 사용자 발언에 "사용자 → Codex" speaker를 부여한다', async () => {
  const parsed = parseCodexTranscript(await fixture('codex-main.jsonl'), { workspaceRoot: FIXTURE_WORKSPACE });
  assert.equal(parsed.events.length, 3);
  const userEvent = parsed.events.find((e) => e.channel === 'user');
  assert.ok(userEvent, 'user 이벤트가 존재해야 함');
  assert.equal(userEvent.actor, 'user');
  assert.equal(userEvent.speaker, '사용자 → Codex');

  const finalEvent = parsed.events.find((e) => e.channel === 'final_answer');
  assert.ok(finalEvent, 'final_answer 이벤트가 존재해야 함');
  assert.equal(finalEvent.speaker, 'Codex');
});

test('[Staging] Codex 하위 에이전트는 기존 부모→하위 규격을 유지한다', async () => {
  const parsed = parseCodexTranscript(await fixture('codex-subagent.jsonl'), { workspaceRoot: FIXTURE_WORKSPACE });
  assert.equal(parsed.isSubagent, true);
  const taskEvent = parsed.events.find((e) => e.channel === 'subagent_task');
  assert.ok(taskEvent);
  assert.equal(taskEvent.speaker, '부모 → Codex 하위 에이전트');
});

test('[Staging] Antigravity 어댑터는 사용자 발언에 "사용자 → Gemini" speaker를 부여한다', async (context) => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), 'staging-antigravity-'));
  context.after(() => rm(temporary, { recursive: true, force: true }));
  const conversationId = '55555555-5555-5555-5555-555555555555';
  const brain = path.join(temporary, '.gemini', 'antigravity', 'brain');
  const logs = path.join(brain, conversationId, '.system_generated', 'logs');
  const cache = path.join(temporary, '.gemini', 'antigravity-cli', 'cache');
  await Promise.all([mkdir(logs, { recursive: true }), mkdir(cache, { recursive: true })]);
  const userTurn = JSON.stringify({ source: 'USER_EXPLICIT', type: 'USER_INPUT', status: 'DONE', step_index: 1, created_at: '2026-09-08T02:00:00.000Z', content: '<USER_REQUEST>\n테스트 요청\n</USER_REQUEST>' });
  const modelTurn = JSON.stringify({ source: 'MODEL', type: 'PLANNER_RESPONSE', status: 'DONE', step_index: 2, created_at: '2026-09-08T02:00:01.000Z', content: '테스트 응답', tool_calls: [] });
  await Promise.all([
    writeFile(path.join(logs, 'transcript.jsonl'), `${userTurn}\n${modelTurn}\n`, 'utf8'),
    writeFile(path.join(cache, 'conversation_metadata.json'), JSON.stringify({ [FIXTURE_WORKSPACE]: conversationId }), 'utf8'),
  ]);
  const result = await collectAntigravityEvents({ workspaceRoot: FIXTURE_WORKSPACE, state: emptyState(), homeDirectory: temporary, roots: [brain], force: true });
  assert.equal(result.status, 'ok');
  assert.equal(result.events.length, 2);
  const userEvent = result.events.find((e) => e.channel === 'user');
  assert.ok(userEvent);
  assert.equal(userEvent.actor, 'user');
  assert.equal(userEvent.speaker, '사용자 → Gemini');

  const finalEvent = result.events.find((e) => e.channel === 'final_answer');
  assert.ok(finalEvent);
  assert.equal(finalEvent.speaker, 'Gemini');
});

test('[Staging] eventAlreadyRecorded: provenance 없는 legacy "## 사용자" 기록도 중복 없이 매칭한다', () => {
  const event = createEvent({
    provider: 'antigravity',
    threadId: 't-1',
    sourceEventId: 's-1',
    occurredAt: '2026-09-08T01:00:00.000Z',
    actor: 'user',
    channel: 'user',
    speaker: '사용자 → Gemini',
    content: '과거 대화 내용입니다.',
  });

  // 1. 과거 legacy 형식 (provenance 없음, ## 사용자 단독)
  const legacyMarkdown = `## 사용자 2026-09-08 10:00:00.000\n\n과거 대화 내용입니다.\n`;
  const legacyCheck = eventAlreadyRecorded(legacyMarkdown, event);
  assert.equal(legacyCheck.matched, true, '과거 ## 사용자 헤더와 내용이 일치하면 matched여야 함');
  assert.equal(legacyCheck.mode, 'legacy-exact');

  // 2. 신규 형식 (## 사용자 → Gemini)
  const newMarkdown = `## 사용자 → Gemini 2026-09-08 10:00:00.000\n\n과거 대화 내용입니다.\n`;
  const newCheck = eventAlreadyRecorded(newMarkdown, event);
  assert.equal(newCheck.matched, true);
  assert.equal(newCheck.mode, 'legacy-exact');

  // 3. 다른 내용인 경우
  const differentMarkdown = `## 사용자 2026-09-08 10:00:00.000\n\n전혀 다른 내용입니다.\n`;
  const diffCheck = eventAlreadyRecorded(differentMarkdown, event);
  assert.equal(diffCheck.matched, false);
});

test('[Staging] projector: 과거 "## 사용자" 기록이 있는 일자 파일에 재투영 시 중복 삽입이 차단된다', async (context) => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'staging-projector-'));
  context.after(() => rm(workspace, { recursive: true, force: true }));

  // 기존 일자 파일 시뮬레이션 (과거 기록: provenance 없음, ## 사용자 단독)
  const chatDayDir = path.join(workspace, 'Chat', '2026', '09');
  await mkdir(chatDayDir, { recursive: true });
  const existingChat = `## 사용자 2026-09-08 10:00:00.000\n\n과거 질문입니다.\n\n## Gemini 2026-09-08 10:00:01.000\n\n과거 답변입니다.\n`;
  await writeFile(path.join(chatDayDir, '08.md'), existingChat, 'utf8');

  // 신규 speaker('사용자 → Gemini')로 과거 이벤트 재수집 시뮬레이션
  const pastUserEvent = createEvent({
    provider: 'antigravity',
    threadId: 't-legacy',
    sourceEventId: '1',
    occurredAt: '2026-09-08T01:00:00.000Z', // KST 10:00:00.000
    sourceOrdinal: 1,
    actor: 'user',
    channel: 'user',
    speaker: '사용자 → Gemini',
    content: '과거 질문입니다.',
  });

  const state = emptyState();
  const result = await projectEvents({
    workspaceRoot: workspace,
    state,
    events: [pastUserEvent],
    dryRun: false,
    trustReceipts: false, // receipt 없이 파일 본문 대조 강제
  });

  assert.equal(result.written, 0, '이미 존재하는 과거 기록이므로 쓰이지 않아야 함');
  assert.equal(result.existing, 1, 'existing 카운트가 1이어야 함');

  // 파일 내용이 변경되지 않고 원본 그대로인지 확인
  const contentAfter = await readFile(path.join(chatDayDir, '08.md'), 'utf8');
  assert.equal(contentAfter, existingChat, '과거 파일 내용이 변형되어서는 안 됨');
});

test('[Staging] projector: 신규 발언은 "## 사용자 → Gemini" 헤더로 정확히 기록된다', async (context) => {
  const workspace = await mkdtemp(path.join(os.tmpdir(), 'staging-projector-new-'));
  context.after(() => rm(workspace, { recursive: true, force: true }));

  const newUserEvent = createEvent({
    provider: 'antigravity',
    threadId: 't-new',
    sourceEventId: '1',
    occurredAt: '2026-09-09T05:00:00.000Z', // KST 14:00:00.000
    sourceOrdinal: 1,
    actor: 'user',
    channel: 'user',
    speaker: '사용자 → Gemini',
    content: '새로운 질문입니다.',
  });

  const state = emptyState();
  const result = await projectEvents({
    workspaceRoot: workspace,
    state,
    events: [newUserEvent],
    dryRun: false,
  });

  assert.equal(result.written, 1);
  const writtenChat = await readFile(path.join(workspace, 'Chat', '2026', '09', '09.md'), 'utf8');
  assert.ok(writtenChat.includes('## 사용자 → Gemini 2026-09-09 14:00:00.000\n\n새로운 질문입니다.'));
});
