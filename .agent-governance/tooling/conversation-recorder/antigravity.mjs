// [역할] Antigravity brain conversation 전사에서 workspace 직접 대화와 하위 작업 handoff를 추출한다.
// [의존성 관계] core.mjs와 <appDataDir>/brain/<conversation-id>/.system_generated/logs/transcript.jsonl 형식에 의존한다.
// [변경 시 영향도] conversation 식별 또는 MODEL 필터를 바꾸면 다른 프로젝트·도구 출력 혼입 시험을 다시 수행해야 한다.

import { readdir, readFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createEvent, normalizeNewlines, normalizePathForComparison, parseJsonLines, sourceFingerprint } from './core.mjs';

// Antigravity의 세 설치 변형에서 brain 루트 후보를 만든다.
export function defaultAntigravityRoots(homeDirectory = os.homedir()) {
  // 사용자 제공 경로 구조와 실제 설치 변형을 모두 명시적으로 나열한다.
  return [path.join(homeDirectory, '.gemini', 'antigravity', 'brain'), path.join(homeDirectory, '.gemini', 'antigravity-cli', 'brain'), path.join(homeDirectory, '.gemini', 'antigravity-ide', 'brain')];
}

// JSON 문자열 안의 이중 escape와 Windows 구분자를 경로 비교용 형태로 바꾼다.
function normalizeTranscriptForSearch(value) {
  // JSON raw의 두 백슬래시와 일반 백슬래시를 모두 슬래시로 치환한다.
  return String(value).replaceAll('\\\\', '/').replaceAll('\\', '/').toLowerCase();
}

// USER_INPUT wrapper에서 사용자가 실제 입력한 USER_REQUEST 원문만 꺼낸다.
export function extractAntigravityUserRequest(content) {
  // wrapper가 없으면 사용자 표시 원문인지 확정할 수 없으므로 빈 값으로 제외한다.
  const match = normalizeNewlines(content).match(/^<USER_REQUEST>(?:\n)?([\s\S]*?)(?:\n)?<\/USER_REQUEST>\s*(?:<ADDITIONAL_METADATA>[\s\S]*<\/ADDITIONAL_METADATA>)?\s*$/);
  // wrapper 안쪽만 반환하여 추가 메타데이터를 사용자 발언으로 기록하지 않는다.
  return match ? match[1] : '';
}

// transcript의 최소 메타데이터를 먼저 읽어 main/worker 관계를 판정한다.
function inspectConversation(text, conversationId, workspaceRoot, fullText = null) {
  // 전체 JSONL을 엄격히 파싱한다.
  const rows = parseJsonLines(text, `Antigravity ${conversationId}`);
  let fullRows = null;
  if (typeof fullText === 'string' && fullText.length > 0) {
    try {
      fullRows = parseJsonLines(fullText, `Antigravity Full ${conversationId}`);
    } catch {
      fullRows = null;
    }
  }
  // 실제 사용자 입력 행만 세어 장기 상위 세션과 단일 위임 세션을 구분하는 보조 근거로 사용한다.
  const userRows = rows.filter((row) => row.value?.source === 'USER_EXPLICIT' && row.value?.type === 'USER_INPUT' && row.value?.status === 'DONE');
  // child가 부모에게 보낸 message receipt의 대상 conversation ID를 수집한다.
  const sentTargets = [];
  for (const row of rows) {
    // content가 없는 tool planning 행은 검사하지 않는다.
    if (typeof row.value?.content !== 'string') continue;
    // 실제 Antigravity receipt 형식에서 UUID를 추출한다.
    const matches = [...row.value.content.matchAll(/Message sent to "([0-9a-f-]{36})"/gi)];
    // 같은 대상이 여러 번 나와도 관계 판정에는 한 번이면 충분하다.
    for (const match of matches) if (!sentTargets.includes(match[1])) sentTargets.push(match[1]);
  }
  // 원본 어딘가에 정규화한 workspace 경로가 있으면 해당 프로젝트 conversation 후보로 본다.
  const workspaceNeedle = normalizePathForComparison(workspaceRoot);
  const workspaceMatch = normalizeTranscriptForSearch(text).includes(workspaceNeedle);
  // 후속 변환에 재사용할 rows와 판정 메타데이터를 반환한다.
  return { conversationId, rows, fullRows, userRows, sentTargets, workspaceMatch };
}

