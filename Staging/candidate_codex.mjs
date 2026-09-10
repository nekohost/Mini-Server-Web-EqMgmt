// [역할] Codex rollout JSONL에서 현재 workspace의 직접 대화와 허용된 하위 에이전트 이력을 추출한다.
// [의존성 관계] candidate_core.mjs의 JSONL·경로·이벤트 정규화 기능과 Codex session_meta/response_item 스키마에 의존한다.
// [변경 시 영향도] Codex 로그 스키마가 달라지면 알 수 없는 행을 추정하지 말고 fixture와 capability를 갱신해야 한다.

import { readdir, readFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createEvent, extractCodexMessageText, normalizePathForComparison, parseJsonLines, sourceFingerprint } from './candidate_core.mjs';

// 디렉터리 트리를 순회해 확장자가 일치하는 파일만 결정적 순서로 반환한다.
async function listFilesRecursive(root, extension) {
  // 결과 배열은 정렬 후 반환한다.
  const result = [];
  // 재귀 함수는 디렉터리 부재를 상위 adapter 오류로 전달한다.
  async function visit(directory) {
    // dirent를 사용해 추가 stat 호출을 줄인다.
    const entries = await readdir(directory, { withFileTypes: true });
    // 파일시스템 반환 순서에 의존하지 않도록 이름순으로 처리한다.
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      // 현재 항목의 절대 경로를 만든다.
      const candidate = path.join(directory, entry.name);
      // 하위 디렉터리는 재귀 탐색한다.
      if (entry.isDirectory()) await visit(candidate);
      // 요청 확장자 파일만 수집한다.
      else if (entry.isFile() && entry.name.endsWith(extension)) result.push(candidate);
    }
  }
  // 루트부터 탐색한다.
  await visit(root);
  // 결정적 경로 목록을 반환한다.
  return result;
}
// Codex content phase가 사용자에게 실제 표시되는 범위인지 판정한다.
function visibleAssistantPhase(phase) {
  // commentary와 final_answer만 사용자 화면에 표시된 대화로 취급한다.
  return phase === 'commentary' || phase === 'final_answer';
}

// 하나의 Codex rollout을 직접 대화 또는 하위 에이전트 이벤트로 변환한다.
export function parseCodexTranscript(text, { workspaceRoot, sourceLabel = 'codex.jsonl' }) {
  // JSONL을 엄격히 파싱한다.
  const rows = parseJsonLines(text, sourceLabel);
  // 첫 session_meta는 workspace와 thread 종류의 신뢰 기준이다.
  const metaRow = rows.find((row) => row.value?.type === 'session_meta');
  // session_meta가 없으면 다른 JSONL을 잘못 읽은 것이므로 차단한다.
  if (!metaRow) throw new Error(`${sourceLabel}: Codex session_meta가 없습니다.`);
  // 세션 메타데이터의 payload를 읽는다.
  const meta = metaRow.value.payload ?? {};
  // 다른 프로젝트 대화를 섞지 않도록 정규화한 cwd를 정확히 비교한다.
  if (normalizePathForComparison(meta.cwd) !== normalizePathForComparison(workspaceRoot)) return { matchedWorkspace: false, events: [], threadId: String(meta.id ?? meta.session_id ?? '') };
  // thread ID는 두 알려진 필드 중 실제 값을 사용한다.
  const threadId = String(meta.id ?? meta.session_id ?? '');
  // 식별자가 없으면 provenance를 만들 수 없으므로 실패한다.
  if (!threadId) throw new Error(`${sourceLabel}: Codex thread ID가 없습니다.`);
  // guardian/approval review는 사용자 대화나 허용된 하위 작업 이력이 아니다.
  if (meta.thread_source === 'guardian_review') return { matchedWorkspace: true, excluded: 'guardian_review', events: [], threadId };
  // 구조화된 subagent spawn 메타데이터를 읽는다.
  const spawn = meta.source?.subagent?.thread_spawn;
  // Codex가 명시적으로 subagent로 표시한 세션만 companion 대상으로 삼는다.
  const isSubagent = meta.thread_source === 'subagent' && Boolean(spawn);
  // 일반 사용자 thread 이외의 알 수 없는 종류는 추정하지 않는다.
  if (!isSubagent && meta.thread_source !== 'user') return { matchedWorkspace: true, excluded: `unsupported-thread-source:${meta.thread_source}`, events: [], threadId };
  // 변환된 표시 이벤트를 누적한다.
  const events = [];
  // 모든 response_item message를 원본 순서대로 검사한다.
  for (const row of rows) {
    // Codex 표시 메시지가 아니면 내부 event/tool 데이터이므로 제외한다.
    if (row.value?.type !== 'response_item' || row.value?.payload?.type !== 'message') continue;
    // 메시지 payload를 읽는다.
    const payload = row.value.payload;
    // 사용자와 assistant 이외의 system/developer 역할은 제외한다.
    if (payload.role !== 'user' && payload.role !== 'assistant') continue;
    // Codex가 user 역할로 주입하는 environment context 등은 실제 user.text가 아니므로 제외한다.
    const contentKinds = payload.internal_chat_message_metadata_passthrough?.content_item_kinds;
    if (payload.role === 'user' && Array.isArray(contentKinds) && !contentKinds.includes('user.text')) continue;
    // assistant는 실제 표시 phase만 허용한다.
    if (payload.role === 'assistant' && !visibleAssistantPhase(payload.phase)) continue;
    // 표시 가능한 content 배열의 원문만 결합한다.
    const content = extractCodexMessageText(payload.content);
    // 빈 메시지는 Chat 블록을 만들지 않는다.
    if (!content) continue;
    // response item 자체 timestamp가 없으면 JSONL envelope timestamp를 사용한다.
    const occurredAt = row.value.timestamp;
    // subagent 세션은 직접 Chat 대신 companion speaker와 channel을 사용한다.
    if (isSubagent) {
      // 사용자 역할은 부모가 전달한 작업, assistant final/commentary는 반환·상태로 구분한다.
      const channel = payload.role === 'user' ? 'subagent_task' : payload.phase === 'final_answer' ? 'subagent_final' : 'subagent_status';
      // 허용된 하위 작업 메시지를 companion 이벤트로 만든다.
      events.push(createEvent({ provider: 'codex', threadId, sourceEventId: payload.id ?? `line-${row.lineNumber}`, sourceOrdinal: row.lineNumber, occurredAt, actor: payload.role === 'user' ? 'parent' : 'subagent', channel, speaker: payload.role === 'user' ? '부모 → Codex 하위 에이전트' : 'Codex 하위 에이전트 → 부모', content, destination: 'subagent', parentThreadId: spawn.parent_thread_id, agentId: spawn.agent_path ?? threadId, agentName: spawn.agent_nickname ?? '', taskName: spawn.agent_path ?? '' }));
      // 다음 메시지로 이동한다.
      continue;
    }
    // 직접 사용자·assistant 대화는 날짜별 주 Chat에 기록한다. (수신 대상 명시: 사용자 → Codex)
    events.push(createEvent({ provider: 'codex', threadId, sourceEventId: payload.id ?? `line-${row.lineNumber}`, sourceOrdinal: row.lineNumber, occurredAt, actor: payload.role, channel: payload.role === 'user' ? 'user' : payload.phase, speaker: payload.role === 'user' ? '사용자 → Codex' : 'Codex', content, destination: 'main' }));
  }
  // 세션 분류와 이벤트를 반환한다.
  return { matchedWorkspace: true, isSubagent, events, threadId };
}

