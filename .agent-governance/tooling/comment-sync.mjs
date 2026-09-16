#!/usr/bin/env node
// [역할] Mini-Server의 명시적 EN/KO 추적 주석과 실제 소스 변경을 검사합니다.
// [의존성 관계] Node.js 표준 모듈만 사용하며 config/state JSON과 프로젝트 소스를 읽습니다.
// [변경 시 영향도] parser 규칙 변경은 Gemini 감사 범위와 baseline 판정에 직접 영향을 줍니다.
import fs from 'node:fs'; // 파일과 baseline을 읽고 씁니다.
import path from 'node:path'; // OS 독립 경로를 정규화합니다.
import crypto from 'node:crypto'; // 주석/소스 SHA-256을 계산합니다.
import { rawBlocks, cleanBody, trackedParts } from './comment-format.mjs';
import { fileURLToPath } from 'node:url'; // 기본 프로젝트 루트를 계산합니다.

const here = path.dirname(fileURLToPath(import.meta.url)); // 현재 후보 도구 위치입니다.
const defaultRoot = path.resolve(here, '..', '..'); // Staging 기준 프로젝트 루트입니다.
const args = process.argv.slice(2); // CLI 인자를 보존합니다.
const command = args.find((value) => !value.startsWith('--')) ?? 'check'; // 기본 명령은 check입니다.
const rootArg = args.find((value) => value.startsWith('--root=')); // fixture용 루트 재정의를 찾습니다.
const root = path.resolve(rootArg ? rootArg.slice(7) : defaultRoot); // 절대 루트로 정규화합니다.
const configArg = args.find((value) => value.startsWith('--config=')); // 설정 경로 재정의를 찾습니다.
const stateArg = args.find((value) => value.startsWith('--state=')); // 상태 경로 재정의를 찾습니다.
const configPath = path.resolve(root, configArg ? configArg.slice(9) : '.agent-governance/comment-sync/config.json'); // 설정 위치입니다.
const statePath = path.resolve(root, stateArg ? stateArg.slice(8) : '.agent-governance/comment-sync/state.json'); // baseline 위치입니다.

