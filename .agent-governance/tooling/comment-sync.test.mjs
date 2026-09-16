#!/usr/bin/env node
// [역할] comment-sync/diff-guard/commit-message 후보를 임시 fixture에서 회귀 검증합니다.
// [의존성 관계] Node.js 표준 모듈과 로컬 Git만 사용하며 운영 프로젝트 파일은 쓰지 않습니다.
// [변경 시 영향도] 후보 계약이 바뀌면 기대 상태와 보안 경계 테스트를 함께 갱신해야 합니다.
import fs from 'node:fs'; // 임시 fixture를 생성하고 수정합니다.
import os from 'node:os'; // OS 임시 디렉터리를 사용합니다.
import path from 'node:path'; // fixture 경로를 구성합니다.
import { spawnSync } from 'node:child_process'; // 후보 CLI와 Git을 실행합니다.
import { fileURLToPath } from 'node:url'; // 후보 도구 절대 경로를 계산합니다.

const here = path.dirname(fileURLToPath(import.meta.url)); // Staging 검증 디렉터리입니다.
const commentSync = path.join(here, 'comment-sync.mjs'); // 주석 검사 후보입니다.
const guard = path.join(here, 'gemini-diff-guard.mjs'); // Gemini guard 후보입니다.
const commitCheck = path.join(here, 'commit-message-check.mjs'); // commit 검사 후보입니다.
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'eqmgmt-comment-sync-')); // 운영 저장소 밖의 임시 루트입니다.
let cases = 0; // 통과한 검증 개수를 셉니다.

