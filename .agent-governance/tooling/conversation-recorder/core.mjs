// [역할] 플랫폼 원본 이벤트를 안전한 Chat Markdown과 로컬 receipt 상태로 투영하는 공통 기능을 제공한다.
// [의존성 관계] Codex·Antigravity 어댑터와 conversation-recorder CLI가 이 모듈을 사용한다.
// [변경 시 영향도] 이벤트 ID, 시각, 필터 또는 쓰기 규칙을 바꾸면 fixture와 기존 cursor 호환성을 함께 검증해야 한다.

import { createHash } from 'node:crypto';
import { constants as fsConstants } from 'node:fs';
import { access, mkdir, open, readFile, rename, rm, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';

// 상태 파일 형식이 바뀌면 이전 cursor를 묵시적으로 오독하지 않도록 버전을 고정한다.
export const STATE_VERSION = 1;
// 하위 에이전트 companion 한 조각의 최대 UTF-8 크기를 계획서 기준인 64 KiB로 제한한다.
export const COMPANION_LIMIT_BYTES = 64 * 1024;
// 대화 이벤트 provenance 주석의 고정 형식은 재시작 후 중복 판정 기준으로 사용한다.
export const EVENT_MARKER_PREFIX = '<!-- conversation-event:';

// 운영체제별 구분자와 대소문자 차이를 제거하여 workspace 경로를 비교한다.
export function normalizePathForComparison(value) {
  // 값이 없으면 빈 경로로 처리하여 임의의 현재 경로와 일치하지 않게 한다.
  if (!value) return '';
  // 절대 경로로 만든 뒤 슬래시와 끝 구분자를 정규화한다.
  return path.resolve(String(value)).replaceAll('\\', '/').replace(/\/$/, '').toLowerCase();
}

// 안정적인 event ID와 content hash를 만들기 위해 SHA-256을 대문자 16진수로 반환한다.
export function sha256(value) {
  // 문자열 변환과 UTF-8 해싱을 한 위치에서 고정한다.
  return createHash('sha256').update(String(value), 'utf8').digest('hex').toUpperCase();
}

// 플랫폼의 ISO 시각을 검증하고 Asia/Seoul 고정 오프셋의 날짜·밀리초 헤더로 변환한다.
export function toKstParts(isoTimestamp) {
  // 플랫폼 어댑터가 전달한 실제 시각만 허용하고 파싱 실패를 즉시 오류로 만든다.
  const instant = new Date(isoTimestamp);
  // 잘못된 시각에서 현재 시각을 대신 쓰지 않도록 명시적으로 차단한다.
  if (Number.isNaN(instant.getTime())) throw new Error(`확인할 수 없는 이벤트 시각: ${isoTimestamp}`);
  // 한국은 일광 절약 시간 없이 UTC+9이므로 표시 전용 Date에 9시간을 더한다.
  const kst = new Date(instant.getTime() + 9 * 60 * 60 * 1000);
  // UTC getter를 사용해 호스트 PC timezone 설정과 무관한 KST 구성요소를 얻는다.
  const yyyy = String(kst.getUTCFullYear()).padStart(4, '0');
  const mm = String(kst.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(kst.getUTCDate()).padStart(2, '0');
  const hh = String(kst.getUTCHours()).padStart(2, '0');
  const mi = String(kst.getUTCMinutes()).padStart(2, '0');
  const ss = String(kst.getUTCSeconds()).padStart(2, '0');
  const ms = String(kst.getUTCMilliseconds()).padStart(3, '0');
  // 파일 경로용 날짜와 헤더용 전체 시각을 함께 반환한다.
  return { date: `${yyyy}-${mm}-${dd}`, year: yyyy, month: mm, day: dd, header: `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}.${ms}`, epochMs: instant.getTime() };
}

// Markdown 구조를 유지하면서 플랫폼별 줄바꿈만 LF로 통일한다.
export function normalizeNewlines(value) {
  // null과 undefined는 기록 가능한 빈 문자열로 바꾸고 CRLF/CR만 LF로 바꾼다.
  return String(value ?? '').replaceAll('\r\n', '\n').replaceAll('\r', '\n');
}

// Rule 6-1-4에 따라 대표적인 비밀값을 원본 Chat에 남기기 전에 치환한다.
export function redactSecrets(value) {
  // 원문 구조를 보존하기 위해 줄바꿈 외의 일반 텍스트 정규화는 수행하지 않는다.
  let result = normalizeNewlines(value);
  // 여러 줄 개인키 전체를 종류와 무관하게 하나의 자리표시자로 치환한다.
  result = result.replace(/-----BEGIN [^-\n]*PRIVATE KEY-----[\s\S]*?-----END [^-\n]*PRIVATE KEY-----/gi, '<개인키>');
  // Authorization Bearer 토큰은 헤더 이름을 유지하고 실제 토큰만 치환한다.
  result = result.replace(/(authorization\s*:\s*bearer\s+)[^\s`"']+/gi, '$1<토큰>');
  // 일반 Bearer 표현도 토큰 본문을 기록하지 않는다.
  result = result.replace(/\b(bearer\s+)[A-Za-z0-9._~+\/-]{12,}/gi, '$1<토큰>');
  // password, secret, token, api key 형태의 key-value에서 값 부분을 치환한다.
  result = result.replace(/\b(password|passwd|secret|api[_ -]?key|access[_ -]?token|refresh[_ -]?token)\b(\s*[:=]\s*)([^\s,;]+)/gi, (_match, key, separator) => `${key}${separator}<비밀값>`);
  // PEM 이외의 길고 전형적인 JWT 세 구간도 토큰으로 치환한다.
  result = result.replace(/\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g, '<토큰>');
  // 전자우편 주소는 로컬 부분과 도메인을 모두 보존하지 않는다.
  result = result.replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, '<이메일>');
  // 대한민국 휴대전화 번호의 구분자 유무를 모두 개인정보 자리표시자로 바꾼다.
  result = result.replace(/(?<!\d)01[016789][ -]?\d{3,4}[ -]?\d{4}(?!\d)/g, '<전화번호>');
  // 주민등록번호처럼 6자리-7자리 형태인 값은 유효성 추정 없이 기록 전에 치환한다.
  result = result.replace(/(?<!\d)\d{6}-[1-8]\d{6}(?!\d)/g, '<개인식별번호>');
  // 치환된 텍스트를 그대로 반환한다.
  return result;
}

// 어댑터 출력에서 안정적인 provenance와 KST 시각을 가진 공통 이벤트를 만든다.
export function createEvent(input) {
  // provider·thread·source 식별자가 없으면 정확히 한 번 보장을 만들 수 없으므로 차단한다.
  if (!input.provider || !input.threadId || input.sourceEventId === undefined || !input.occurredAt) throw new Error('대화 이벤트 식별자 또는 시각이 누락되었습니다.');
  // 플랫폼이 확인한 시각을 KST 표시 정보로 변환한다.
  const time = toKstParts(input.occurredAt);
  // 비밀 치환을 적용하되 앞뒤 공백은 사용자 원문이므로 제거하지 않는다.
  const content = redactSecrets(input.content ?? '');
  // 이벤트 ID는 파일 경로나 원문을 노출하지 않고 안정적인 원본 식별자만 해싱한다.
  const eventId = sha256(`${input.provider}\u0000${input.threadId}\u0000${input.sourceEventId}`);
  // projector가 사용할 필드를 고정된 형태로 반환한다.
  return {
    provider: input.provider,
    threadId: String(input.threadId),
    sourceEventId: String(input.sourceEventId),
    sourceOrdinal: Number(input.sourceOrdinal ?? 0),
    occurredAt: input.occurredAt,
    time,
    actor: input.actor,
    channel: input.channel,
    speaker: input.speaker,
    content,
    contentHash: sha256(content),
    eventId,
    destination: input.destination ?? 'main',
    parentThreadId: input.parentThreadId ? String(input.parentThreadId) : '',
    agentId: input.agentId ? String(input.agentId) : '',
    agentName: input.agentName ? String(input.agentName) : '',
    taskName: input.taskName ? String(input.taskName) : '',
  };
}

// JSONL 한 줄 오류가 전체 정상 세션을 오염시키지 않도록 줄 번호와 함께 엄격히 파싱한다.
export function parseJsonLines(text, sourceLabel = 'JSONL') {
  // 플랫폼 로그의 실제 줄 번호를 source ordinal로 사용할 수 있게 보존한다.
  const rows = [];
  // 마지막 개행 뒤의 빈 줄은 정상으로 허용한다.
  normalizeNewlines(text).split('\n').forEach((line, index) => {
    // 공백 줄은 이벤트가 아니므로 건너뛴다.
    if (!line.trim()) return;
    // 손상된 JSON은 cursor를 전진시키지 않도록 예외로 처리한다.
    try {
      rows.push({ value: JSON.parse(line), lineNumber: index + 1 });
    } catch (error) {
      throw new Error(`${sourceLabel} ${index + 1}행 JSON 파싱 실패: ${error.message}`);
    }
  });
  // 성공적으로 읽은 전체 행을 반환한다.
  return rows;
}

// Codex response_item content 배열에서 사용자에게 표시된 텍스트만 순서대로 결합한다.
export function extractCodexMessageText(contentItems) {
  // 메시지 content가 배열이 아니면 표시 텍스트가 없는 것으로 처리한다.
  if (!Array.isArray(contentItems)) return '';
  // input_text와 output_text만 허용하고 이미지·도구 payload는 제외한다.
  return contentItems.map((item) => item?.text ?? item?.input_text ?? item?.output_text ?? '').join('');
}

// 상태 파일이 없을 때 안전한 빈 상태를 제공한다.
export function emptyState() {
  // receipts는 event별 완료 증명, sources는 stat polling 기준, health는 사용자 상태 출력에 사용한다.
  return { version: STATE_VERSION, receipts: {}, sources: {}, health: {}, registeredConversations: { antigravity: [] }, updatedAt: null };
}

// 상태 파일을 읽되 알 수 없는 버전이나 손상 JSON을 조용히 초기화하지 않는다.
export async function readState(statePath) {
  // 최초 실행은 정상적인 빈 상태로 시작한다.
  try {
    const parsed = JSON.parse(await readFile(statePath, 'utf8'));
    // 상태 버전이 다르면 cursor 오독을 막기 위해 실패시킨다.
    if (parsed.version !== STATE_VERSION) throw new Error(`지원하지 않는 recorder state 버전: ${parsed.version}`);
    // 누락된 선택 필드는 이전 같은 버전 상태와 호환되도록 보완한다.
    parsed.receipts ??= {};
    parsed.sources ??= {};
    parsed.health ??= {};
    parsed.registeredConversations ??= { antigravity: [] };
    // 검증된 상태를 반환한다.
    return parsed;
  } catch (error) {
    // 파일 부재만 최초 실행으로 인정한다.
    if (error.code === 'ENOENT') return emptyState();
    // 손상 상태는 중복 위험이 있으므로 호출자에게 전달한다.
    throw error;
  }
}

// 임시 파일 fsync와 rename을 사용해 완성되지 않은 JSON이나 Markdown 노출을 막는다.
export async function writeFileAtomic(targetPath, content) {
  // 대상 디렉터리는 프로젝트 내부 검증 후 호출되며 필요한 경우 생성한다.
  await mkdir(path.dirname(targetPath), { recursive: true });
  // 같은 디렉터리의 고유 임시 파일을 사용해 rename의 파일시스템 원자성을 확보한다.
  const temporaryPath = `${targetPath}.tmp-${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  // UTF-8 바이트를 명시하여 Windows 기본 인코딩 영향을 제거한다.
  const handle = await open(temporaryPath, 'wx');
  try {
    // 완성된 본문 전체를 한 번에 기록한다.
    await handle.writeFile(content, { encoding: 'utf8' });
    // 디스크 버퍼까지 내려간 뒤 파일을 공개한다.
    await handle.sync();
  } finally {
    // 성공·실패와 무관하게 파일 핸들을 닫는다.
    await handle.close();
  }
  try {
    // 같은 볼륨의 rename으로 기존 파일을 원자적으로 교체한다.
    await rename(temporaryPath, targetPath);
  } catch (error) {
    // Windows에서 기존 대상 교체가 거부되면 이전 파일을 삭제하지 않고 실패한다.
    await rm(temporaryPath, { force: true });
    throw error;
  }
}

// PID가 실제로 살아 있는지 확인하여 stale lock을 안전하게 구분한다.
export function isProcessAlive(pid) {
  // 유효하지 않은 PID는 활성 소유자로 인정하지 않는다.
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    // signal 0은 프로세스를 종료하지 않고 존재·접근 가능성만 확인한다.
    process.kill(pid, 0);
    // 오류가 없으면 프로세스가 살아 있다.
    return true;
  } catch (error) {
    // 권한 오류는 존재하는 다른 프로세스일 수 있으므로 활성으로 취급한다.
    if (error.code === 'EPERM') return true;
    // ESRCH 등은 stale PID로 판단한다.
    return false;
  }
}

// 짧은 임계구역에 프로젝트 단일 writer lock을 적용한다.
export async function withWriterLock(lockPath, callback, { waitMs = 0, pollMs = 50 } = {}) {
  // 상태 디렉터리를 lock 생성 전에 준비한다.
  await mkdir(path.dirname(lockPath), { recursive: true });
  // preflight와 watcher 충돌은 제한 시간 동안 기다리고 stale lock은 회수한다.
  const deadline = Date.now() + waitMs;
  while (true) {
    try {
      // wx 플래그는 이미 lock이 있으면 원자적으로 실패한다.
      const handle = await open(lockPath, 'wx');
      try {
        // PID와 시각을 남겨 stale 판정 근거를 제공한다.
        await handle.writeFile(JSON.stringify({ pid: process.pid, createdAt: new Date().toISOString() }), 'utf8');
        // 사용자의 writer 작업을 lock 안에서 실행한다.
        return await callback();
      } finally {
        // 파일 핸들을 먼저 닫고 자신이 만든 lock을 제거한다.
        await handle.close();
        await rm(lockPath, { force: true });
      }
    } catch (error) {
      // lock 충돌 이외의 파일 오류는 즉시 전달한다.
      if (error.code !== 'EEXIST') throw error;
      // 기존 lock의 PID를 읽어 실제 소유자가 살아 있는지 확인한다.
      let lockInfo;
      try {
        lockInfo = JSON.parse(await readFile(lockPath, 'utf8'));
      } catch {
        // 손상 lock은 안전한 소유 여부를 증명할 수 없으므로 현재 시도에서는 회수하지 않는다.
        throw new Error(`대화 기록 lock을 판독할 수 없습니다: ${lockPath}`);
      }
      // 살아 있는 프로세스의 lock은 빼앗지 않고 호출자가 허용한 시간만 기다린다.
      if (isProcessAlive(Number(lockInfo.pid))) {
        if (Date.now() < deadline) {
          await new Promise((resolve) => setTimeout(resolve, pollMs));
          continue;
        }
        throw new Error(`다른 대화 기록 writer가 실행 중입니다. PID=${lockInfo.pid}`);
      }
      // 죽은 PID가 확정된 stale lock만 제거하고 한 번 재시도한다.
      await rm(lockPath, { force: true });
    }
  }
}

// 대상 경로가 반드시 workspace의 Chat 하위인지 확인해 경로 이탈을 차단한다.
export function assertInsideChat(chatRoot, candidatePath) {
  // 두 경로를 절대 경로로 변환한다.
  const root = path.resolve(chatRoot);
  const candidate = path.resolve(candidatePath);
  // path.relative가 상위 이동이나 절대 경로를 반환하면 Chat 밖이다.
  const relative = path.relative(root, candidate);
  // Chat 루트 자신 또는 그 하위만 허용한다.
  if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error(`Chat 경로 이탈이 차단되었습니다: ${candidate}`);
  // 검증된 절대 경로를 반환한다.
  return candidate;
}

// 기존 Markdown에서 provenance와 동일 헤더·본문을 찾아 재처리 중복을 막는다.
export function eventAlreadyRecorded(markdown, event) {
  // 새 형식 provenance가 있으면 content와 무관하게 같은 원본 event로 확정한다.
  if (markdown.includes(`${EVENT_MARKER_PREFIX} ${event.eventId} -->`)) return { matched: true, mode: 'provenance' };
  // 복원된 기존 파일에는 provenance가 없으므로 정확한 헤더와 원문 블록도 호환 판정한다.
  const header = `## ${event.speaker} ${event.time.header}\n\n`;
  // 해당 헤더의 모든 위치를 검사하여 동률 시각의 다른 발언과 구분한다.
  let searchFrom = 0;
  while (true) {
    // 다음 같은 헤더를 찾는다.
    const index = markdown.indexOf(header, searchFrom);
    // 더 없으면 미기록으로 판정한다.
    if (index < 0) break;
    // 다음 대화 헤더 또는 파일 끝까지를 현재 블록 본문으로 본다.
    const bodyStart = index + header.length;
    const nextHeader = markdown.slice(bodyStart).search(/\n(?:<!-- conversation-event: [A-F0-9]{64} -->\n)?## [^\n]+ \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\n/);
    // 다음 헤더가 없으면 끝까지, 있으면 바로 전까지 읽는다.
    const bodyEnd = nextHeader < 0 ? markdown.length : bodyStart + nextHeader;
    // 블록 사이 구분 개행만 제거하고 원문을 비교한다.
    const existingBody = markdown.slice(bodyStart, bodyEnd).replace(/\n+$/, '');
    // 치환 후 원문이 완전히 같으면 legacy 기록으로 인정한다.
    if (existingBody === event.content.replace(/\n+$/, '')) return { matched: true, mode: 'legacy-exact' };
    // 같은 시각의 다음 헤더를 계속 검사한다.
    searchFrom = bodyStart;
  }
  // provenance와 legacy exact 모두 없으면 새 기록이 필요하다.
  return { matched: false, mode: 'none' };
}

// 한 이벤트를 provenance가 붙은 표준 Markdown 블록으로 렌더링한다.
export function renderEventBlock(event) {
  // 원문 끝의 개행 수와 무관하게 블록 사이에는 정확히 한 빈 줄을 둔다.
  const body = event.content.replace(/\n+$/, '');
  // 숨은 provenance는 사용자 원문 밖에 배치한다.
  return `${EVENT_MARKER_PREFIX} ${event.eventId} -->\n## ${event.speaker} ${event.time.header}\n\n${body}\n`;
}

// 기존 시간순 블록을 손대지 않고 새 블록의 안정적인 삽입 위치를 계산한다.
export function insertEventBlock(markdown, event) {
  // 기존 파일과 새 블록을 LF 기준으로 처리한다.
  const current = normalizeNewlines(markdown);
  // 모든 대화 헤더의 시각과 시작 위치를 수집한다.
  const headerPattern = /^## [^\n]+ (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})$/gm;
  const headers = [...current.matchAll(headerPattern)];
  // 더 늦은 첫 헤더 앞에 삽입하고 같은 시각 헤더 뒤에는 유지한다.
  const next = headers.find((match) => match[1] > event.time.header);
  // provenance가 다음 헤더 바로 앞에 있으면 그 표식까지 함께 뒤로 보낸다.
  let insertAt = next ? next.index : current.length;
  if (next) {
    // 직전 줄이 provenance인지 제한된 범위에서 확인한다.
    const prefix = current.slice(0, insertAt);
    const markerMatch = prefix.match(/<!-- conversation-event: [A-F0-9]{64} -->\n$/);
    // 다음 블록의 provenance 앞을 실제 삽입 위치로 사용한다.
    if (markerMatch) insertAt -= markerMatch[0].length;
  }
  // 파일 끝 append와 중간 삽입 모두 블록 사이 빈 줄을 보장한다.
  const before = current.slice(0, insertAt).replace(/\n*$/, '');
  const after = current.slice(insertAt).replace(/^\n*/, '');
  const block = renderEventBlock(event).replace(/\n+$/, '');
  // 앞이나 뒤가 비어 있어도 불필요한 선행 공백을 만들지 않는다.
  return [before, block, after].filter((part) => part.length > 0).join('\n\n') + '\n';
}

// 긴 문자열도 UTF-8 문자 경계를 보존하면서 지정한 바이트 이하로 나눈다.
function splitUtf8Text(text, limitBytes) {
  // JavaScript의 for-of는 surrogate pair를 한 문자로 순회하므로 UTF-8 문자를 깨지 않는다.
  const chunks = [];
  let current = '';
  let currentBytes = 0;
  for (const character of text) {
    // 각 코드 포인트의 실제 UTF-8 크기를 계산한다.
    const characterBytes = Buffer.byteLength(character, 'utf8');
    // 현재 조각에 더할 수 없으면 먼저 확정한다.
    if (current && currentBytes + characterBytes > limitBytes) {
      chunks.push(current);
      current = '';
      currentBytes = 0;
    }
    // 한 코드 포인트는 최대 4바이트이므로 정상 제한값에서는 항상 들어간다.
    current += character;
    currentBytes += characterBytes;
  }
  // 마지막 조각을 빠뜨리지 않는다.
  if (current) chunks.push(current);
  return chunks;
}

// 하위 에이전트 원문 블록들을 UTF-8 문자를 보존하며 64 KiB 이하 조각에 나눈다.
export function splitCompanionBlocks(blocks, limitBytes = COMPANION_LIMIT_BYTES) {
  // 코드 포인트 하나도 담을 수 없는 제한은 호출 오류로 처리한다.
  if (!Number.isInteger(limitBytes) || limitBytes < 4) throw new Error('companion 분할 크기는 4바이트 이상의 정수여야 합니다.');
  // 렌더링된 블록 사이의 기존 한 줄 구분만 추가해 전체 원문 스트림을 확정한다.
  const transcript = blocks.join('\n');
  // 전체가 제한 안이면 Markdown 블록 경계를 그대로 유지한다.
  if (Buffer.byteLength(transcript, 'utf8') <= limitBytes) return transcript ? [transcript] : [];
  // 큰 transcript는 문자 경계에서 나누며 parts를 이어 붙이면 원본 스트림과 정확히 같아야 한다.
  return splitUtf8Text(transcript, limitBytes);
}

// 대상 Markdown을 읽는 동안 다른 편집이 있었는지 fingerprint로 확인한다.
async function readStableMarkdown(targetPath) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    let before = null;
    let markdown = '';
    try {
      before = await sourceFingerprint(targetPath);
      markdown = await readFile(targetPath, 'utf8');
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    let after = null;
    try { after = await sourceFingerprint(targetPath); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    // 읽기 전후 파일 상태가 같을 때만 안정 snapshot으로 사용한다.
    if (before === after) return { markdown, fingerprint: after };
  }
  throw new Error(`동시 수정 중인 Chat 파일을 안정적으로 읽지 못했습니다: ${targetPath}`);
}

// 프로젝트 Chat에 직접 이벤트와 하위 에이전트 companion을 한 writer 임계구역에서 반영한다.
export async function projectEvents({ workspaceRoot, chatRoot = path.join(workspaceRoot, 'Chat'), state, events, dryRun = false, trustReceipts = true }) {
  // 입력 이벤트를 source 시각, provider, thread, ordinal 순으로 결정적으로 정렬한다.
  const ordered = [...events].sort((a, b) => a.time.epochMs - b.time.epochMs || a.provider.localeCompare(b.provider) || a.threadId.localeCompare(b.threadId) || a.sourceOrdinal - b.sourceOrdinal);
  // 하위 에이전트 상세 이벤트와 주 대화 이벤트를 분리한다.
  const subagentEvents = ordered.filter((event) => event.destination === 'subagent');
  const mainEvents = ordered.filter((event) => event.destination === 'main');
  // 실행 결과 통계를 호출자와 status에 제공한다.
  const summary = { considered: ordered.length, written: 0, existing: 0, companionFiles: 0, planned: [] };
  // 하위 에이전트 thread별 전체 원문을 먼저 companion으로 만든다.
  const groups = new Map();
  for (const event of subagentEvents) {
    // provider와 thread 조합은 다른 플랫폼 UUID 충돌을 막는다.
    const key = `${event.provider}:${event.threadId}`;
    // 같은 하위 작업의 이벤트 배열을 준비한다.
    if (!groups.has(key)) groups.set(key, []);
    // 정렬된 이벤트를 그대로 추가한다.
    groups.get(key).push(event);
  }
  // companion 파일과 완료 receipt를 각 하위 작업별로 생성한다.
  for (const [key, group] of groups) {
    // task·상태·handoff 원문을 별도 speaker 헤더로 렌더링한다.
    const blocks = group.map((event) => renderEventBlock(event));
    // 64 KiB를 넘으면 블록 경계에서 순번 조각으로 나눈다.
    const parts = splitCompanionBlocks(blocks);
    // 첫 이벤트의 날짜와 식별자를 안전한 파일명으로 사용한다.
    const first = group[0];
    const safeAgent = (first.agentId || first.threadId).replace(/[^A-Za-z0-9._-]/g, '_');
    // 모든 조각 경로를 먼저 결정한다.
    const relativePaths = parts.map((_part, index) => path.posix.join('Subagents', first.time.year, first.time.month, first.time.day, `${first.provider}_${safeAgent}_part-${String(index + 1).padStart(3, '0')}.md`));
    // dry-run이 아니면 companion 각 조각을 원자적으로 쓴다.
    const companionReceiptComplete = trustReceipts && group.every((event) => state.receipts[event.eventId]?.contentHash === event.contentHash);
    if (!dryRun && !companionReceiptComplete) {
      for (let index = 0; index < parts.length; index += 1) {
        // Chat 밖으로 나갈 수 없는 절대 경로를 검증한다.
        const target = assertInsideChat(chatRoot, path.join(chatRoot, relativePaths[index]));
        // 파생 transcript는 전체 source group에서 재생성하므로 원자적 교체한다.
        await writeFileAtomic(target, parts[index]);
      }
      // 하위 원본 이벤트는 전체 순번 파일 집합에 속하므로 첫 경로와 조각 수를 receipt에 남긴다.
      for (const event of group) state.receipts[event.eventId] = { file: relativePaths[0], parts: relativePaths.length, contentHash: event.contentHash, recordedAt: new Date().toISOString(), mode: 'companion' };
    }
    // 상세 파일 수를 결과에 반영한다.
    summary.companionFiles += parts.length;
    // 하위 작업 마지막 이벤트 시각에 주 대화 receipt를 만든다.
    const last = group[group.length - 1];
    // 날짜 파일 위치를 기준으로 계산한 상대 링크를 사용해 실제 companion 경로로 이동하게 한다.
    const mainFileDirectory = path.join(chatRoot, last.time.year, last.time.month);
    const links = relativePaths.map((relative, index) => {
      const target = path.join(chatRoot, relative);
      return `[상세 ${index + 1}](${path.relative(mainFileDirectory, target).replaceAll('\\', '/')})`;
    }).join(', ');
    // task 원문의 첫 줄만 메타데이터로 사용하고 전체 원문은 companion에 둔다.
    const task = group.find((event) => event.channel === 'subagent_task')?.content.split('\n')[0] || first.taskName || first.agentId || first.threadId;
    // receipt 자체도 안정적인 가상 source ID로 중복을 방지한다.
    const providerLabel = first.provider === 'codex' ? 'Codex' : first.provider === 'antigravity' ? 'Gemini' : first.provider;
    mainEvents.push(createEvent({ provider: first.provider, threadId: first.parentThreadId || `parent-of-${first.threadId}`, sourceEventId: `subagent-receipt:${first.threadId}`, sourceOrdinal: last.sourceOrdinal, occurredAt: last.occurredAt, actor: 'subagent', channel: 'subagent_receipt', speaker: `${providerLabel} 하위 에이전트`, content: `- 작업 ID: \`${first.agentId || first.threadId}\`\n- 작업: ${task}\n- 상태: ${last.channel === 'subagent_final' ? '완료' : '진행 기록'}\n- 상세 기록 (${relativePaths.length}개): ${links}` }));
    // key 사용은 그룹의 결정적 순회를 명시하기 위한 것이므로 lint상 미사용을 피한다.
    void key;
  }
  // companion에서 만든 receipt까지 다시 전체 안정 순서로 정렬한다.
  mainEvents.sort((a, b) => a.time.epochMs - b.time.epochMs || a.provider.localeCompare(b.provider) || a.threadId.localeCompare(b.threadId) || a.sourceOrdinal - b.sourceOrdinal);
  // 각 주 대화 이벤트를 날짜 파일에 정확히 한 번 반영한다.
  for (const event of mainEvents) {
    // 빈 원문은 사용자에게 표시된 메시지가 아니므로 건너뛴다.
    if (!event.content) continue;
    // 정상 경로에서는 Chat 반영 뒤 저장된 receipt로 과거 이벤트의 반복 파일 읽기를 줄인다.
    if (trustReceipts && state.receipts[event.eventId]?.contentHash === event.contentHash) {
      summary.existing += 1;
      continue;
    }
    // 날짜별 표준 경로를 만들고 Chat 하위임을 확인한다.
    const relativePath = path.posix.join(event.time.year, event.time.month, `${event.time.day}.md`);
    const targetPath = assertInsideChat(chatRoot, path.join(chatRoot, relativePath));
    // 파일이 없으면 빈 Markdown으로 시작한다.
    let snapshot = await readStableMarkdown(targetPath);
    let markdown = snapshot.markdown;
    // provenance 또는 legacy exact 기록 여부를 확인한다.
    const existing = eventAlreadyRecorded(normalizeNewlines(markdown), event);
    if (existing.matched) {
      // 이미 존재하는 이벤트는 쓰지 않고 receipt만 복구할 수 있다.
      summary.existing += 1;
      if (!dryRun) state.receipts[event.eventId] = { file: relativePath, contentHash: event.contentHash, recordedAt: new Date().toISOString(), mode: existing.mode };
      continue;
    }
    // dry-run에는 변경 예정 경로와 ID만 보고하고 파일·state를 쓰지 않는다.
    summary.planned.push({ eventId: event.eventId, file: relativePath, speaker: event.speaker, timestamp: event.time.header });
    if (dryRun) continue;
    // 기존 시간순을 유지하는 새 전체 문서를 계산한다.
    let revised = insertEventBlock(markdown, event);
    // 계산 뒤 수동 편집이 끼어들었으면 최신 파일을 다시 읽고 블록을 재계산한다.
    let latestFingerprint = null;
    try { latestFingerprint = await sourceFingerprint(targetPath); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (latestFingerprint !== snapshot.fingerprint) {
      snapshot = await readStableMarkdown(targetPath);
      markdown = snapshot.markdown;
      const latestExisting = eventAlreadyRecorded(normalizeNewlines(markdown), event);
      if (latestExisting.matched) {
        summary.existing += 1;
        state.receipts[event.eventId] = { file: relativePath, contentHash: event.contentHash, recordedAt: new Date().toISOString(), mode: latestExisting.mode };
        continue;
      }
      revised = insertEventBlock(markdown, event);
    }
    // UTF-8 임시 파일과 rename으로 원자적으로 교체한다.
    await writeFileAtomic(targetPath, revised);
    // 실제 파일 반영 후에만 receipt를 만든다.
    state.receipts[event.eventId] = { file: relativePath, contentHash: event.contentHash, recordedAt: new Date().toISOString(), mode: 'provenance' };
    // 성공 통계를 증가시킨다.
    summary.written += 1;
  }
  // 호출자가 상태와 보고서에 사용할 결과를 반환한다.
  return summary;
}

// 상태 파일을 Chat 내부에 원자적으로 저장한다.
export async function writeState(statePath, state) {
  // 마지막 정상 갱신 시각을 상태에 남긴다.
  state.updatedAt = new Date().toISOString();
  // 사람이 검사할 수 있도록 들여쓴 UTF-8 JSON으로 기록한다.
  await writeFileAtomic(statePath, `${JSON.stringify(state, null, 2)}\n`);
}

// 테스트와 status가 파일 존재 여부를 예외 없이 확인할 수 있게 한다.
export async function pathExists(candidatePath) {
  try {
    // 읽기 가능성까지 확인하여 단순 directory entry와 구분한다.
    await access(candidatePath, fsConstants.F_OK);
    // 접근 가능하면 true다.
    return true;
  } catch {
    // 부재 또는 접근 불가는 false로 반환한다.
    return false;
  }
}

// stat polling 비교용 fingerprint를 만든다.
export async function sourceFingerprint(sourcePath) {
  // 크기와 mtime을 함께 사용해 일반 append와 교체를 감지한다.
  const info = await stat(sourcePath);
  // 정밀도 차이를 피하기 위해 mtimeMs를 정수 문자열로 저장한다.
  return `${info.size}:${Math.trunc(info.mtimeMs)}`;
}