// 상위 대화 또는 확인된 worker의 허용 이벤트를 공통 이벤트로 변환한다.
function conversationEvents(info, { isSubagent = false, parentThreadId = '' } = {}) {
  // 변환 결과를 원본 step 순서대로 누적한다.
  const events = [];
  // 하위 agent 식별자는 conversation ID를 안정적으로 사용한다.
  const agentId = info.conversationId;
  for (const row of info.rows) {
    // 편의를 위해 전사 event를 지역 변수에 둔다.
    const item = row.value;
    // 완료된 명시 사용자 입력은 direct user 또는 부모의 task로 처리한다.
    if (item?.source === 'USER_EXPLICIT' && item?.type === 'USER_INPUT' && item?.status === 'DONE') {
      // wrapper 밖 메타데이터를 제외한 실제 요청만 추출한다.
      const content = extractAntigravityUserRequest(item.content ?? '');
      // wrapper가 없거나 빈 요청이면 기록하지 않는다.
      if (!content) continue;
      // 하위 conversation의 유일한 user request는 부모가 맡긴 task로 companion에 보낸다.
      events.push(createEvent({ provider: 'antigravity', threadId: info.conversationId, sourceEventId: `step-${item.step_index}`, sourceOrdinal: Number(item.step_index ?? row.lineNumber), occurredAt: item.created_at, actor: isSubagent ? 'parent' : 'user', channel: isSubagent ? 'subagent_task' : 'user', speaker: isSubagent ? '부모 → Gemini 하위 에이전트' : '사용자 → Gemini', content, destination: isSubagent ? 'subagent' : 'main', parentThreadId, agentId, taskName: agentId }));
      // 같은 행을 MODEL로 다시 처리하지 않는다.
      continue;
    }
    // 사용자에게 보이는 최종 MODEL 응답은 content가 있는 완료 PLANNER_RESPONSE다.
    const visibleFinal = item?.source === 'MODEL' && item?.type === 'PLANNER_RESPONSE' && item?.status === 'DONE' && typeof item.content === 'string' && item.content.length > 0 && (!Array.isArray(item.tool_calls) || item.tool_calls.length === 0);
    // 도구 계획과 GENERIC tool output은 제외한다.
    if (!visibleFinal) continue;
    let content = item.content;
    // 텍스트가 축약된 경우 full transcript의 원본 본문을 사용한다.
    if (Array.isArray(item?.truncated_fields) && item.truncated_fields.includes('content') && Array.isArray(info.fullRows)) {
      const fullMatch = info.fullRows[row.lineNumber - 1]?.value?.step_index === item.step_index
        ? info.fullRows[row.lineNumber - 1]?.value
        : info.fullRows.find((candidate) => candidate.value?.step_index === item.step_index)?.value;
      if (typeof fullMatch?.content === 'string' && fullMatch.content.length > 0) {
        content = fullMatch.content;
      }
    }
    // 직접 최종 답변 또는 하위 handoff 원문을 기록한다.
    events.push(createEvent({ provider: 'antigravity', threadId: info.conversationId, sourceEventId: `step-${item.step_index}`, sourceOrdinal: Number(item.step_index ?? row.lineNumber), occurredAt: item.created_at, actor: 'assistant', channel: isSubagent ? 'subagent_final' : 'final_answer', speaker: isSubagent ? 'Gemini 하위 에이전트 → 부모' : 'Gemini', content, destination: isSubagent ? 'subagent' : 'main', parentThreadId, agentId, taskName: agentId }));
  }
  // 허용된 이벤트만 반환한다.
  return events;
}