function run(command, args, cwd = temp) { // 프로세스 결과를 문자열과 exit code로 반환합니다.
  return spawnSync(command, args, { cwd, encoding: 'utf8', env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' } }); // 입력 없이 동기 실행합니다.
}
function expect(condition, label, detail = '') { // 실패 지점을 명확하게 표시합니다.
  if (!condition) throw new Error(`${label}${detail ? `: ${detail}` : ''}`); // 첫 불일치에서 검증을 중단합니다.
  cases += 1; // 성공 케이스를 누적합니다.
}
function invoke(tool, args) { // Node CLI 후보를 같은 런타임으로 실행합니다.
  return run(process.execPath, [tool, ...args]); // stdout/stderr/exit code를 보존합니다.
}
function write(relative, content) { // 임시 fixture 파일만 생성합니다.
  const target = path.join(temp, relative); // fixture 내부 절대 경로입니다.
  fs.mkdirSync(path.dirname(target), { recursive: true }); // 부모 디렉터리를 준비합니다.
  fs.writeFileSync(target, content, 'utf8'); // UTF-8 텍스트로 기록합니다.
}
function read(relative) { // fixture 원문 복원에 사용합니다.
  return fs.readFileSync(path.join(temp, relative), 'utf8'); // 운영 파일은 읽지 않습니다.
}
const pyBase = `# [MINI-COMMENT: TEST.PY.LINE]\n# [EN rev.1]\n# [Role] Validates a fixture value.\n# [Dependencies] Python fixture only.\n# [Impact] Changes fixture validation behavior.\n# [KO rev.1]\n# [역할] fixture 값을 검증한다.\n# [의존성 관계] Python fixture만 사용한다.\n# [변경 시 영향도] fixture 검증 동작에 영향을 준다.\n\ndef validate(value):\n    return bool(value)\n`; // Python # 형식입니다.
const pyDocBase = `\"\"\"[MINI-COMMENT: TEST.PY.DOC]\n[EN rev.1]\n[Role] Describes a module fixture.\n[Dependencies] No external dependency.\n[Impact] Documentation fixture only.\n[KO rev.1]\n[역할] 모듈 fixture를 설명한다.\n[의존성 관계] 외부 의존성이 없다.\n[변경 시 영향도] 문서 fixture에만 영향을 준다.\n\"\"\"\nVALUE = 1\n`; // Python triple quote 형식입니다.
const jsBase = `// [MINI-COMMENT: TEST.JS.LINE]\n// [EN rev.1]\n// [Role] Returns a JavaScript fixture value.\n// [Dependencies] JavaScript fixture only.\n// [Impact] Changes fixture output.\n// [KO rev.1]\n// [역할] JavaScript fixture 값을 반환한다.\n// [의존성 관계] JavaScript fixture만 사용한다.\n// [변경 시 영향도] fixture 출력에 영향을 준다.\n\nexport function value() { return 1; }\n`; // JavaScript // 형식입니다.
const jsBlockBase = `/**\n * [MINI-COMMENT: TEST.JS.BLOCK]\n * [EN rev.1]\n * [Role] Returns a block-comment fixture value.\n * [Dependencies] JavaScript fixture only.\n * [Impact] Changes block fixture output.\n * [KO rev.1]\n * [역할] 블록 주석 fixture 값을 반환한다.\n * [의존성 관계] JavaScript fixture만 사용한다.\n * [변경 시 영향도] 블록 fixture 출력에 영향을 준다.\n */\nexport const blockValue = () => 2;\n`; // JavaScript block 형식입니다.
const htmlBase = `<!--\n[MINI-COMMENT: TEST.HTML.BLOCK]\n[EN rev.1]\n[Role] Renders a fixture panel.\n[Dependencies] Static fixture markup only.\n[Impact] Changes fixture presentation.\n[KO rev.1]\n[역할] fixture 패널을 렌더링한다.\n[의존성 관계] 정적 fixture 마크업만 사용한다.\n[변경 시 영향도] fixture 표시 방식에 영향을 준다.\n-->\n<section>fixture</section>\n`; // HTML 주석 형식입니다.
const config = { schema_version: 1, roots: ['a.py', 'doc.py', 'a.js', 'b.js', 'a.html'], extensions: ['.py', '.js', '.mjs', '.html'] }; // 다중언어 fixture 범위입니다.
write('a.py', pyBase); // Python # fixture를 준비합니다.
write('doc.py', pyDocBase); // Python triple quote fixture를 준비합니다.
write('a.js', jsBase); // JavaScript line fixture를 준비합니다.
write('b.js', jsBlockBase); // JavaScript block fixture를 준비합니다.
write('a.html', htmlBase); // HTML fixture를 준비합니다.
write('config.json', `${JSON.stringify(config, null, 2)}\n`); // comment-sync 설정을 준비합니다.
const common = [`--root=${temp}`, '--config=config.json', '--state=state.json']; // 공통 CLI 인자입니다.
write('empty-config.json', `${JSON.stringify({ schema_version: 1, roots: [], extensions: ['.py', '.js', '.mjs', '.html'] }, null, 2)}\n`); // 최초 도입 상태를 검증하는 빈 설정입니다.
let result = invoke(commentSync, ['check', `--root=${temp}`, '--config=empty-config.json', '--state=empty-state.json']); // 추적 블록과 baseline이 모두 없는 최초 상태입니다.
expect(result.status === 0 && result.stdout.includes('BOOTSTRAP-PENDING'), 'empty initial state reports bootstrap pending without blocking'); // 정상 동기화로 과장하지 않되 단계적 도입을 막지 않습니다.
const enOnly = `# [MINI-COMMENT: TEST.PY.EN_ONLY]\n# [EN rev.1]\n# [Role] Prepares a canonical handoff.\n# [Dependencies] Python fixture only.\n# [Impact] Requires Gemini audit before baseline.\n\ndef pending():\n    return True\n`; // 신규 구현자가 KO를 대신 작성하지 않은 정상 인계 fixture입니다.
write('pending.py', enOnly); // EN-only 신규 블록을 준비합니다.
write('pending-config.json', `${JSON.stringify({ schema_version: 1, roots: ['pending.py'], extensions: ['.py'] }, null, 2)}\n`); // 별도 상태로 검사합니다.
result = invoke(commentSync, ['check', `--root=${temp}`, '--config=pending-config.json', '--state=pending-state.json']); // 신규 EN-only 인계를 검사합니다.
expect(result.status === 1 && result.stdout.includes('TRANSLATION-PENDING') && result.stdout.includes('NEW-UNBASELINED') && !result.stdout.includes('FORMAT-ERROR'), 'new EN-only block is a valid Gemini handoff'); // 형식 오류가 아니라 감사 대기 상태여야 합니다.
result = invoke(commentSync, ['baseline', ...common]); // 명시적 감사 승인 없는 baseline을 시도합니다.
expect(result.status === 2 && result.stderr.includes('--accept-audited'), 'baseline requires audit flag'); // 실수 갱신을 거부해야 합니다.
result = invoke(commentSync, ['baseline', ...common, '--accept-audited']); // 감사 완료를 모의합니다.
expect(result.status === 0 && result.stdout.includes('Baseline written: 5'), 'multi-language baseline'); // 5개 블록이 등록되어야 합니다.
result = invoke(commentSync, ['check', ...common]); // 생성된 baseline과 같은 상태를 검사합니다.
expect(result.status === 0 && result.stdout.includes('COMMENT-SYNC: OK'), 'baseline check pass'); // 정상 상태여야 합니다.

write('a.py', pyBase.replace('return bool(value)', 'return value is not None')); // 코드만 바꿉니다.
result = invoke(commentSync, ['check', ...common]); // EN rev 누락을 검사합니다.
expect(result.status === 1 && result.stdout.includes('REVISION-SUSPECT'), 'source hash detects code change'); // source 변경을 잡아야 합니다.
write('a.py', pyBase); // 기준 fixture를 복원합니다.
write('a.js', jsBase.replace('Returns a JavaScript fixture value.', 'Returns the JavaScript fixture value.')); // EN 본문만 바꿉니다.
result = invoke(commentSync, ['check', ...common]); // EN hash/rev 정합성을 검사합니다.
expect(result.status === 1 && result.stdout.includes('EN-REVISION-SUSPECT'), 'EN revision suspect'); // EN rev 누락이어야 합니다.
write('a.js', jsBase); // 기준 fixture를 복원합니다.
write('a.html', htmlBase.replace('fixture 패널을 렌더링한다.', 'fixture 패널을 표시한다.')); // KO 본문만 바꿉니다.
result = invoke(commentSync, ['check', ...common]); // KO hash/rev 정합성을 검사합니다.
expect(result.status === 1 && result.stdout.includes('KO-REVISION-SUSPECT'), 'KO revision suspect'); // KO rev 누락이어야 합니다.
write('a.html', htmlBase); // 기준 fixture를 복원합니다.
write('a.py', pyBase.replace('[EN rev.1]', '[EN rev.2]')); // 구현자가 EN revision만 증가시킨 상태를 만듭니다.
result = invoke(commentSync, ['check', ...common]); // Gemini 동기화 대기를 검사합니다.
expect(result.status === 1 && result.stdout.includes('TRANSLATION-PENDING'), 'translation pending'); // EN>KO여야 합니다.
write('a.py', pyBase.replace('[KO rev.1]', '[KO rev.2]')); // KO가 canonical보다 앞선 잘못된 상태를 만듭니다.
result = invoke(commentSync, ['check', ...common]); // KO ahead를 검사합니다.
expect(result.status === 1 && result.stdout.includes('INVALID-KO-AHEAD'), 'KO ahead blocked'); // baseline 승인 대상이 아닙니다.
write('a.py', pyBase.replace('# [Impact] Changes fixture validation behavior.\n', '')); // 영문 필수 메타 필드를 제거합니다.
result = invoke(commentSync, ['check', ...common]); // 기존 3대 메타 보존을 검사합니다.
expect(result.status === 1 && result.stdout.includes('META-FIELD-MISSING'), 'required metadata preserved'); // 메타 누락을 차단해야 합니다.
write('a.py', pyBase); // Python fixture를 정상 복원합니다.
write('b.js', jsBlockBase.replace('TEST.JS.BLOCK', 'TEST.JS.LINE')); // 다른 블록과 Comment ID를 충돌시킵니다.
result = invoke(commentSync, ['check', ...common]); // ID 안정성을 검사합니다.
expect(result.status === 1 && result.stdout.includes('DUPLICATE-ID'), 'duplicate comment id blocked'); // 중복 ID를 허용하지 않습니다.
write('b.js', jsBlockBase); // JavaScript fixture를 정상 복원합니다.
fs.unlinkSync(path.join(temp, 'a.html')); // baseline에 존재하던 블록을 삭제합니다.
result = invoke(commentSync, ['check', ...common]); // 조용한 주석 삭제를 검사합니다.
expect(result.status === 1 && result.stdout.includes('MISSING-COMMENT'), 'missing comment detected'); // 삭제 ID를 보고해야 합니다.
write('a.html', htmlBase); // HTML fixture를 복원합니다.
write('legacy.py', '# [역할] 아직 MINI-COMMENT로 전환되지 않은 중요 주석\nVALUE = 2\n'); // inventory 후보를 만듭니다.
write('config.json', `${JSON.stringify({ ...config, roots: [...config.roots, 'legacy.py'] }, null, 2)}\n`); // inventory 범위를 확장합니다.
result = invoke(commentSync, ['inventory', ...common]); // 점진적 전환 후보를 조사합니다.
expect(result.status === 0 && result.stdout.includes('Untracked metadata comment candidates: 1'), 'inventory finds legacy metadata'); // 일괄 변환 대신 후보만 제시해야 합니다.
write('config.json', `${JSON.stringify(config, null, 2)}\n`); // guard 검증 전에 원래 설정을 복원합니다.
const guardRoot = path.join(temp, 'guard-repo'); // diff guard만을 위한 별도 임시 Git 저장소입니다.
fs.mkdirSync(path.join(guardRoot, 'docs'), { recursive: true }); // 허용 문서 경로를 준비합니다.
const guardSource = pyBase.replace('TEST.PY.LINE', 'GUARD.PY.VALUE'); // 동일 규격의 추적 소스를 재사용합니다.
fs.writeFileSync(path.join(guardRoot, 'guard.py'), guardSource, 'utf8'); // guard 대상 소스입니다.
fs.writeFileSync(path.join(guardRoot, 'notes.txt'), 'baseline note\n', 'utf8'); // 다른 작업자의 선행 dirty 변경을 모의할 파일입니다.
fs.writeFileSync(path.join(guardRoot, 'docs', 'COMMENT_GLOSSARY.md'), '# Glossary\n', 'utf8'); // 기본 허용 문서입니다.
run('git', ['init', '-q'], guardRoot); // 임시 Git 저장소를 초기화합니다.
run('git', ['config', 'user.name', 'Fixture'], guardRoot); // 임시 commit 작성자입니다.
run('git', ['config', 'user.email', 'fixture@example.test'], guardRoot); // 전역 Git 설정을 변경하지 않습니다.
run('git', ['add', '.'], guardRoot); // 초기 fixture만 stage합니다.
result = run('git', ['commit', '-q', '-m', 'fixture baseline'], guardRoot); // HEAD 비교 기준을 만듭니다.
expect(result.status === 0, 'temporary git baseline'); // fixture commit이 정상이어야 합니다.
fs.writeFileSync(path.join(guardRoot, 'notes.txt'), 'preexisting other-worker change\n', 'utf8'); // snapshot 이전 dirty 변경입니다.
const guardCommon = [`--root=${guardRoot}`, '--snapshot=guard-snapshot.json']; // guard 공통 인자입니다.
result = invoke(guard, ['snapshot', ...guardCommon]); // Gemini 감사 직전 상태를 저장합니다.
expect(result.status === 0, 'guard snapshot'); // 선행 dirty 상태를 안전하게 캡처해야 합니다.
fs.writeFileSync(path.join(guardRoot, 'guard.py'), guardSource.replace('fixture 값을 검증한다.', 'fixture 값의 유효성을 검증한다.'), 'utf8'); // KO 본문만 바꿉니다.
result = invoke(guard, ['check', ...guardCommon]); // snapshot 이후 delta를 검사합니다.
expect(result.status === 0 && result.stdout.includes('KO-only') && result.stdout.includes('GEMINI-DIFF-GUARD: OK'), 'KO-only change allowed with preexisting dirty file'); // 선행 변경은 무시하고 KO만 허용합니다.
fs.writeFileSync(path.join(guardRoot, 'guard.py'), guardSource.replace('return bool(value)', 'return value is not None'), 'utf8'); // 실행 코드를 변경합니다.
result = invoke(guard, ['check', ...guardCommon]); // 코드 변경 차단을 검사합니다.
expect(result.status === 1 && result.stdout.includes('execution code or EN/non-KO content changed'), 'execution code blocked'); // KO 업무 범위를 넘어가면 실패해야 합니다.
fs.writeFileSync(path.join(guardRoot, 'guard.py'), guardSource.replace('Validates a fixture value.', 'Validates the fixture value.'), 'utf8'); // EN canonical을 변경합니다.
result = invoke(guard, ['check', ...guardCommon]); // EN 변경 차단을 검사합니다.
expect(result.status === 1 && result.stdout.includes('execution code or EN/non-KO content changed'), 'EN change blocked'); // Gemini가 EN을 직접 고치지 못하게 합니다.
fs.writeFileSync(path.join(guardRoot, 'guard.py'), guardSource, 'utf8'); // 소스를 snapshot 기준으로 복원합니다.
fs.writeFileSync(path.join(guardRoot, 'docs', 'COMMENT_GLOSSARY.md'), '# Glossary\n용어 추가\n', 'utf8'); // 기본 허용 용어집을 수정합니다.
result = invoke(guard, ['check', ...guardCommon]); // 허용 문서 변경을 검사합니다.
expect(result.status === 0 && result.stdout.includes('allowed document'), 'glossary change allowed'); // 용어집은 감사 범위 안입니다.
fs.writeFileSync(path.join(guardRoot, 'docs', 'COMMENT_GLOSSARY.md'), '# Glossary\n', 'utf8'); // 용어집을 복원합니다.
fs.writeFileSync(path.join(guardRoot, 'notes.txt'), 'Gemini changed another worker file\n', 'utf8'); // 선행 dirty 파일을 Gemini가 다시 바꾼 상황입니다.
result = invoke(guard, ['check', ...guardCommon]); // 타 작업자 변경 보존을 검사합니다.
expect(result.status === 1 && result.stdout.includes('notes.txt'), 'preexisting dirty file mutation blocked'); // snapshot과 달라지면 차단해야 합니다.
fs.writeFileSync(path.join(guardRoot, 'notes.txt'), 'preexisting other-worker change\n', 'utf8'); // snapshot 상태로 복원합니다.
result = run('git', ['commit', '--allow-empty', '-q', '-m', 'head change'], guardRoot); // 동시 commit을 모의합니다.
expect(result.status === 0, 'temporary concurrent commit'); // HEAD를 실제로 바꿉니다.
result = invoke(guard, ['check', ...guardCommon]); // stale snapshot을 검사합니다.
expect(result.status === 1 && result.stderr.includes('HEAD-CHANGED'), 'HEAD change invalidates snapshot'); // 동시 작업은 새 snapshot을 요구합니다.
result = invoke(commitCheck, ['feat: 카탈로그 신청 규칙을 정리']); // 권장 한국어 commit 제목입니다.
expect(result.status === 0 && result.stdout.includes('COMMIT-MESSAGE: OK'), 'Korean Conventional Commit accepted'); // 정상 제목이어야 합니다.
result = invoke(commitCheck, ['feat: add catalog request rules']); // 기존 영어-only 패턴입니다.
expect(result.status === 1 && result.stderr.includes('Korean subject required'), 'English-only commit rejected'); // 사용자 가독성 정책에 맞지 않습니다.
result = invoke(commitCheck, ['feature: 한국어지만 type이 잘못됨']); // 허용되지 않은 type입니다.
expect(result.status === 1 && result.stderr.includes('invalid Conventional Commit'), 'invalid type rejected'); // 자동화 호환성을 보존합니다.
result = invoke(commitCheck, ['Merge branch test']); // Git 자동 merge 메시지를 모의합니다.
expect(result.status === 0 && result.stdout.includes('AUTO-GENERATED-EXCEPTION'), 'auto merge exception'); // 자동 메시지는 예외로 분리합니다.

console.log(JSON.stringify({ ok: true, cases, temp_scope: temp, note: 'temporary fixtures only; production repository was not mutated by this verifier' }, null, 2)); // 최종 증거를 출력합니다.
fs.rmSync(temp, { recursive: true, force: true }); // 검증이 끝난 임시 fixture를 제거합니다.