function sha(text) { // UTF-8 문자열을 안정적인 SHA-256으로 변환합니다.
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex'); // hex digest를 반환합니다.
}
function rel(file) { // 보고용 경로를 프로젝트 상대 POSIX 형태로 바꿉니다.
  return path.relative(root, file).replaceAll('\\', '/'); // 플랫폼 차이를 제거합니다.
}
function loadJson(file, fallback = null) { // JSON 파일을 명시적으로 읽습니다.
  if (!fs.existsSync(file)) return fallback; // 선택 상태 파일은 없을 수 있습니다.
  return JSON.parse(fs.readFileSync(file, 'utf8')); // 파싱 실패는 fail-closed 예외가 됩니다.
}
function walk(entry, extensions) { // 설정된 파일/디렉터리만 재귀 탐색합니다.
  if (!fs.existsSync(entry)) throw new Error(`CONFIG-ERROR: missing root ${rel(entry)}`);
  const relative = path.relative(fs.realpathSync(root), fs.realpathSync(entry));
  if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('CONFIG-ERROR: root escapes workspace');
  const stat = fs.statSync(entry); // 파일 종류를 확인합니다.
  if (stat.isFile()) return extensions.includes(path.extname(entry).toLowerCase()) ? [entry] : []; // 허용 확장자만 반환합니다.
  return fs.readdirSync(entry, { withFileTypes: true }).flatMap((item) => { // 하위 항목을 순회합니다.
    const full = path.join(entry, item.name); // 실제 하위 경로입니다.
    if (item.isDirectory()) return walk(full, extensions); // 디렉터리는 재귀합니다.
    return item.isFile() && extensions.includes(path.extname(item.name).toLowerCase()) ? [full] : []; // 소스 파일만 포함합니다.
  });
}
function parseFile(file) { // 한 파일의 추적 블록과 source 범위를 계산합니다.
  const text = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n'); // 텍스트와 줄바꿈을 정규화합니다.
  const extension = path.extname(file).toLowerCase(); // 언어 판정에 사용합니다.
  const tracked = rawBlocks(text, extension).map(block => ({ ...block, part: trackedParts(block.raw, extension) })).filter(block => block.part);
  return tracked.map((block, index) => {
    const { id, enRev, koRev, enText, koText } = block.part;
    const nextStart = tracked[index + 1]?.start ?? text.length; // 다음 추적 블록 전까지를 source 범위로 잡습니다.
    const sourceText = text.slice(block.end, nextStart).trim(); // 실제 실행/템플릿 영역을 보수적으로 포함합니다.
    const line = text.slice(0, block.start).split('\n').length; // 1-based 시작 행을 계산합니다.
    return { // baseline과 보고에 필요한 값만 노출합니다.
      id, file: rel(file), line, language: extension, // 위치와 언어입니다.
      enRev, koRev, // revision입니다.
      enText, koText, enHash: sha(enText), koHash: sha(koText), sourceHash: sha(sourceText), // 무결성 hash입니다.
    };
  });
}
function inventoryFiles(config) { // 설정된 root들에서 지원 소스를 수집합니다.
  if (config.schema_version !== 1 || !Array.isArray(config.roots) || !config.roots.every(p => typeof p === 'string' && p.trim())) throw new Error('CONFIG-ERROR: invalid schema/roots');
  const extensions = config.extensions ?? ['.py', '.js', '.mjs', '.html'];
  if (!Array.isArray(extensions) || !extensions.length || extensions.some(ext => !['.py', '.js', '.mjs', '.html'].includes(ext))) throw new Error('CONFIG-ERROR: unsupported extensions'); // 기본 지원 확장자입니다.
  return [...new Set((config.roots ?? []).flatMap((entry) => walk(path.resolve(root, entry), extensions)))].sort(); // 중복 없이 정렬합니다.
}
function collect(config) { // 전체 추적 블록을 하나의 배열로 모읍니다.
  return inventoryFiles(config).flatMap(parseFile); // 파일별 parser 결과를 합칩니다.
}
function duplicateIds(comments) { // 동일 ID의 중복 사용을 탐지합니다.
  const seen = new Map(); // 최초 위치를 보관합니다.
  const duplicates = []; // 중복 쌍을 반환합니다.
  for (const comment of comments) { // 모든 추적 블록을 검사합니다.
    if (seen.has(comment.id)) duplicates.push([seen.get(comment.id), comment]); // 두 번째부터 문제로 기록합니다.
    else seen.set(comment.id, comment); // 최초 블록은 기준 위치가 됩니다.
  }
  return duplicates; // 호출자가 상세 메시지를 구성합니다.
}
function hasLabel(text, label) {
  const lines = text.split('\n').filter(line => line.startsWith(label));
  return lines.length === 1 && lines[0].slice(label.length).trim().length > 0;
}
function hasEnMeta(comment) { // 영문 canonical 3대 메타 필드를 확인합니다.
  return ['[Role]', '[Dependencies]', '[Impact]'].every((label) => hasLabel(comment.enText, label)); // 신규 EN-only 인계도 검증할 수 있습니다.
}
function hasKoMeta(comment) { // 한국어 감사본 3대 메타 필드를 확인합니다.
  return ['[역할]', '[의존성 관계]', '[변경 시 영향도]'].every((label) => hasLabel(comment.koText, label)); // KO 블록이 있을 때만 호출합니다.
}
function hasRequiredMeta(comment) { // baseline 승인에는 EN/KO 양쪽 메타가 모두 필요합니다.
  return hasEnMeta(comment) && hasKoMeta(comment); // 감사 완료 상태의 엄격한 조건입니다.
}
function loadState() { // 승인된 baseline을 읽습니다.
  const state = loadJson(statePath, { schema_version: 1, accepted_at: null, comments: {} });
  if (state.schema_version !== 1 || !state.comments || typeof state.comments !== 'object' || Array.isArray(state.comments)) throw new Error('STATE-ERROR: invalid schema');
  for (const [id, entry] of Object.entries(state.comments)) {
    if (!/^[A-Z0-9][A-Z0-9_.-]*$/.test(id) || !entry || typeof entry.file !== 'string'
      || !Number.isSafeInteger(entry.en_rev) || entry.en_rev < 1 || entry.en_rev !== entry.ko_rev
      || !['en_hash', 'ko_hash', 'source_hash'].every(key => /^[a-f0-9]{64}$/.test(entry[key] ?? ''))) throw new Error(`STATE-ERROR: invalid entry ${id}`);
  }
  return state; // 최초 도입 시 빈 상태를 허용합니다.
}
function issue(type, comment, detail = '') { // 사람이 읽을 수 있는 일관된 진단 문자열을 만듭니다.
  const where = comment ? `${comment.file}:${comment.line} ${comment.id}` : ''; // 위치가 있으면 함께 표시합니다.
  return `${type.padEnd(24)} ${where}${detail ? ` — ${detail}` : ''}`.trimEnd(); // 정렬된 한 줄을 반환합니다.
}
function compare(comments, state) { // 현재 상태와 baseline의 차이를 분류합니다.
  const problems = []; // fail-closed 문제 목록입니다.
  for (const [first, second] of duplicateIds(comments)) problems.push(issue('DUPLICATE-ID', second, `also at ${first.file}:${first.line}`)); // ID 재사용을 막습니다.
  const currentIds = new Set(comments.map((comment) => comment.id)); // 삭제 검사용 현재 ID 집합입니다.
  for (const comment of comments) { // 추적 블록별 동기화 상태를 판정합니다.
    const old = state.comments?.[comment.id]; // 승인된 이전 baseline을 먼저 찾습니다.
    if (comment.enRev === null) { // EN canonical marker는 모든 추적 블록에 필수입니다.
      problems.push(issue('FORMAT-ERROR', comment, 'missing EN revision')); // 기준 주석이 없으면 감사할 수 없습니다.
      continue; // 이후 비교는 의미가 없으므로 건너뜁니다.
    }
    if (!hasEnMeta(comment)) problems.push(issue('META-FIELD-MISSING', comment, 'Role/Dependencies/Impact 누락')); // EN 기준 메타는 항상 필요합니다.
    if (comment.koRev === null) { // 신규 EN-only 블록은 Gemini 인계 상태로 허용합니다.
      if (old) problems.push(issue('FORMAT-ERROR', comment, 'baselined comment lost KO revision')); // 승인된 KO 삭제는 형식 오류입니다.
      else {
        problems.push(issue('TRANSLATION-PENDING', comment, 'KO block not audited yet')); // 신규 블록은 정상 인계 상태입니다.
        problems.push(issue('NEW-UNBASELINED', comment)); // 감사 전 baseline 수용은 금지합니다.
      }
      continue; // KO hash/revision 비교는 감사 이후에만 가능합니다.
    }
    if (!hasKoMeta(comment)) problems.push(issue('META-FIELD-MISSING', comment, '역할/의존성 관계/변경 시 영향도 누락')); // KO 블록이 있으면 기존 Rule 필드를 보존합니다.
    if (comment.koRev > comment.enRev) problems.push(issue('INVALID-KO-AHEAD', comment)); // KO가 canonical보다 앞설 수 없습니다.
    if (comment.enRev > comment.koRev) problems.push(issue('TRANSLATION-PENDING', comment)); // Gemini 감사·동기화가 필요한 상태입니다.
    if (!old) { // 신규 블록은 baseline 감사가 필요합니다.
      problems.push(issue('NEW-UNBASELINED', comment)); // 자동 수용하지 않습니다.
      continue; // 비교할 이전 값이 없습니다.
    }
    if (comment.enRev < old.en_rev || comment.koRev < old.ko_rev) problems.push(issue('REVISION-REGRESSION', comment));
    if (comment.enRev !== old.en_rev || comment.koRev !== old.ko_rev || comment.sourceHash !== old.source_hash || comment.enHash !== old.en_hash || comment.koHash !== old.ko_hash) problems.push(issue('AUDIT-REQUIRED', comment));
    if (comment.enHash !== old.en_hash && comment.enRev === old.en_rev) problems.push(issue('EN-REVISION-SUSPECT', comment)); // EN 변경 후 rev 누락입니다.
    if (comment.koHash !== old.ko_hash && comment.koRev === old.ko_rev) problems.push(issue('KO-REVISION-SUSPECT', comment)); // KO 변경 후 rev 누락입니다.
    if (comment.sourceHash !== old.source_hash && comment.enRev === old.en_rev) problems.push(issue('REVISION-SUSPECT', comment, 'source changed while EN rev stayed the same')); // 소스 변경 누락입니다.
    if (comment.file !== old.file) problems.push(issue('LOCATION-CHANGED', comment, `baseline=${old.file}`)); // 이동은 허용하되 재감사를 요구합니다.
  }
  for (const id of Object.keys(state.comments ?? {})) { // baseline에만 남은 삭제 ID를 검사합니다.
    if (!currentIds.has(id)) problems.push(`MISSING-COMMENT          ${id}`); // 조용한 삭제를 막습니다.
  }
  return problems; // 호출자가 exit code와 출력을 결정합니다.
}
function writeBaseline(comments) { // 감사 완료 상태를 새 baseline으로 저장합니다.
  const state = { schema_version: 1, accepted_at: new Date().toISOString(), note: 'Accepted after source/EN audit and KO synchronization.', comments: {} }; // 원장 헤더입니다.
  const report = args.find(value => value.startsWith('--audit-report='))?.slice(15);
  const auditor = args.find(value => value.startsWith('--auditor='))?.slice(10);
  if (Boolean(report) !== Boolean(auditor)) throw new Error('AUDIT-ERROR: --audit-report and --auditor must be supplied together');
  if (report) {
    const absolute = path.resolve(root, report);
    const relative = path.relative(root, absolute).replaceAll('\\', '/');
    if (!/^Reports\/.*\.md$/.test(relative) || !fs.existsSync(absolute)) throw new Error('AUDIT-ERROR: existing Reports/*.md evidence required');
    state.audit = { auditor, report: relative };
  }
  for (const comment of comments) state.comments[comment.id] = { file: comment.file, line: comment.line, language: comment.language, en_rev: comment.enRev, ko_rev: comment.koRev, en_hash: comment.enHash, ko_hash: comment.koHash, source_hash: comment.sourceHash }; // 블록별 불변식을 기록합니다.
  fs.mkdirSync(path.dirname(statePath), { recursive: true }); // 상태 디렉터리를 준비합니다.
  const tempPath = `${statePath}.${crypto.randomUUID()}.tmp`;
  try {
    fs.writeFileSync(tempPath, `${JSON.stringify(state, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' });
    fs.renameSync(tempPath, statePath);
  } finally { if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath); } // 원장을 UTF-8 JSON으로 저장합니다.
}
function checkCommand(config) { // 현재 baseline 대비 상태를 검사합니다.
  const comments = collect(config); // 설정 범위의 추적 블록을 읽습니다.
  const state = loadState(); // 승인 원장을 읽습니다.
  const problems = compare(comments, state); // 모든 상태 이상을 분류합니다.
  const baselineCount = Object.keys(state.comments ?? {}).length; // 최초 부트스트랩과 운영 상태를 구분합니다.
  console.log(`Tracked bilingual comments: ${comments.length}`); // 추적 규모를 출력합니다.
  console.log(`Baseline entries: ${baselineCount}`); // baseline 규모를 출력합니다.
  if (comments.length === 0 && baselineCount === 0) { console.log('COMMENT-SYNC: BOOTSTRAP-PENDING — inventory 후 감사된 첫 블록부터 점진적으로 등록'); return 0; } // 도입 전 상태를 정상 동기화로 과장하지 않습니다.
  if (problems.length === 0) { console.log('COMMENT-SYNC: OK'); return 0; } // 이상이 없으면 성공합니다.
  console.log(`COMMENT-SYNC: ${problems.length} issue(s)`); // 문제 개수를 명시합니다.
  for (const problem of problems) console.log(problem); // 누락 없이 각 문제를 출력합니다.
  return 1; // CI/AI가 실패를 감지하도록 비영(非零) 종료합니다.
}
function inventoryCommand(config) { // 아직 추적되지 않은 중요 메타 주석 후보를 찾습니다.
  let tracked = 0; // 추적 블록 수입니다.
  const candidates = []; // 기존 메타 주석 후보입니다.
  for (const file of inventoryFiles(config)) { // 설정 범위만 조사합니다.
    const text = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n'); // 파일을 정규화합니다.
    const extension = path.extname(file).toLowerCase(); // 언어 parser를 선택합니다.
    for (const block of rawBlocks(text, extension)) { // 모든 주석 블록을 확인합니다.
      const body = cleanBody(block.raw, extension); // 언어 문법을 제거합니다.
      if (/^\[MINI-COMMENT:/m.test(body)) { tracked += 1; continue; } // 이미 추적 중이면 제외합니다.
      if (body.includes('[역할]') || body.includes('[Role]')) candidates.push(`${rel(file)}:${text.slice(0, block.start).split('\n').length}`); // 기존 중요 주석만 후보로 냅니다.
    }
  }
  console.log(`Tracked bilingual comments: ${tracked}`); // 현재 추적 수를 표시합니다.
  console.log(`Untracked metadata comment candidates: ${candidates.length}`); // 전환 후보 수를 표시합니다.
  for (const candidate of candidates.slice(0, 100)) console.log(candidate); // 과도한 출력을 제한합니다.
  if (candidates.length > 100) console.log(`... ${candidates.length - 100} more`); // 남은 개수를 알립니다.
  return 0; // inventory는 정보성 명령입니다.
}
function baselineCommand(config) { // 감사된 현재 상태를 baseline으로 승인합니다.
  if (!args.includes('--accept-audited')) { // 실수로 baseline을 덮지 못하게 합니다.
    console.error('baseline requires --accept-audited after an authorized source/EN audit'); // 명시적 감사 전제입니다.
    return 2; // 승인 누락을 일반 불일치와 구분합니다.
  }
  const comments = collect(config); // 현재 추적 블록을 수집합니다.
  const problems = compare(comments, loadState()).filter(problem => !/^(NEW-UNBASELINED|AUDIT-REQUIRED|LOCATION-CHANGED)\s/.test(problem));
  if (problems.length) { console.error('Baseline refused:\n' + problems.join('\n')); return 1; }
  const duplicates = duplicateIds(comments); // ID 중복을 먼저 확인합니다.
  const invalid = comments.filter((comment) => comment.enRev === null || comment.koRev === null || comment.enRev !== comment.koRev || !hasRequiredMeta(comment)); // baseline 불가 블록입니다.
  if (comments.length === 0 || duplicates.length > 0 || invalid.length > 0) { // 불완전 상태는 원장에 기록하지 않습니다.
    console.error(`Baseline refused: comments=${comments.length}, duplicates=${duplicates.length}, invalid=${invalid.length}`); // 거부 근거를 출력합니다.
    return 1; // fail-closed 종료입니다.
  }
  writeBaseline(comments); // 모든 조건이 만족된 경우에만 원장을 갱신합니다.
  console.log(`Baseline written: ${comments.length} tracked comments`); // 승인 규모를 표시합니다.
  console.log(rel(statePath)); // 실제 상태 파일 위치를 표시합니다.
  return 0; // 정상 종료합니다.
}
function help() { // 사용 가능한 계약을 간단히 출력합니다.
  console.log('Mini-Server bilingual comment sync helper'); // 도구 이름입니다.
  console.log('  comment-sync.mjs check'); // baseline 검사입니다.
  console.log('  comment-sync.mjs inventory'); // 전환 후보 조사입니다.
  console.log('  comment-sync.mjs baseline --accept-audited'); // 감사 후 baseline 승인입니다.
  console.log('Options: --root=PATH --config=PATH --state=PATH [--audit-report=Reports/...md --auditor=NAME]'); // 검증 범위와 실제 감사자 근거입니다.
  return 0; // help는 성공입니다.
}
const config = loadJson(configPath); // 설정은 필수 입력입니다.
if (!config) { console.error(`Missing config: ${configPath}`); process.exitCode = 2; } // 설정 누락은 fail-closed입니다.
else { // 설정이 있을 때만 실제 명령을 수행합니다.
  const handlers = { check: checkCommand, inventory: inventoryCommand, baseline: baselineCommand, help: () => help(), '--help': () => help(), '-h': () => help() }; // 명령 allowlist입니다.
  const handler = handlers[command]; // 요청 명령을 찾습니다.
  if (!handler) { console.error(`Unknown command: ${command}`); process.exitCode = 2; } // 임의 명령은 거부합니다.
  else process.exitCode = handler(config); // 선택 명령의 결과를 프로세스 exit code로 전달합니다.
}