// 현재 PC의 Codex 원본 중 변경된 workspace 세션만 읽는다.
export async function collectCodexEvents({ workspaceRoot, state, homeDirectory = os.homedir(), force = false }) {
  // Codex 기본 session 저장 경로를 사용한다.
  const sessionsRoot = path.join(homeDirectory, '.codex', 'sessions');
  // 모든 날짜 폴더를 탐색하므로 이전 날짜에 시작된 연속 세션도 놓치지 않는다.
  let files;
  try {
    files = await listFilesRecursive(sessionsRoot, '.jsonl');
  } catch (error) {
    // 원본 경로 부재는 해당 플랫폼 unsupported 오류로 반환한다.
    if (error.code === 'ENOENT') return { platform: 'codex', status: 'unsupported', events: [], snapshots: {}, errors: [`Codex sessions 경로 없음: ${sessionsRoot}`] };
    // 다른 접근 오류도 명시적으로 반환한다.
    return { platform: 'codex', status: 'error', events: [], snapshots: {}, errors: [error.message] };
  }
  // 변경 파일 결과를 누적한다.
  const events = [];
  const snapshots = {};
  const errors = [];
  // 모든 session 파일을 실제 stat 기준으로 검사한다.
  for (const file of files) {
    try {
      // Windows fs.watch 누락과 무관한 size:mtime fingerprint를 계산한다.
      const fingerprint = await sourceFingerprint(file);
      // 현재 snapshot은 파싱 성공 뒤 state에 반영된다.
      snapshots[file] = fingerprint;
      // 이전 성공 fingerprint와 같으면 폴링 주기마다 전체 파싱하지 않는다.
      if (!force && state.sources[file] === fingerprint) continue;
      // UTF-8 JSONL 원본을 읽는다.
      const text = await readFile(file, 'utf8');
      // 현재 workspace와 일치하는 표시 이벤트만 추출한다.
      const parsed = parseCodexTranscript(text, { workspaceRoot, sourceLabel: file });
      // workspace가 다르면 snapshot만 기억하고 이벤트를 추가하지 않는다.
      if (parsed.matchedWorkspace) events.push(...parsed.events);
    } catch (error) {
      // 파싱 실패 파일은 snapshot을 제거하여 다음 reconcile에서 다시 시도한다.
      delete snapshots[file];
      // 오류에는 원문 대신 파일 경로와 원인만 남긴다.
      errors.push(`${file}: ${error.message}`);
    }
  }
  // 일부 파일 실패도 플랫폼 상태에 반영한다.
  return { platform: 'codex', status: errors.length ? 'error' : 'ok', events, snapshots, errors };
}
