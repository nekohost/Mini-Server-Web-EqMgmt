// [역할] Context 경로 역할·정규화·구조화 오류를 읽기 전용으로 처리한다.
// [의존성 관계] governance-tool의 router와 Node path/fs. [변경 시 영향도] catalog/CLI 진단 계약.
import path from 'node:path'; // 운영체제 경로와 Windows 절대 경로를 분리한다.
import fs from 'node:fs'; // 존재하는 경로의 symlink 경계만 읽는다.

// [역할] 실패는 pack 없이 진단만 전달한다. [의존성 관계] CLI catch. [변경 시 영향도] 오류 소비자.
export class ContextInputError extends Error {
  constructor(diagnostics) { // 모든 원인을 함께 보존한다.
    super(diagnostics.map(item => item.message).join(' | ')); // 기존 문자열 error 키도 유지한다.
    this.diagnostics = diagnostics; // 기계 판독 코드·입력·힌트를 노출한다.
  }
}

// [역할] 규칙 수정 없이 가능한 진단과 구현 재개의 경계를 설명한다. [의존성 관계] Rule 9-3. [변경 시 영향도] 자동 재시도 안내.
export const CONTEXT_RECOVERY = Object.freeze({
  implementationBlocked: true, // 실패 상태에서는 일반 구현이 불가능하다.
  readOnlyDiagnosis: ['catalog', 'validate', 'inspect-declared-inputs'], // 정책·파일을 변경하지 않는 검사만 안내한다.
  resumeRequires: ['evidence-based-input-correction', 'validate-pass', 'new-context-pass', 'read-all-packs', 'existing-user-authorization'], // 자동 승인이나 노드 축소는 허용하지 않는다.
});

// [역할] 구조화 진단을 같은 모양으로 만든다. [의존성 관계] context loader. [변경 시 영향도] 오류 테스트.
export function diagnostic(code, message, details = {}) {
  return { code, message, ...details }; // 호출자가 input·role·expectedPaths·hint를 추가한다.
}

// [역할] 경로가 프로젝트 밖인지 운영체제 의미로 판정한다. [의존성 관계] path.relative. [변경 시 영향도] scope 게이트.
function outside(root, target) {
  const relative = path.relative(root, target); // 실제 프로젝트를 기준으로 비교한다.
  return relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative); // 이름이 ..로 시작하는 정상 하위 폴더와 구분한다.
}

// [역할] 생성 전 파일도 가장 가까운 기존 조상의 실제 경계를 검사한다. [의존성 관계] realpath. [변경 시 영향도] symlink 통한 외부 경로 오분류.
function resolvedAncestor(target) {
  let current = target; // 대상 자체부터 조사한다.
  while (!fs.existsSync(current)) { // 아직 생성하지 않은 후보는 상위 디렉터리로 이동한다.
    const parent = path.dirname(current); // 다음 기존 조상을 찾는다.
    if (parent === current) return current; // 파일시스템 루트에서 종료한다.
    current = parent; // 반복 깊이는 경로 구성요소 수로 제한된다.
  }
  return fs.realpathSync(current); // symlink/junction의 실제 대상을 반환한다.
}

// [역할] 대상/참고를 혼합하지 않고 모든 경로를 독립 검증한다. [의존성 관계] router 등록 패턴/외부 scope. [변경 시 영향도] 성공 context 입력.
export function classifyPaths(options, router, projectRoot, matches) {
  const diagnostics = []; // 오류 발생 시에도 모든 입력을 점검한다.
  const entries = []; // 역할과 원본/정규화 경로를 함께 보존한다.
  const policy = router.routing_policy; // manifest에 검증된 정책을 사용한다.
  const scopeAllowed = options.intents.some(intent => policy.external_path_scope_intents.includes(intent)); // 외부 경로는 scope intent가 필수다.
  const root = fs.realpathSync(projectRoot); // 프로젝트 자체가 symlink인 경우도 동일하게 비교한다.
  for (const [role, values] of [['target', options.paths], ['reference', options.referencePaths || []]]) { // 참고 경로를 작업 대상으로 승격하지 않는다.
    for (const input of values) { // 각각 독립적으로 검사한다.
      if (typeof input !== 'string' || !input.trim() || /[\x00-\x1f*?]/u.test(input)) { // 빈값·제어문자·glob 입력은 대상이 불명확하다.
        diagnostics.push(diagnostic('INVALID_PATH', '경로는 비어 있지 않은 실제 대상이어야 합니다.', { input, role })); // 원인을 명확히 분리한다.
        continue; // 잘못된 경로를 파일시스템에 전달하지 않는다.
      }
      const portable = input.replaceAll('\\', '/'); // 구분자만 통일하며 Staging 접두사는 제거하지 않는다.
      const foreignWindows = process.platform !== 'win32' && path.win32.isAbsolute(input); // Linux에서 Windows 드라이브를 상대 경로로 오판하지 않는다.
      const resolved = path.resolve(projectRoot, portable); // ..를 제거한 실제 경계로 판단한다.
      const external = foreignWindows || outside(projectRoot, resolved) || outside(root, resolvedAncestor(resolved)); // symlink 경계도 포함한다.
      const normalized = external ? portable : path.relative(projectRoot, resolved).split(path.sep).join('/') || '.'; // 프로젝트 내부 절대 경로는 상대 경로로 변환한다.
      entries.push({ input, normalized, role, external }); // 실패 진단과 정상 응답에서 같은 입력 모델을 사용한다.
      if (external) { // 외부 경로는 로컬 프로젝트 등록 패턴으로 우회하지 않는다.
        if (!scopeAllowed) diagnostics.push(diagnostic('EXTERNAL_SCOPE_REQUIRED', `외부 path에는 scope intent가 필요합니다: ${input}`, { input, role, hint: 'catalog에서 실제 외부 작업에 맞는 scope intent를 확인하세요.' })); // 권한을 자동 추가하지 않는다.
      } else if (!policy.registered_project_paths.some(pattern => matches(pattern, normalized) || (pattern.endsWith('/**') && matches(pattern.slice(0, -3), normalized)))) { // 등록된 디렉터리 자체도 허용한다.
        diagnostics.push(diagnostic('UNMATCHED_PATH', `미분류 프로젝트 경로: ${input}`, { input, normalized, role, hint: 'catalog의 knownPathPatterns를 확인하세요. 무관한 경로를 추가하지 마세요.' })); // 일반 intent가 있어도 경로 오류를 유지한다.
      }
    }
  }
  return { entries, diagnostics }; // 호출자가 모든 진단을 모아 fail-closed 한다.
}