// brain 루트 아래 conversation ID와 표준 transcript 경로를 수집한다.
async function discoverConversationFiles(roots) {
  // 발견 결과를 누적한다.
  const discovered = [];
  for (const root of roots) {
    try {
      // UUID 디렉터리를 이름순으로 읽는다.
      const entries = await readdir(root, { withFileTypes: true });
      entries.sort((a, b) => a.name.localeCompare(b.name));
      for (const entry of entries) {
        // 디렉터리만 conversation 후보로 취급한다.
        if (!entry.isDirectory()) continue;
        // Antigravity가 제공하는 축약 없는 표준 transcript만 사용한다.
        const conversationPath = path.join(root, entry.name);
        const transcriptPath = path.join(conversationPath, '.system_generated', 'logs', 'transcript.jsonl');
        const transcriptFullPath = path.join(conversationPath, '.system_generated', 'logs', 'transcript_full.jsonl');
        const messagesPath = path.join(conversationPath, '.system_generated', 'messages');
        // 존재 여부는 이후 stat에서 검증한다.
        discovered.push({ conversationId: entry.name, conversationPath, transcriptPath, transcriptFullPath, messagesPath });
      }
    } catch (error) {
      // 설치 변형 하나가 없으면 다른 루트를 계속 검사한다.
      if (error.code !== 'ENOENT') throw error;
    }
  }
  // 전체 후보를 반환한다.
  return discovered;
}

// 부모 conversation의 메시지 보관소에서 worker와 부모의 명시적 관계 및 handoff를 읽는다.
async function discoverMessageRelationships(candidates, snapshots, errors) {
  // sender별 parent와 사용자에게 노출 가능한 handoff 목록을 보존한다.
  const relationships = new Map();
  for (const candidate of candidates) {
    let entries;
    try {
      entries = await readdir(candidate.messagesPath, { withFileTypes: true });
    } catch (error) {
      // 메시지 폴더가 없는 일반 conversation은 정상이다.
      if (error.code !== 'ENOENT') errors.push(`${candidate.messagesPath}: ${error.message}`);
      continue;
    }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      // read.json 같은 상태 파일과 하위 디렉터리는 관계 원본이 아니다.
      if (!entry.isFile() || !entry.name.endsWith('.json') || entry.name === 'read.json') continue;
      const messagePath = path.join(candidate.messagesPath, entry.name);
      try {
        // 폴링이 새 메시지 파일도 감지하도록 각 파일 fingerprint를 남긴다.
        snapshots[messagePath] = await sourceFingerprint(messagePath);
        const message = JSON.parse(await readFile(messagePath, 'utf8'));
        // sender·recipient가 실제 conversation UUID인 mailbox 메시지만 하위 관계로 인정한다.
        const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (typeof message.sender !== 'string' || typeof message.recipient !== 'string' || !uuidPattern.test(message.sender) || !uuidPattern.test(message.recipient)) continue;
        if (!relationships.has(message.sender)) relationships.set(message.sender, { parentThreadId: message.recipient, messages: [] });
        const relation = relationships.get(message.sender);
        // 한 sender가 서로 다른 부모로 보내면 임의 선택하지 않고 오류로 격리한다.
        if (relation.parentThreadId !== message.recipient) {
          errors.push(`Antigravity worker ${message.sender}의 부모 conversation이 둘 이상입니다.`);
          relationships.delete(message.sender);
          continue;
        }
        // 실제 전송된 content와 timestamp가 있는 메시지만 상태·handoff 후보로 보관한다.
        if (typeof message.content === 'string' && message.content.length > 0 && message.timestamp) {
          relation.messages.push({ id: String(message.id ?? entry.name), timestamp: message.timestamp, content: message.content });
        }
      } catch (error) {
        // 작성 중인 파일은 다음 폴링에서 재시도하고 현재 cursor를 성공 처리하지 않는다.
        delete snapshots[messagePath];
        errors.push(`${messagePath}: ${error.message}`);
      }
    }
  }
  // 파일명 순서와 무관하게 원본 timestamp로 안정 정렬한다.
  for (const relation of relationships.values()) relation.messages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp) || a.id.localeCompare(b.id));
  return relationships;
}

