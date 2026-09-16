#!/usr/bin/env node
// [역할] Gemini 주석 감사 후 Git 변경이 KO 영역과 명시 허용 문서에만 한정됐는지 검사합니다.
// [의존성 관계] Git HEAD, 작업트리, MINI-COMMENT 블록 형식을 사용합니다.
// [변경 시 영향도] 허용 범위가 넓어지면 Gemini가 실행 코드나 EN 기준을 변경할 위험이 증가합니다.
import fs from 'node:fs'; // 현재 작업트리 파일을 읽습니다.
import path from 'node:path'; // 상대/절대 경로를 정규화합니다.
import { execFileSync } from 'node:child_process'; // Git의 읽기 전용 명령을 실행합니다.
import { fileURLToPath } from 'node:url'; // 기본 프로젝트 루트를 계산합니다.

const here = path.dirname(fileURLToPath(import.meta.url)); // 후보 도구의 위치입니다.
const args = process.argv.slice(2); // CLI allowlist 인자를 보존합니다.
const rootArg = args.find((value) => value.startsWith('--root=')); // 테스트 루트 재정의입니다.
const root = path.resolve(rootArg ? rootArg.slice(7) : path.resolve(here, '..', '..')); // 프로젝트 루트입니다.
const extraAllowed = new Set(args.filter((value) => value.startsWith('--allow-path=')).map((value) => value.slice(13).replaceAll('\\', '/'))); // 작업별 보고서 등을 명시 허용합니다.
const sourceExtensions = new Set(['.py', '.js', '.mjs', '.html']); // KO-only 검사가 가능한 소스 형식입니다.
const defaultAllowed = new Set(['.agent-governance/comment-sync/state.json', 'docs/COMMENT_GLOSSARY.md']); // Gemini 기본 수정 허용 문서입니다.