// Antigravity가 저장한 workspace registry에서 현재 프로젝트와 연결된 conversation ID를 찾는다.
async function discoverWorkspaceConversationIds(homeDirectory, snapshots, errors) {
  // CLI와 IDE가 함께 갱신하는 두 JSON cache를 모두 사용한다.
  const cacheRoot = path.join(homeDirectory, '.gemini', 'antigravity-cli', 'cache');
  const metadataPath = path.join(cacheRoot, 'conversation_metadata.json');
  const recentPath = path.join(cacheRoot, 'last_conversations.json');
  const ids = new Set();
  let metadata = null;
  let recent = null;
  for (const [label, sourcePath] of [['metadata', metadataPath], ['recent', recentPath]]) {
    try {
      snapshots[sourcePath] = await sourceFingerprint(sourcePath);
      const parsed = JSON.parse(await readFile(sourcePath, 'utf8'));
      if (label === 'metadata') metadata = parsed;
      else recent = parsed;
    } catch (error) {
      // cache가 설치되지 않은 배포형은 brain·mailbox 판별로 계속 진행한다.
      delete snapshots[sourcePath];
      if (error.code !== 'ENOENT') errors.push(`${sourcePath}: ${error.message}`);
    }
  }
  return { ids, metadata, recent };
}

// 읽은 registry 객체를 현재 workspace와 비교해 ID 집합을 완성한다.
function matchWorkspaceConversationIds(registry, workspaceRoot) {
  const workspace = normalizePathForComparison(workspaceRoot);
  // conversation_metadata는 workspace 절대 경로를 ID에 직접 매핑한다.
  for (const [workspacePath, conversationId] of Object.entries(registry.metadata ?? {})) {
    if (normalizePathForComparison(workspacePath) === workspace && typeof conversationId === 'string') registry.ids.add(conversationId);
  }
  // last_conversations는 conversation별 WorkspaceURIs를 보존한다.
  for (const [conversationId, entry] of Object.entries(registry.recent?.conversations ?? {})) {
    const uris = entry?.summary?.WorkspaceURIs;
    if (!Array.isArray(uris)) continue;
    for (const uri of uris) {
      try {
        if (normalizePathForComparison(fileURLToPath(uri)) === workspace) registry.ids.add(conversationId);
      } catch {
        // file URI가 아닌 값은 workspace 근거로 사용하지 않는다.
      }
    }
  }
  return registry.ids;
}