function git(...gitArgs) { // Git 출력의 인코딩과 작업 위치를 고정합니다.
  return execFileSync('git', gitArgs, { cwd: root, encoding: 'utf8', env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' } }).replace(/\r\n/g, '\n'); // 읽기 전용 결과를 반환합니다.
}
function normalize(value) { // 비교 전 줄바꿈만 정규화합니다.
  return value.replace(/\r\n/g, '\n'); // 의미 있는 공백은 그대로 유지합니다.
}
function isAllowedDocument(file) { // 소스 외 수정 허용 경로를 판정합니다.
  const normalized = file.replaceAll('\\', '/'); // Git 경로 형식으로 맞춥니다.
  return defaultAllowed.has(normalized) || extraAllowed.has(normalized); // 명시된 문서만 허용합니다.
}
function commentPattern(extension) { // 언어별 전체 주석 블록 패턴을 반환합니다.
  if (extension === '.py') return /(?:^[ \t]*#.*(?:\r?\n|$))+|(?:'''[\s\S]*?'''|"""[\s\S]*?""")/gm; // Python line/docstring입니다.
  if (extension === '.js' || extension === '.mjs') return /(?:^[ \t]*\/\/.*(?:\r?\n|$))+|\/\*[\s\S]*?\*\//gm; // JavaScript line/block입니다.
  if (extension === '.html') return /<!--[\s\S]*?-->/g; // HTML block입니다.
  return null; // 미지원 확장자는 source guard 대상이 아닙니다.
}
function maskKoRaw(raw, extension) { // 추적 블록의 KO marker와 본문만 비교에서 제외합니다.
  if (!raw.includes('[MINI-COMMENT:')) return raw; // 일반 주석은 그대로 비교합니다.
  const koIndex = raw.search(/\[KO rev\.\d+\]/); // KO 섹션 시작점을 찾습니다.
  if (koIndex < 0) return raw; // KO marker가 없으면 변경을 숨기지 않습니다.
  let suffix = ''; // block comment의 닫는 토큰만 보존합니다.
  const trimmed = raw.trimStart(); // 주석 형식을 판별합니다.
  if (extension === '.html') suffix = '-->'; // HTML 종료 토큰입니다.
  else if ((extension === '.js' || extension === '.mjs') && trimmed.startsWith('/*')) suffix = '*/'; // JS block 종료 토큰입니다.
  else if (extension === '.py' && trimmed.startsWith('"""')) suffix = '"""'; // Python double docstring 종료 토큰입니다.
  else if (extension === '.py' && trimmed.startsWith("'''")) suffix = "'''"; // Python single docstring 종료 토큰입니다.
  const suffixIndex = suffix ? raw.lastIndexOf(suffix) : raw.length; // 닫는 토큰 위치입니다.
  const prefix = raw.slice(0, koIndex); // Comment ID와 EN canonical은 완전히 보존합니다.
  return `${prefix}[KO-MASKED]${suffix ? raw.slice(suffixIndex) : ''}`; // KO 길이·문구·revision만 무시합니다.
}
function maskKo(text, extension) { // 파일 전체에서 추적 KO 영역만 정규화합니다.
  const pattern = commentPattern(extension); // 해당 언어의 주석 패턴을 선택합니다.
  if (!pattern) return normalize(text); // 미지원 파일은 그대로 비교합니다.
  return normalize(text).replace(pattern, (raw) => maskKoRaw(raw, extension)); // 각 주석 블록을 선택적으로 마스킹합니다.
}
function shaBuffer(buffer) { // snapshot 변화 탐지용 raw bytes hash입니다.
  return cryptoHash(buffer); // 아래 공통 helper를 사용합니다.
}
const cryptoModule = await import('node:crypto'); // raw snapshot hash에 Node 표준 crypto를 사용합니다.
function cryptoHash(buffer) { // Buffer/문자열을 SHA-256으로 변환합니다.
  return cryptoModule.createHash('sha256').update(buffer).digest('hex'); // hex digest를 반환합니다.
}
function statusEntries() { // 현재 Git 변경 경로와 상태를 읽습니다.
  const lines = git('status', '--porcelain=v1', '--untracked-files=all').split('\n').filter(Boolean); // tracked/untracked 모두 포함합니다.
  return lines.map((line) => { // 간단한 porcelain 항목으로 정규화합니다.
    const status = line.slice(0, 2); // XY 상태 코드입니다.
    const rawPath = line.slice(3).replace(/^"|"$/g, ''); // 일반 경로를 추출합니다.
    const file = rawPath.includes(' -> ') ? rawPath.split(' -> ').at(-1) : rawPath; // rename은 새 경로를 사용합니다.
    return { status, file: file.replaceAll('\\', '/') }; // Git 스타일 구분자로 반환합니다.
  });
}
function fileBytes(file) { // 현재 작업트리 파일을 안전하게 읽습니다.
  const absolute = path.resolve(root, file); // 프로젝트 내부 절대 경로입니다.
  return fs.existsSync(absolute) ? fs.readFileSync(absolute) : null; // 삭제 파일은 null입니다.
}
function headText(file) { // HEAD의 추적 파일 내용을 읽습니다.
  try { return git('show', `HEAD:${file}`); } catch { return null; } // 신규 파일은 null로 처리합니다.
}
function snapshotCommand(snapshotPath) { // Gemini 작업 전 dirty 상태를 보존합니다.
  const entries = statusEntries(); // 선행 변경을 확인합니다.
  const snapshot = { schema_version: 1, created_at: new Date().toISOString(), head: git('rev-parse', 'HEAD').trim(), files: {} }; // 기준 commit을 고정합니다.
  for (const entry of entries) { // 기존 dirty 파일은 내용까지 저장합니다.
    const bytes = fileBytes(entry.file); // 현재 작업트리 기준입니다.
    snapshot.files[entry.file] = { status: entry.status, sha256: bytes ? shaBuffer(bytes) : null, content_base64: bytes ? bytes.toString('base64') : null }; // 이후 delta 비교용입니다.
  }
  fs.mkdirSync(path.dirname(snapshotPath), { recursive: true }); // snapshot 디렉터리를 준비합니다.
  fs.writeFileSync(snapshotPath, `${JSON.stringify(snapshot, null, 2)}\n`, 'utf8'); // 작업 전 상태를 기록합니다.
  console.log(`Guard snapshot written: ${path.relative(root, snapshotPath).replaceAll('\\', '/')}`); // 위치를 보고합니다.
  return 0; // snapshot 성공입니다.
}
function headBytes(file) { // HEAD의 원시 bytes를 가져옵니다.
  try { return execFileSync('git', ['show', `HEAD:${file}`], { cwd: root, encoding: null, env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' } }); } catch { return null; } // 신규 파일은 null입니다.
}
function snapshotBytes(snapshot, file) { // Gemini 작업 직전 파일 내용을 복원합니다.
  const entry = snapshot.files?.[file]; // 기존 dirty snapshot을 먼저 확인합니다.
  if (entry) return entry.content_base64 === null ? null : Buffer.from(entry.content_base64, 'base64'); // 선행 변경을 정확히 기준으로 사용합니다.
  return headBytes(file); // 당시 clean 파일은 HEAD가 기준입니다.
}
function checkCommand(snapshotPath) { // snapshot 이후 Gemini가 만든 delta만 검사합니다.
  if (!fs.existsSync(snapshotPath)) { console.error(`Missing snapshot: ${snapshotPath}`); return 2; } // 기준 없이는 검사하지 않습니다.
  const snapshot = JSON.parse(fs.readFileSync(snapshotPath, 'utf8')); // 작업 전 상태를 읽습니다.
  const currentHead = git('rev-parse', 'HEAD').trim(); // 현재 commit을 확인합니다.
  if (currentHead !== snapshot.head) { console.error(`GUARD: HEAD-CHANGED ${snapshot.head} -> ${currentHead}`); return 1; } // 감사 중 commit 변화는 중단합니다.
  const snapshotRel = path.relative(root, snapshotPath).replaceAll('\\', '/'); // snapshot 자체는 검사 대상에서 제외합니다.
  const currentEntries = statusEntries(); // 현재 dirty 경로를 수집합니다.
  const files = new Set([...Object.keys(snapshot.files ?? {}), ...currentEntries.map((entry) => entry.file)]); // 이전/현재 변경을 모두 비교합니다.
  const violations = []; // 허용 범위를 벗어난 delta입니다.
  const accepted = []; // 실제 Gemini 허용 변경입니다.
  for (const file of [...files].sort()) { // 경로별로 결정적으로 검사합니다.
    if (file === snapshotRel) continue; // guard snapshot은 임시 상태 파일입니다.
    const before = snapshotBytes(snapshot, file); // Gemini 작업 직전 bytes입니다.
    const after = fileBytes(file); // 현재 작업트리 bytes입니다.
    const beforeHash = before ? shaBuffer(before) : null; // 빠른 동일성 비교입니다.
    const afterHash = after ? shaBuffer(after) : null; // 현재 hash입니다.
    if (beforeHash === afterHash) continue; // 다른 작업자의 선행 변경은 그대로 보존되면 무시합니다.
    if (isAllowedDocument(file)) { accepted.push(`${file} (allowed document)`); continue; } // 상태/용어집/명시 보고서는 허용합니다.
    const extension = path.extname(file).toLowerCase(); // 소스 KO-only 검사를 준비합니다.
    if (!sourceExtensions.has(extension) || !before || !after) { violations.push(`${file}: path/type/create/delete not allowed`); continue; } // 실행 파일 생성·삭제는 금지합니다.
    const beforeMasked = maskKo(before.toString('utf8'), extension); // 작업 전 KO를 마스킹합니다.
    const afterMasked = maskKo(after.toString('utf8'), extension); // 작업 후 KO를 마스킹합니다.
    if (beforeMasked !== afterMasked) violations.push(`${file}: execution code or EN/non-KO content changed`); // KO 외 변화는 차단합니다.
    else accepted.push(`${file} (KO-only)`); // 순수 KO 동기화만 허용합니다.
  }
  console.log(`Guard accepted changes: ${accepted.length}`); // 허용된 Gemini 변경 수를 표시합니다.
  for (const item of accepted) console.log(`ALLOW ${item}`); // 사람이 확인할 수 있게 경로를 출력합니다.
  if (violations.length === 0) { console.log('GEMINI-DIFF-GUARD: OK'); return 0; } // 위반이 없으면 성공합니다.
  console.log(`GEMINI-DIFF-GUARD: ${violations.length} violation(s)`); // 실패 개수를 표시합니다.
  for (const violation of violations) console.log(`BLOCK ${violation}`); // 차단 이유를 모두 출력합니다.
  return 1; // 자동화가 중단되도록 실패 코드를 반환합니다.
}
function help() { // 명령 계약을 출력합니다.
  console.log('Mini-Server Gemini diff guard'); // 도구 이름입니다.
  console.log('  gemini-diff-guard.mjs snapshot --snapshot=PATH'); // 감사 전 snapshot입니다.
  console.log('  gemini-diff-guard.mjs check --snapshot=PATH [--allow-path=PATH]'); // 감사 후 delta 검사입니다.
  console.log('Options: --root=PATH'); // fixture 검증용 루트입니다.
  return 0; // help는 성공입니다.
}
const command = args.find((value) => !value.startsWith('--')) ?? 'check'; // 기본 명령은 check입니다.
const snapshotArg = args.find((value) => value.startsWith('--snapshot=')); // 기준 snapshot 인자입니다.
const snapshotPath = snapshotArg ? path.resolve(root, snapshotArg.slice(11)) : null; // 절대 경로로 정규화합니다.
if (command === 'snapshot') { // 감사 전 상태 캡처입니다.
  if (!snapshotPath) { console.error('snapshot requires --snapshot=PATH'); process.exitCode = 2; } // 경로 누락을 거부합니다.
  else process.exitCode = snapshotCommand(snapshotPath); // 기준 상태를 기록합니다.
} else if (command === 'check') { // 감사 후 변경 범위 검사입니다.
  if (!snapshotPath) { console.error('check requires --snapshot=PATH'); process.exitCode = 2; } // 기준 없이는 비교하지 않습니다.
  else process.exitCode = checkCommand(snapshotPath); // Gemini delta를 판정합니다.
} else if (['help', '--help', '-h'].includes(command)) process.exitCode = help(); // 도움말입니다.
else { console.error(`Unknown command: ${command}`); process.exitCode = 2; } // 임의 명령은 거부합니다.