// stat polling으로 변경된 Antigravity conversation을 식별하고 workspace 이벤트를 추출한다.
export async function collectAntigravityEvents({ workspaceRoot, state, homeDirectory = os.homedir(), roots = defaultAntigravityRoots(homeDirectory), force = false }) {
  // 설치된 brain 후보를 모두 찾는다.
  let candidates;
  try {
    candidates = await discoverConversationFiles(roots);
  } catch (error) {
    return { platform: 'antigravity', status: 'error', events: [], snapshots: {}, errors: [error.message] };
  }
  // transcript가 하나도 없으면 지원되지 않는 환경으로 명시한다.
  if (candidates.length === 0) return { platform: 'antigravity', status: 'unsupported', events: [], snapshots: {}, errors: ['Antigravity brain transcript를 찾지 못했습니다.'] };
  // main/child 관계 판정을 위해 변경 후보의 메타데이터를 먼저 모은다.
  const inspected = [];
  const snapshots = {};
  const errors = [];
  // 부모의 message mailbox는 worker transcript 안 문자열보다 강한 상위/하위 관계 근거다.
  const messageRelationships = await discoverMessageRelationships(candidates, snapshots, errors);
  // 플랫폼 registry의 workspace 매핑은 새 직접 conversation 첫 턴을 잡는 우선 근거다.
  const workspaceRegistry = await discoverWorkspaceConversationIds(homeDirectory, snapshots, errors);
  const registryIds = matchWorkspaceConversationIds(workspaceRegistry, workspaceRoot);
  for (const candidate of candidates) {
    try {
      // 없는 표준 transcript 후보는 조용히 건너뛴다.
      const fingerprint = await sourceFingerprint(candidate.transcriptPath);
      snapshots[candidate.transcriptPath] = fingerprint;
      // 등록 conversation은 다른 파일의 child 관계 판정에 필요하므로 force가 아니어도 변경분만 파싱한다.
      const registered = state.registeredConversations?.antigravity?.includes(candidate.conversationId);
      const related = messageRelationships.has(candidate.conversationId) || [...messageRelationships.values()].some((relation) => relation.parentThreadId === candidate.conversationId);
      if (!force && !registered && !related && state.sources[candidate.transcriptPath] === fingerprint) continue;
      // UTF-8 transcript 전체를 한 conversation 단위로 읽는다.
      const text = await readFile(candidate.transcriptPath, 'utf8');
      let fullText = null;
      if (candidate.transcriptFullPath) {
        try {
          fullText = await readFile(candidate.transcriptFullPath, 'utf8');
        } catch (error) {
          if (error.code !== 'ENOENT') errors.push(`${candidate.transcriptFullPath}: ${error.message}`);
        }
      }
      // workspace 포함 여부와 parent receipt를 검사한다.
      inspected.push(inspectConversation(text, candidate.conversationId, workspaceRoot, fullText));
    } catch (error) {
      // 파일 부재는 discover와 실제 생성 사이 race일 수 있으므로 다음 polling에서 재시도한다.
      delete snapshots[candidate.transcriptPath];
      if (error.code !== 'ENOENT') errors.push(`${candidate.transcriptPath}: ${error.message}`);
    }
  }
  // 이미 등록된 main conversation과 이번에 workspace가 확인된 후보를 합친다.
  const knownIds = new Set(state.registeredConversations?.antigravity ?? []);
  // workspace registry가 명시한 ID는 user turn 수와 무관하게 직접 conversation으로 등록한다.
  for (const conversationId of registryIds) knownIds.add(conversationId);
  for (const info of inspected) {
    // 여러 직접 사용자 턴 또는 자신의 mailbox에 worker 메시지가 있으면 상위 conversation으로 확정한다.
    const receivesWorkerMessages = [...messageRelationships.values()].some((relation) => relation.parentThreadId === info.conversationId);
    if (info.workspaceMatch && (info.userRows.length > 1 || receivesWorkerMessages)) knownIds.add(info.conversationId);
  }
  // 단일 user session 중 known main으로 message를 보낸 conversation을 child로 판정한다.
  const childParent = new Map();
  // 부모 mailbox가 제공한 sender/recipient 관계를 최우선으로 적용한다.
  for (const [childId, relation] of messageRelationships) if (knownIds.has(relation.parentThreadId)) childParent.set(childId, relation.parentThreadId);
  for (const info of inspected) {
    // 장기 상위 세션을 하위로 오인하지 않도록 user input 1건 조건을 둔다.
    if (info.userRows.length !== 1) continue;
    // 알려진 main target 중 첫 실제 parent를 사용한다.
    const parent = info.sentTargets.find((target) => knownIds.has(target));
    // parent가 확인된 경우만 하위 companion을 활성화한다.
    if (parent && !childParent.has(info.conversationId)) childParent.set(info.conversationId, parent);
  }
  // workspace 직접 이벤트와 확인된 child 이벤트를 누적한다.
  const events = [];
  for (const info of inspected) {
    // 확인된 child는 main timeline에서 제외하고 companion으로 변환한다.
    if (childParent.has(info.conversationId)) {
      const childEvents = conversationEvents(info, { isSubagent: true, parentThreadId: childParent.get(info.conversationId) });
      const existingContents = new Set(childEvents.map((event) => event.content));
      const relation = messageRelationships.get(info.conversationId);
      // mailbox에만 있는 진행 보고도 내부 tool 원문 없이 실제 전송 content만 companion에 보존한다.
      for (const message of relation?.messages ?? []) {
        if (existingContents.has(message.content)) continue;
        childEvents.push(createEvent({ provider: 'antigravity', threadId: info.conversationId, sourceEventId: `message-${message.id}`, sourceOrdinal: childEvents.length + 1, occurredAt: message.timestamp, actor: 'assistant', channel: 'subagent_status', speaker: 'Gemini 하위 에이전트 → 부모', content: message.content, destination: 'subagent', parentThreadId: childParent.get(info.conversationId), agentId: info.conversationId, taskName: info.conversationId }));
      }
      events.push(...childEvents);
    }
    // 알려진 main은 직접 user/final만 변환한다.
    else if (knownIds.has(info.conversationId)) events.push(...conversationEvents(info));
  }
  // 성공한 등록 conversation 목록을 상태에 반영할 값으로 반환한다.
  const registeredConversations = [...knownIds].sort();
  // 오류가 있으면 해당 source cursor는 전진하지 않도록 error 상태를 준다.
  return { platform: 'antigravity', status: errors.length ? 'error' : 'ok', events, snapshots, errors, registeredConversations };
}
