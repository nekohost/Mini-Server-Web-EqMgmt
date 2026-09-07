// [역할] 운영 거버넌스 YAML을 정규 파서로 검증하고 결정적 노드 목록과 Rule 동기화 계획을 출력한다.
// [의존성 관계] manifest.yaml, router.yaml, human-rule-map.yaml, 각 Markdown 노드, 루트 Rule.md, npm yaml 패키지에 의존한다.
// [변경 시 영향도] 출력 스키마나 검증 규칙을 바꾸면 세 제품 진입점, governance.rule-sync, README, 검증 보고서를 함께 갱신해야 한다.

// Node 내장 파일 시스템 API를 읽기 전용 검사에 사용한다.
import fs from 'node:fs';
// 경로 정규화와 상대 경로 계산에 Node 내장 path API를 사용한다.
import path from 'node:path';
// Rule 및 원본 문서 SHA-256 검증에 Node 내장 crypto API를 사용한다.
import crypto from 'node:crypto';
// ESM 모듈의 현재 파일 위치를 계산하기 위해 URL 변환 API를 사용한다.
import { fileURLToPath } from 'node:url';
// 정규 YAML 구문과 중복 키를 실제 파싱하기 위해 yaml 패키지를 사용한다.
import { parseDocument } from 'yaml';

// 현재 도구 파일의 절대 경로를 확보한다.
const TOOL_FILE = fileURLToPath(import.meta.url);
// package.json과 도구가 있는 tooling 디렉터리를 확보한다.
const TOOL_DIR = path.dirname(TOOL_FILE);
// manifest.yaml이 있는 거버넌스 루트를 확보한다.
const GOVERNANCE_ROOT = path.resolve(TOOL_DIR, '..');
// 사용자용 Rule.md와 제품별 진입점이 있는 프로젝트 루트를 확보한다.
const PROJECT_ROOT = path.resolve(GOVERNANCE_ROOT, '..');
// 고정 manifest 경로를 한 곳에서 관리한다.
const MANIFEST_FILE = path.join(GOVERNANCE_ROOT, 'manifest.yaml');
// 고정 router 경로를 한 곳에서 관리한다.
const ROUTER_FILE = path.join(GOVERNANCE_ROOT, 'router.yaml');
// 양방향 사용자 Rule 추적성 원장의 고정 경로를 관리한다.
const HUMAN_MAP_FILE = path.join(GOVERNANCE_ROOT, 'traceability', 'human-rule-map.yaml');
// 승인된 Rule 섹션별 기준선의 고정 경로를 관리한다.
const RULE_SECTION_BASELINE_FILE = path.join(GOVERNANCE_ROOT, 'traceability', 'rule-section-baseline.yaml');
// 거버넌스 도구 의존성 선언 파일 경로를 관리한다.
const TOOL_PACKAGE_FILE = path.join(TOOL_DIR, 'package.json');
// 실제 해석 버전과 무결성을 고정한 npm 잠금 파일 경로를 관리한다.
const TOOL_LOCK_FILE = path.join(TOOL_DIR, 'package-lock.json');

// 파일을 UTF-8 문자열로만 읽고 이 도구에서는 어떠한 파일 쓰기도 수행하지 않는다.
function readUtf8(filePath) {
  // 존재하는 파일의 바이트를 UTF-8로 해석하여 반환한다.
  return fs.readFileSync(filePath, 'utf8');
}

// SHA-256을 manifest와 같은 대문자 16진수 형식으로 계산한다.
function sha256(filePath) {
  // 파일 원본 바이트를 읽어 해시 입력의 인코딩 변형을 방지한다.
  const bytes = fs.readFileSync(filePath);
  // SHA-256 해시를 생성하고 대문자 16진수로 반환한다.
  return crypto.createHash('sha256').update(bytes).digest('hex').toUpperCase();
}

// 문자열을 운영체제 줄바꿈과 무관한 SHA-256 대문자 16진수로 계산한다.
function sha256Text(text) {
  // CRLF와 CR을 LF로 통일하고 마지막 공백 줄만 제거해 플랫폼 간 기준선을 안정화한다.
  const normalized = String(text).replace(/\r\n?/g, '\n').trimEnd();
  // 정규화한 UTF-8 문자열을 SHA-256으로 계산한다.
  return crypto.createHash('sha256').update(normalized, 'utf8').digest('hex').toUpperCase();
}

// 사용자용 Markdown Rule에서 코드 펜스를 제외한 번호 정책 섹션을 추출한다.
function parseRuleSections(ruleText) {
  // 줄 단위 보존을 위해 LF 기준으로 정규화한다.
  const lines = String(ruleText).replace(/\r\n?/g, '\n').split('\n');
  // 섹션 헤더 목록을 선언 순서로 수집한다.
  const headings = [];
  // 코드 펜스 내부의 # 주석을 정책 헤더로 오인하지 않도록 상태를 관리한다.
  let inFence = false;
  // 각 줄을 순서대로 검사한다.
  for (let index = 0; index < lines.length; index += 1) {
    // 앞뒤 공백을 제거한 현재 줄을 읽는다.
    const line = lines[index].trim();
    // 코드 펜스 시작·종료를 토글한다.
    if (line.startsWith('```')) {
      inFence = !inFence;
      continue;
    }
    // 코드 펜스 안의 내용은 정책 헤더 분석에서 제외한다.
    if (inFence) continue;
    // Staging Rule의 ##~###### 번호 헤더만 안정적인 섹션으로 허용한다.
    const match = line.match(/^(#{2,6})\s+(\d+(?:-\d+)*)\.\s+/);
    // 번호 헤더가 아니면 다음 줄을 검사한다.
    if (!match) continue;
    // ID, 헤더 깊이, 시작 줄을 저장한다.
    headings.push({ id: match[2], level: match[1].length, start: index });
  }
  // 중복 ID는 기준선·역추적성을 모호하게 하므로 즉시 실패한다.
  const duplicateIds = headings.map((heading) => heading.id).filter((id, index, values) => values.indexOf(id) !== index);
  if (duplicateIds.length > 0) throw new Error(`Rule 섹션 ID 중복: ${[...new Set(duplicateIds)].join(', ')}`);
  // ID별 해시와 선언 순서를 함께 보관한다.
  const sections = {};
  // 각 헤더에서 다음 헤더 직전까지를 해당 섹션의 직접 정책 블록으로 사용한다.
  for (let index = 0; index < headings.length; index += 1) {
    // 현재 헤더를 읽는다.
    const heading = headings[index];
    // 바로 다음 정책 헤더 전까지만 직접 블록으로 사용해 상위·하위 중복 변경 보고를 줄인다.
    const end = index + 1 < headings.length ? headings[index + 1].start : lines.length;
    // 헤더와 직접 본문을 포함한 안정적 해시를 저장한다.
    sections[heading.id] = sha256Text(lines.slice(heading.start, end).join('\n'));
  }
  // 결정적인 섹션 기준선 객체를 반환한다.
  return { sections, order: headings.map((heading) => heading.id) };
}

// mapping이 참조하는 Rule 섹션 해시를 집계해 노드 반영 상태 digest를 계산한다.
function mappingSourceSectionDigest(mapping, sectionHashes) {
  // 해당 노드가 참조하는 섹션 ID를 중복 없이 사전순으로 정렬한다.
  const sectionIds = [...new Set(arrayValue(mapping.human_rule_sections).map(String))].sort();
  // 모든 참조 섹션이 기준선에 있어야 node digest를 계산할 수 있다.
  for (const sectionId of sectionIds) if (!sectionHashes[sectionId]) throw new Error(`${mapping.node_id}: 기준선에 없는 Rule 섹션 ${sectionId}`);
  // 섹션 ID와 해시 쌍을 고정 형식으로 결합한다.
  const canonical = sectionIds.map((sectionId) => `${sectionId}:${sectionHashes[sectionId]}`).join('\n');
  // 결합 결과를 노드 front matter와 대조할 digest로 반환한다.
  return sha256Text(canonical);
}

// 두 Rule 섹션 기준선의 차이를 추가·삭제·내용 변경으로 분류한다.
function compareRuleSections(current, baselineSections) {
  // 기준선이 비정상이어도 호출자가 안전하게 오류 처리할 수 있도록 빈 객체로 정규화한다.
  const baseline = baselineSections && typeof baselineSections === 'object' ? baselineSections : {};
  // 현재 Rule에만 있는 ID는 새 섹션이다.
  const added = current.order.filter((sectionId) => !Object.prototype.hasOwnProperty.call(baseline, sectionId));
  // 기준선에만 있는 ID는 삭제 또는 번호 변경으로 본다.
  const removed = Object.keys(baseline).filter((sectionId) => !Object.prototype.hasOwnProperty.call(current.sections, sectionId)).sort();
  // 양쪽에 있으나 섹션 블록 hash가 다르면 내용 또는 하위 구조가 변경된 것이다.
  const changed = current.order.filter((sectionId) => Object.prototype.hasOwnProperty.call(baseline, sectionId) && baseline[sectionId] !== current.sections[sectionId]);
  // 모든 변경 ID를 중복 없이 안정적으로 정렬한다.
  const affectedSections = [...new Set([...added, ...removed, ...changed])].sort((left, right) => left.localeCompare(right, 'en'));
  // 호출자가 동일한 판정만 사용하도록 하나의 객체로 반환한다.
  return { added, removed, changed, affectedSections };
}

// Rule 현재 상태와 승인된 섹션 기준선을 비교해 변경 종류와 영향 노드를 계산한다.
function createSyncStatus(governance) {
  // manifest의 사용자 Rule 경로를 해석한다.
  const ruleFile = path.resolve(GOVERNANCE_ROOT, governance.manifest.human_reference?.path ?? '');
  // 기준선 파일이 없으면 안전하게 중지한다.
  if (!fs.existsSync(RULE_SECTION_BASELINE_FILE)) throw new Error(`Rule 섹션 기준선 파일이 없습니다: ${displayPath(RULE_SECTION_BASELINE_FILE)}`);
  // 현재 Rule 원문과 기준선 YAML을 정규 파싱한다.
  const currentRuleHash = sha256(ruleFile);
  const current = parseRuleSections(readUtf8(ruleFile));
  const baseline = parseYamlFile(RULE_SECTION_BASELINE_FILE);
  // 기준선의 섹션 해시 객체를 안전하게 정규화한다.
  const baselineSections = baseline.sections && typeof baseline.sections === 'object' ? baseline.sections : {};
  // 섹션 차이 계산은 동기화 상태와 검증에서 같은 규칙을 사용한다.
  const sectionDiff = compareRuleSections(current, baselineSections);
  // 개별 결과를 명시적 지역 변수로 꺼내 이후 영향 분석에 사용한다.
  const { added, removed, changed, affectedSections } = sectionDiff;
  // 변경 섹션을 참조하는 node mapping을 수집한다.
  const mappings = arrayValue(governance.humanMap.mappings);
  const affectedNodeIds = manifestOrder(mappings.filter((mapping) => arrayValue(mapping.human_rule_sections).map(String).some((sectionId) => affectedSections.includes(sectionId))).map((mapping) => mapping.node_id), governance.manifest);
  // mapping으로 결정할 수 없는 변경 섹션을 별도 보고한다.
  const unmappedSections = affectedSections.filter((sectionId) => !mappings.some((mapping) => arrayValue(mapping.human_rule_sections).map(String).includes(sectionId)));
  // 동기화 여부와 stale 계획 방지에 필요한 현재 Rule 해시를 반환한다.
  return {
    schemaVersion: 1,
    governanceVersion: governance.manifest.governance_version,
    baselineRuleHash: baseline.source_rule_sha256 ?? null,
    currentRuleHash,
    baselineMatchesManifest: baseline.source_rule_sha256 === governance.manifest.human_reference?.sha256,
    added,
    changed,
    removed,
    affectedSections,
    affectedNodeIds,
    unmappedSections,
    inSync: added.length === 0 && changed.length === 0 && removed.length === 0,
  };
}

// YAML 문서를 strict 모드로 파싱하고 문법 또는 중복 키 오류를 예외로 변환한다.
function parseYamlText(text, label) {
  // 정규 YAML 파서에 strict·uniqueKeys 옵션을 적용한다.
  const document = parseDocument(text, { prettyErrors: true, strict: true, uniqueKeys: true });
  // 파서 오류가 있으면 모든 메시지를 결합해 fail-closed 한다.
  if (document.errors.length > 0) {
    // 파일명과 모든 YAML 오류를 호출자에게 전달한다.
    throw new Error(`${label}: ${document.errors.map((error) => error.message).join(' | ')}`);
  }
  // 파싱된 YAML을 JavaScript 객체로 안전하게 변환한다.
  return document.toJS({ maxAliasCount: 100 });
}

// YAML 파일을 UTF-8로 읽어 정규 파싱한다.
function parseYamlFile(filePath) {
  // 표시 가능한 Staging 상대 경로를 오류 라벨로 사용한다.
  const label = displayPath(filePath);
  // 읽은 원문을 공통 YAML 파서에 전달한다.
  return parseYamlText(readUtf8(filePath), label);
}

// Markdown 노드의 첫 YAML front matter와 본문을 분리한다.
function parseMarkdownNode(filePath) {
  // 노드 전체를 UTF-8로 읽는다.
  const text = readUtf8(filePath);
  // 문서 시작의 한 쌍짜리 --- 블록만 front matter로 허용한다.
  const match = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n/);
  // front matter가 없으면 노드 ID와 부모를 검증할 수 없으므로 실패한다.
  if (!match) {
    // 정확한 파일 경로를 포함한 오류를 발생시킨다.
    throw new Error(`${displayPath(filePath)}: YAML front matter가 없습니다.`);
  }
  // front matter를 정규 YAML 파서로 파싱한다.
  const frontMatter = parseYamlText(match[1], `${displayPath(filePath)} front matter`);
  // 파싱된 메타데이터와 원문 전체를 함께 반환한다.
  return { frontMatter, text };
}

// Windows와 POSIX에서 동일한 슬래시 기반 경로를 출력한다.
function displayPath(filePath) {
  // Staging을 기준으로 상대 경로를 계산하고 역슬래시를 슬래시로 바꾼다.
  return path.relative(PROJECT_ROOT, filePath).split(path.sep).join('/');
}

// 모든 YAML 파일을 결정적 정렬 순서로 재귀 수집한다.
function listYamlFiles(directory) {
  // 현재 디렉터리에서 찾은 YAML 경로를 누적한다.
  const results = [];
  // 파일 시스템 반환 순서 차이를 없애기 위해 이름순으로 정렬한다.
  const entries = fs.readdirSync(directory, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name));
  // 정렬된 각 엔트리를 파일 또는 디렉터리로 처리한다.
  for (const entry of entries) {
    // 현재 엔트리의 절대 경로를 계산한다.
    const entryPath = path.join(directory, entry.name);
    // node_modules는 설치 산출물이므로 프로젝트 YAML 검사에서 제외한다.
    if (entry.isDirectory() && entry.name === 'node_modules') {
      // 다음 엔트리로 이동한다.
      continue;
    }
    // 하위 디렉터리는 같은 규칙으로 재귀 탐색한다.
    if (entry.isDirectory()) {
      // 재귀 결과를 현재 결과에 추가한다.
      results.push(...listYamlFiles(entryPath));
    }
    // 확장자가 .yaml인 일반 파일만 검사 대상으로 추가한다.
    if (entry.isFile() && entry.name.endsWith('.yaml')) {
      // 절대 경로를 결과에 추가한다.
      results.push(entryPath);
    }
  }
  // 결정적 순서의 YAML 파일 목록을 반환한다.
  return results;
}

// 배열 값이 아니면 빈 배열로 정규화해 선택적 YAML 키를 안전하게 처리한다.
function arrayValue(value) {
  // 배열이면 얕은 복사본을 반환하고 그 외에는 빈 배열을 반환한다.
  return Array.isArray(value) ? [...value] : [];
}

// 두 배열을 문자열 집합 기준으로 비교한다.
function sameStringSet(left, right) {
  // 중복 제거 후 정렬한 왼쪽 배열을 JSON 문자열로 직렬화한다.
  const leftValue = JSON.stringify([...new Set(arrayValue(left).map(String))].sort());
  // 중복 제거 후 정렬한 오른쪽 배열을 JSON 문자열로 직렬화한다.
  const rightValue = JSON.stringify([...new Set(arrayValue(right).map(String))].sort());
  // 두 정규화 문자열의 일치 여부를 반환한다.
  return leftValue === rightValue;
}

// YAML 경로 패턴을 전체 문자열 정규식으로 변환한다.
function globMatches(patternValue, candidateValue) {
  // 경로 구분자를 슬래시로 통일하고 선행 ./를 제거한다.
  const pattern = String(patternValue).replaceAll('\\', '/').replace(/^\.\//, '');
  // 후보 경로도 같은 방식으로 정규화한다.
  const candidate = String(candidateValue).replaceAll('\\', '/').replace(/^\.\//, '');
  // 정규식 특수문자를 먼저 이스케이프한다.
  let source = pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  // **를 임시 토큰으로 바꾸어 단일 * 처리와 구분한다.
  source = source.replaceAll('**', '__DOUBLE_STAR__');
  // 단일 *는 한 경로 구간 안의 모든 문자와 일치시킨다.
  source = source.replaceAll('*', '[^/]*');
  // **는 경로 구간을 넘어 모든 문자와 일치시킨다.
  source = source.replaceAll('__DOUBLE_STAR__', '.*');
  // 대소문자를 구분하지 않는 전체 문자열 정규식을 실행한다.
  return new RegExp(`^${source}$`, 'i').test(candidate);
}

// 명령행 옵션을 반복 가능한 intent·path·section 배열로 파싱한다.
function parseArguments(argv) {
  // 첫 번째 인수를 하위 명령으로 사용하고 없으면 help로 처리한다.
  const command = argv[0] ?? 'help';
  // 모든 반복 옵션과 플래그의 기본값을 선언한다.
  const options = { intents: [], paths: [], sections: [], expectedRuleSha: null, smallModel: false, json: true };
  // 하위 명령 다음 인수부터 한 개씩 검사한다.
  for (let index = 1; index < argv.length; index += 1) {
    // 현재 옵션 이름을 읽는다.
    const token = argv[index];
    // --intent 다음 값을 intents 배열에 추가한다.
    if (token === '--intent') {
      // 값 누락을 명시 오류로 처리한다.
      if (!argv[index + 1]) throw new Error('--intent 값이 필요합니다.');
      // 정규화한 intent를 저장한다.
      options.intents.push(argv[index + 1]);
      // 소비한 값 인덱스를 건너뛴다.
      index += 1;
      // 다음 옵션으로 이동한다.
      continue;
    }
    // --path 다음 값을 paths 배열에 추가한다.
    if (token === '--path') {
      // 값 누락을 명시 오류로 처리한다.
      if (!argv[index + 1]) throw new Error('--path 값이 필요합니다.');
      // 정규화 전 원본 경로를 저장한다.
      options.paths.push(argv[index + 1]);
      // 소비한 값 인덱스를 건너뛴다.
      index += 1;
      // 다음 옵션으로 이동한다.
      continue;
    }
    // --section 다음 값을 sections 배열에 추가한다.
    if (token === '--section') {
      // 값 누락을 명시 오류로 처리한다.
      if (!argv[index + 1]) throw new Error('--section 값이 필요합니다.');
      // Rule 섹션 번호를 문자열로 저장한다.
      options.sections.push(argv[index + 1]);
      // 소비한 값 인덱스를 건너뛴다.
      index += 1;
      // 다음 옵션으로 이동한다.
      continue;
    }
    // --expected-rule-sha는 계획 생성 또는 검증 직전 관측한 Rule 상태를 고정한다.
    if (token === '--expected-rule-sha') {
      // SHA-256 값 누락은 동시성 방어를 무력화하므로 즉시 거부한다.
      if (!argv[index + 1]) throw new Error('--expected-rule-sha 값이 필요합니다.');
      // 대소문자와 공백 차이를 없앤 SHA-256 문자열을 보관한다.
      options.expectedRuleSha = String(argv[index + 1]).trim().toUpperCase();
      // 소비한 값 인수를 건너뛴다.
      index += 1;
      // 다음 옵션으로 이동한다.
      continue;
    }
    // --small-model은 router의 작은 모델 예산을 선택한다.
    if (token === '--small-model') {
      // 작은 모델 플래그를 활성화한다.
      options.smallModel = true;
      // 다음 옵션으로 이동한다.
      continue;
    }
    // 정의되지 않은 옵션은 자동 무시하지 않고 실패한다.
    throw new Error(`알 수 없는 옵션: ${token}`);
  }
  // 중복 입력을 제거해 결정적인 인수 객체를 반환한다.
  return {
    command,
    options: {
      ...options,
      intents: [...new Set(options.intents)],
      paths: [...new Set(options.paths)],
      sections: [...new Set(options.sections)],
    },
  };
}

// manifest 순서를 보존한 노드 메타데이터와 파싱 본문을 로드한다.
function loadGovernance() {
  // manifest를 정규 YAML로 파싱한다.
  const manifest = parseYamlFile(MANIFEST_FILE);
  // router를 정규 YAML로 파싱한다.
  const router = parseYamlFile(ROUTER_FILE);
  // human map을 정규 YAML로 파싱한다.
  const humanMap = parseYamlFile(HUMAN_MAP_FILE);
  // 노드 ID별 파싱 결과를 저장한다.
  const nodes = new Map();
  // manifest 객체 삽입 순서대로 각 노드를 로드한다.
  for (const [nodeId, relativePath] of Object.entries(manifest.nodes ?? {})) {
    // manifest 상대 경로를 절대 경로로 해석한다.
    const filePath = path.resolve(GOVERNANCE_ROOT, relativePath);
    // Markdown front matter와 본문을 파싱한다.
    const parsed = parseMarkdownNode(filePath);
    // 노드 정보를 ID 키로 저장한다.
    nodes.set(nodeId, { id: nodeId, relativePath, filePath, ...parsed });
  }
  // 공통 로딩 결과를 반환한다.
  return { manifest, router, humanMap, nodes };
}

// 선택 노드와 그 모든 부모를 집합에 추가한다.
function addWithParents(nodeId, nodes, destination, visiting = new Set()) {
  // 순환 부모가 발견되면 즉시 실패한다.
  if (visiting.has(nodeId)) throw new Error(`부모 순환이 발견되었습니다: ${[...visiting, nodeId].join(' -> ')}`);
  // 이미 추가된 노드는 중복 처리하지 않는다.
  if (destination.has(nodeId)) return;
  // 존재하지 않는 노드는 fail-closed 한다.
  if (!nodes.has(nodeId)) throw new Error(`manifest에 없는 노드입니다: ${nodeId}`);
  // 현재 노드를 순환 검사 집합에 추가한다.
  visiting.add(nodeId);
  // 현재 노드의 부모 ID를 읽는다.
  const parentId = nodes.get(nodeId).frontMatter.parent;
  // 부모가 있으면 부모를 먼저 재귀 추가한다.
  if (parentId) addWithParents(parentId, nodes, destination, visiting);
  // 현재 노드를 최종 집합에 추가한다.
  destination.add(nodeId);
  // 다른 분기를 위해 현재 노드를 순환 검사 집합에서 제거한다.
  visiting.delete(nodeId);
}

// 한글을 문자 수÷4로 과소평가하지 않도록 UTF-8 바이트 기반 계획 토큰을 계산한다.
function estimateNodeTokens(node) {
  // UTF-8 3바이트를 한 계획 토큰으로 간주해 영문과 한글 혼합 문서에 보수적으로 적용한다.
  return Math.ceil(Buffer.byteLength(node.text, 'utf8') / 3);
}

// manifest 순서로 노드 ID를 정렬한다.
function manifestOrder(nodeIds, manifest) {
  // 비교용 ID 집합을 만든다.
  const selected = new Set(nodeIds);
  // manifest 노드 키 순서에서 선택된 ID만 남긴다.
  return Object.keys(manifest.nodes ?? {}).filter((nodeId) => selected.has(nodeId));
}

// context 예산을 초과하면 공통 안전 노드를 보존한 여러 pack으로 분할한다.
function buildPacks(selectedIds, baseIds, governance, budget) {
  // 공통 안전 노드와 그 부모를 base 집합에 추가한다.
  const baseSet = new Set();
  // 각 기본 노드의 부모 체인을 함께 보존한다.
  for (const nodeId of baseIds) addWithParents(nodeId, governance.nodes, baseSet);
  // 최종 선택에서 base를 제외한 노드를 manifest 순서로 구한다.
  const optionalIds = manifestOrder(selectedIds.filter((nodeId) => !baseSet.has(nodeId)), governance.manifest);
  // 생성한 pack 목록을 저장한다.
  const packs = [];
  // 현재 pack에 추가할 선택 노드를 저장한다.
  let currentOptional = [];
  // 현재 선택으로 pack 객체를 생성하는 내부 함수를 선언한다.
  const createPack = (optional) => {
    // pack마다 base와 필요한 부모를 다시 구성한다.
    const packSet = new Set(baseSet);
    // 선택 노드와 부모를 pack에 추가한다.
    for (const nodeId of optional) addWithParents(nodeId, governance.nodes, packSet);
    // manifest 순서로 정렬한다.
    const nodeIds = manifestOrder([...packSet], governance.manifest);
    // pack의 총 예상 토큰을 계산한다.
    const estimatedTokens = nodeIds.reduce((total, nodeId) => total + estimateNodeTokens(governance.nodes.get(nodeId)), 0);
    // pack 세부 정보를 반환한다.
    return { nodes: nodeIds, estimatedTokens, overBudget: estimatedTokens > budget };
  };
  // 모든 선택 노드를 순서대로 pack에 배치한다.
  for (const nodeId of optionalIds) {
    // 현재 pack에 새 노드를 넣은 후보를 만든다.
    const proposed = [...currentOptional, nodeId];
    // 후보 pack의 토큰을 계산한다.
    const proposedPack = createPack(proposed);
    // 이미 선택 노드가 있고 후보가 예산을 넘으면 현재 pack을 확정한다.
    if (currentOptional.length > 0 && proposedPack.overBudget) {
      // 현재 pack을 결과에 추가한다.
      packs.push(createPack(currentOptional));
      // 새 pack을 현재 노드부터 시작한다.
      currentOptional = [nodeId];
    } else {
      // 예산 내이면 후보를 현재 pack으로 채택한다.
      currentOptional = proposed;
    }
  }
  // 남은 선택 노드 또는 base 전용 pack을 결과에 추가한다.
  if (currentOptional.length > 0 || packs.length === 0) packs.push(createPack(currentOptional));
  // 결정적 pack 목록을 반환한다.
  return packs;
}

// router 규칙과 입력 intent·path·section으로 실제 로딩 노드를 계산한다.
function createContext(governance, options) {
  // route 매칭과 동적 섹션 오류를 누적한다.
  const errors = [];
  // 매칭된 route ID를 입력 순서대로 보존한다.
  const matchedRoutes = [];
  // route가 요구하는 비노드 입력 파일을 누적한다.
  const requiredInputs = new Set();
  // 기본 노드부터 선택 집합에 추가한다.
  const selected = new Set();
  // router default_load의 부모 체인을 포함한다.
  for (const nodeId of arrayValue(governance.router.default_load)) addWithParents(nodeId, governance.nodes, selected);
  // 각 supplied intent가 실제 intent route에 소비되었는지 추적한다.
  const matchedIntents = new Set();
  // 각 supplied path가 실제 route에 소비되었는지 추적한다.
  const matchedPaths = new Set();
  // router의 모든 규칙을 선언 순서대로 검사한다.
  for (const rule of arrayValue(governance.router.rules)) {
    // 현재 route가 선언한 intent 목록을 정규화한다.
    const routeIntents = arrayValue(rule.match?.intents).map(String);
    // 현재 route가 선언한 path 패턴 목록을 정규화한다.
    const routePaths = arrayValue(rule.match?.paths).map(String);
    // intent 조건이 없으면 true이고, 있으면 입력 intent 중 하나가 일치해야 한다.
    const intentMatches = routeIntents.length === 0 || options.intents.some((intent) => routeIntents.includes(intent));
    // path 조건이 없으면 true이고, 있으면 입력 path 중 하나가 패턴과 일치해야 한다.
    const pathMatches = routePaths.length === 0 || options.paths.some((candidate) => routePaths.some((pattern) => globMatches(pattern, candidate)));
    // 두 조건을 모두 만족하지 않으면 현재 route를 건너뛴다.
    if (!intentMatches || !pathMatches) continue;
    // 매칭된 route ID를 기록한다.
    matchedRoutes.push(rule.id);
    // 현재 route가 소비한 supplied intent를 기록한다.
    for (const intent of options.intents) if (routeIntents.includes(intent)) matchedIntents.add(intent);
    // 경로 조건이 없는 매칭 route는 모든 supplied path를 처리한 것으로 기록한다.
    if (routePaths.length === 0) for (const candidate of options.paths) matchedPaths.add(candidate);
    // 경로 조건이 있는 route는 실제 일치한 path만 기록한다.
    for (const candidate of options.paths) if (routePaths.some((pattern) => globMatches(pattern, candidate))) matchedPaths.add(candidate);
    // route의 고정 노드와 부모를 선택 집합에 추가한다.
    for (const nodeId of arrayValue(rule.load)) addWithParents(nodeId, governance.nodes, selected);
    // route가 요구하는 입력 파일을 출력에 추가한다.
    for (const inputPath of arrayValue(rule.required_inputs)) requiredInputs.add(inputPath);
    // 변경 섹션 필수 route에서 섹션이 없으면 fail-closed 오류를 추가한다.
    if (rule.changed_rule_sections_required && options.sections.length === 0) errors.push(`${rule.id}: --section이 필요합니다.`);
    // dynamic_load가 선언된 route는 human map에서 섹션 대상 노드를 추가한다.
    if (rule.dynamic_load && options.sections.length > 0) {
      // 각 변경 섹션을 독립적으로 해석한다.
      for (const section of options.sections) {
        // 해당 섹션을 역참조하는 모든 mapping을 찾는다.
        const mappings = arrayValue(governance.humanMap.mappings).filter((mapping) => arrayValue(mapping.human_rule_sections).map(String).includes(section));
        // 미등록 섹션은 자동 추측하지 않고 오류를 추가한다.
        if (mappings.length === 0) {
          // 정확한 누락 섹션을 보고한다.
          errors.push(`${rule.id}: human-rule-map에 없는 섹션 ${section}`);
          // 다음 섹션으로 이동한다.
          continue;
        }
        // 모든 역참조 대상 노드와 부모를 선택 집합에 추가한다.
        for (const mapping of mappings) addWithParents(mapping.node_id, governance.nodes, selected);
      }
    }
  }
  // route가 하나도 없으면 기본 노드만으로 성공 처리하지 않는다.
  if (matchedRoutes.length === 0) errors.push('일치하는 route가 없습니다.');
  // 정책이 요구하면 모든 supplied intent가 적어도 하나의 intent route에 일치해야 한다.
  if (governance.router.routing_policy?.require_all_supplied_intents_matched) {
    // 소비되지 않은 intent를 각각 오류로 보고한다.
    for (const intent of options.intents) if (!matchedIntents.has(intent)) errors.push(`미등록 또는 미매칭 intent: ${intent}`);
  }
  // 정책이 요구하면 모든 supplied path가 적어도 하나의 route에 일치해야 한다.
  if (governance.router.routing_policy?.require_all_supplied_paths_matched) {
    // 소비되지 않은 path를 각각 오류로 보고한다.
    for (const candidate of options.paths) if (!matchedPaths.has(candidate)) errors.push(`미매칭 path: ${candidate}`);
  }
  // 오류가 있으면 context pack을 생성하지 않고 예외로 중지한다.
  if (errors.length > 0) throw new Error(errors.join(' | '));
  // 선택된 모든 노드를 manifest 순서로 정렬한다.
  const nodes = manifestOrder([...selected], governance.manifest);
  // 모델 유형에 따른 토큰 예산을 선택한다.
  const budget = Number(options.smallModel ? governance.router.routing_policy?.max_small_model_context_tokens : governance.router.routing_policy?.max_default_context_tokens);
  // 항상 보존할 default_load를 base로 pack을 분할한다.
  const packs = buildPacks(nodes, arrayValue(governance.router.default_load), governance, budget);
  // 단일 노드조차 예산에 들어가지 않는 pack을 찾는다.
  const overBudgetPacks = packs.map((pack, index) => ({ ...pack, index: index + 1 })).filter((pack) => pack.overBudget);
  // 예산을 지킬 수 없으면 규칙을 버리지 않고 실패한다.
  if (overBudgetPacks.length > 0) throw new Error(`분할 후에도 context 예산을 초과합니다: pack ${overBudgetPacks.map((pack) => pack.index).join(', ')}`);
  // 모델이 그대로 소비할 결정적 JSON 구조를 반환한다.
  return {
    schemaVersion: 1,
    governanceVersion: governance.manifest.governance_version,
    inputs: { intents: options.intents, paths: options.paths, sections: options.sections, smallModel: options.smallModel },
    matchedRoutes,
    requiredInputs: [...requiredInputs],
    budget,
    tokenEstimator: governance.router.routing_policy?.token_estimator,
    tokenBudgetIsModelAgnosticEstimate: Boolean(governance.router.routing_policy?.token_budget_is_model_agnostic_estimate),
    splitRequired: packs.length > 1,
    nodes,
    packs,
  };
}

// Rule 섹션에서 대상 노드와 필수 동기화 파일을 산출한다.
function createSyncPlan(governance, options) {
  // Rule 동기화에는 적어도 한 개 섹션이 필요하다.
  if (options.sections.length === 0) throw new Error('sync-plan에는 --section이 하나 이상 필요합니다.');
  // 계획이 오래된 Rule 상태에 적용되는 것을 막기 위해 관측 hash를 필수로 요구한다.
  if (!options.expectedRuleSha) throw new Error('sync-plan에는 sync-status의 currentRuleHash를 --expected-rule-sha로 지정해야 합니다.');
  // 현재 Rule과 승인된 섹션 기준선의 차이를 먼저 계산한다.
  const syncStatus = createSyncStatus(governance);
  // 계획 생성 시점에도 Rule이 바뀌었으면 새 상태를 다시 확인하도록 중단한다.
  if (options.expectedRuleSha !== syncStatus.currentRuleHash) throw new Error(`Rule SHA-256이 변경되었습니다. expected=${options.expectedRuleSha} actual=${syncStatus.currentRuleHash}`);
  // 기준선 불일치가 있으면 상태가 보고한 모든 변경 섹션을 빠짐없이 계획 대상으로 받아야 한다.
  if (!syncStatus.inSync && !sameStringSet(options.sections, syncStatus.affectedSections)) throw new Error(`sync-plan 섹션은 sync-status의 전체 변경 목록과 일치해야 합니다. expected=${syncStatus.affectedSections.join(', ')}`);
  // 섹션별 mapping을 누적한다.
  const targetMappings = [];
  // 각 입력 섹션을 human map과 대조한다.
  for (const section of options.sections) {
    // 현재 섹션을 참조하는 모든 mapping을 찾는다.
    const mappings = arrayValue(governance.humanMap.mappings).filter((mapping) => arrayValue(mapping.human_rule_sections).map(String).includes(section));
    // 미등록 섹션은 의미 추론 없이 실패한다.
    if (mappings.length === 0) throw new Error(`human-rule-map에 없는 Rule 섹션입니다: ${section}`);
    // 중복 mapping을 제거하면서 대상에 추가한다.
    for (const mapping of mappings) if (!targetMappings.some((item) => item.node_id === mapping.node_id)) targetMappings.push(mapping);
  }
  // manifest 순서로 대상 노드 ID를 정렬한다.
  const targetNodeIds = manifestOrder(targetMappings.map((mapping) => mapping.node_id), governance.manifest);
  // 대상 노드의 실제 상대 경로를 구성한다.
  const targetNodes = targetNodeIds.map((nodeId) => ({ nodeId, path: governance.manifest.nodes[nodeId] }));
  // 항상 함께 갱신해야 하는 파일과 대상 노드를 결합한다.
  const requiredFiles = [
    '../Rule.md',
    ...targetNodes.map((node) => node.path),
    'traceability/human-rule-map.yaml',
    'traceability/rule-section-baseline.yaml',
    'manifest.yaml',
  ];
  // AI가 적용할 고정 동기화 계획을 반환한다.
  return {
    schemaVersion: 1,
    governanceVersion: governance.manifest.governance_version,
    baseRuleHash: syncStatus.currentRuleHash,
    sections: options.sections,
    syncStatus: {
      added: syncStatus.added,
      changed: syncStatus.changed,
      removed: syncStatus.removed,
      unmappedSections: syncStatus.unmappedSections,
    },
    targetNodes,
    sectionHashUpdates: Object.fromEntries(options.sections.map((section) => [section, parseRuleSections(readUtf8(path.resolve(GOVERNANCE_ROOT, governance.manifest.human_reference?.path ?? ''))).sections[section] ?? null])),
    nodeSourceDigestUpdates: Object.fromEntries(targetMappings.map((mapping) => [mapping.node_id, mappingSourceSectionDigest(mapping, parseRuleSections(readUtf8(path.resolve(GOVERNANCE_ROOT, governance.manifest.human_reference?.path ?? ''))).sections)])),
    requiredFiles: [...new Set(requiredFiles)],
    mandatoryActions: [
      '사용자 Rule 변경 의미를 대상 노드 본문에 투영',
      '대상 노드 human_rule_sections와 source_human 갱신',
      'human-rule-map node↔section↔HUMAN ID 갱신',
      'target node source_section_digest를 nodeSourceDigestUpdates 값으로 갱신',
      'traceability/rule-section-baseline.yaml의 섹션 hash와 source_rule_sha256 갱신',
      'manifest human_reference.sha256와 governance_version 갱신',
      '새 노드일 때만 manifest nodes 등록',
      '새 작업 유형 또는 경로일 때만 router 갱신',
      'Staging/에서 node .agent-governance/tooling/governance-tool.mjs validate --expected-rule-sha <baseRuleHash> 오류 0건 확인',
    ],
    validationCommand: `node .agent-governance/tooling/governance-tool.mjs validate --expected-rule-sha ${syncStatus.currentRuleHash}`,
  };
}

// 현재 Rule과 human map으로 승인 가능한 기준선 초안을 읽기 전용으로 계산한다.
function createSnapshot(governance) {
  // manifest가 가리키는 사용자 Rule 파일을 해석한다.
  const ruleFile = path.resolve(GOVERNANCE_ROOT, governance.manifest.human_reference?.path ?? '');
  // 현재 Rule의 섹션 hash와 원본 hash를 계산한다.
  const parsedRule = parseRuleSections(readUtf8(ruleFile));
  const ruleHash = sha256(ruleFile);
  // 모든 매핑 노드에 대해 해당 섹션 집합의 기대 digest를 계산한다.
  const nodeSourceDigests = Object.fromEntries(arrayValue(governance.humanMap.mappings).map((mapping) => [mapping.node_id, mappingSourceSectionDigest(mapping, parsedRule.sections)]));
  // 사람 또는 AI가 검토한 뒤 YAML 기준선과 node front matter에 반영할 값만 반환한다.
  return {
    schemaVersion: 1,
    governanceVersion: governance.manifest.governance_version,
    sourceRuleHash: ruleHash,
    sectionBaseline: { schema_version: 1, source_rule_sha256: ruleHash, sections: parsedRule.sections },
    nodeSourceDigests,
  };
}

// AI가 자연어 요청을 정규화할 때 참고할 수 있도록 전체 route 카탈로그를 출력한다.
function createCatalog(governance) {
  // router 규칙을 작은 모델이 비교하기 쉬운 고정 필드로 축약한다.
  const routes = arrayValue(governance.router.rules).map((rule) => ({
    // route 고유 ID를 보존한다.
    id: rule.id,
    // route가 인식하는 모든 intent를 보존한다.
    intents: arrayValue(rule.match?.intents),
    // route가 인식하는 모든 path 패턴을 보존한다.
    paths: arrayValue(rule.match?.paths),
    // route가 로드하는 고정 노드 목록을 보존한다.
    load: arrayValue(rule.load),
    // Rule 변경 섹션 요구 여부를 명시한다.
    changedRuleSectionsRequired: Boolean(rule.changed_rule_sections_required),
  }));
  // 중복을 제거한 지원 intent 목록을 정렬한다.
  const knownIntents = [...new Set(routes.flatMap((route) => route.intents))].sort();
  // 중복을 제거한 path 패턴 목록을 정렬한다.
  const knownPathPatterns = [...new Set(routes.flatMap((route) => route.paths))].sort();
  // AI가 입력 전 대조할 카탈로그를 반환한다.
  return {
    schemaVersion: 1,
    governanceVersion: governance.manifest.governance_version,
    knownIntents,
    knownPathPatterns,
    routes,
    instruction: '사용자 요청을 하나로 축약하지 말고 관련 intent와 path를 모두 선택한다. 목록에 없거나 판단할 수 없으면 fail-closed 한다.',
  };
}

// 전체 운영 거버넌스의 실제 파싱과 양방향 불변식을 검사한다.
function validateGovernance(governance, options = {}) {
  // 차단 오류를 누적한다.
  const errors = [];
  // 비차단 주의사항을 누적한다.
  const warnings = [];
  // package.json을 JSON 표준 파서로 읽는다.
  const toolPackage = JSON.parse(readUtf8(TOOL_PACKAGE_FILE));
  // package-lock.json을 JSON 표준 파서로 읽는다.
  const toolLock = JSON.parse(readUtf8(TOOL_LOCK_FILE));
  // package.json에 선언된 yaml 버전을 읽는다.
  const configuredYamlVersion = toolPackage.dependencies?.yaml;
  // 잠금 파일에 고정된 yaml 실제 버전을 읽는다.
  const lockedYamlVersion = toolLock.packages?.['node_modules/yaml']?.version;
  // 설치된 yaml package.json의 경로를 계산한다.
  const installedYamlPackageFile = path.join(TOOL_DIR, 'node_modules', 'yaml', 'package.json');
  // 설치된 패키지 버전을 런타임 실측한다.
  const installedYamlVersion = fs.existsSync(installedYamlPackageFile) ? JSON.parse(readUtf8(installedYamlPackageFile)).version : null;
  // 선언 버전과 잠금 버전이 다르면 재현 가능한 파싱을 보장할 수 없다.
  if (configuredYamlVersion !== lockedYamlVersion) errors.push(`yaml 선언·잠금 버전 불일치: configured=${configuredYamlVersion} locked=${lockedYamlVersion}`);
  // 현재 설치 버전과 잠금 버전이 다르면 실제 검증기가 잠금 상태와 다르다.
  if (installedYamlVersion !== lockedYamlVersion) errors.push(`yaml 설치·잠금 버전 불일치: installed=${installedYamlVersion} locked=${lockedYamlVersion}`);
  // 정규 YAML 파싱에 성공한 파일을 기록한다.
  const parsedYamlFiles = [];
  // 모든 운영 거버넌스 YAML을 실제 파싱한다.
  for (const yamlFile of listYamlFiles(GOVERNANCE_ROOT)) {
    // 각 YAML 파일을 strict 모드로 파싱한다.
    parseYamlFile(yamlFile);
    // 성공한 상대 경로를 결과에 추가한다.
    parsedYamlFiles.push(displayPath(yamlFile));
  }
  // manifest 노드 순서와 경로를 추출한다.
  const manifestEntries = Object.entries(governance.manifest.nodes ?? {});
  // human map의 mapping 목록을 추출한다.
  const mappings = arrayValue(governance.humanMap.mappings);
  // 중복 node_id mapping을 찾기 위한 집합을 만든다.
  const mappedIds = new Set();
  // 모든 mapping을 manifest와 실제 노드에 대조한다.
  for (const mapping of mappings) {
    // node_id 중복은 양방향 원장의 모호성이므로 오류다.
    if (mappedIds.has(mapping.node_id)) errors.push(`human map 중복 node_id: ${mapping.node_id}`);
    // 현재 mapping ID를 기록한다.
    mappedIds.add(mapping.node_id);
    // manifest에 없는 mapping은 오류다.
    if (!governance.nodes.has(mapping.node_id)) {
      // 누락 ID를 보고한다.
      errors.push(`human map의 미등록 노드: ${mapping.node_id}`);
      // 실제 노드 대조를 건너뛴다.
      continue;
    }
    // 실제 manifest 상대 경로를 읽는다.
    const node = governance.nodes.get(mapping.node_id);
    // map과 manifest의 노드 경로를 대조한다.
    if (mapping.node_path !== node.relativePath) errors.push(`node_path 불일치: ${mapping.node_id}`);
    // map과 front matter의 human_rule_sections를 집합으로 대조한다.
    if (!sameStringSet(mapping.human_rule_sections, node.frontMatter.human_rule_sections)) errors.push(`human_rule_sections 불일치: ${mapping.node_id}`);
    // map과 front matter의 source_rules를 대조한다.
    if (!sameStringSet(mapping.source_rules, node.frontMatter.source_rules)) errors.push(`source_rules 불일치: ${mapping.node_id}`);
    // map과 front matter의 source_validations를 대조한다.
    if (!sameStringSet(mapping.source_validations, node.frontMatter.source_validations)) errors.push(`source_validations 불일치: ${mapping.node_id}`);
    // map과 front matter의 source_entrypoints를 대조한다.
    if (!sameStringSet(mapping.source_entrypoints, node.frontMatter.source_entrypoints)) errors.push(`source_entrypoints 불일치: ${mapping.node_id}`);
    // front matter에 source_human이 있으면 map과 대조한다.
    if (node.frontMatter.source_human !== undefined && !sameStringSet(mapping.source_human, node.frontMatter.source_human)) errors.push(`source_human 불일치: ${mapping.node_id}`);
    // Rule 섹션 기준선을 읽을 수 있을 때에는 노드가 어느 섹션 원문 상태를 반영했는지도 검증한다.
    if (fs.existsSync(RULE_SECTION_BASELINE_FILE)) {
      // 승인된 기준선 문서를 정규 파싱한다.
      const sectionBaseline = parseYamlFile(RULE_SECTION_BASELINE_FILE);
      // map의 모든 섹션 hash로 기대 digest를 계산한다.
      try {
        // front matter에 저장된 digest가 정확히 일치해야 Rule 반영 누락을 차단한다.
        if (node.frontMatter.source_section_digest !== mappingSourceSectionDigest(mapping, sectionBaseline.sections)) errors.push(`source_section_digest 불일치: ${mapping.node_id}`);
      } catch (error) {
        // 기준선에서 사라진 매핑 섹션도 검증 실패로 누적한다.
        errors.push(error instanceof Error ? error.message : String(error));
      }
    }
  }
  // 모든 manifest 노드를 front matter와 map에 대조한다.
  for (const [nodeId, relativePath] of manifestEntries) {
    // 파싱된 노드를 가져온다.
    const node = governance.nodes.get(nodeId);
    // front matter ID가 manifest 키와 다르면 오류다.
    if (node.frontMatter.id !== nodeId) errors.push(`manifest↔front matter ID 불일치: ${nodeId}`);
    // manifest 상대 경로가 실제 로드 경로와 다른 경우를 차단한다.
    if (node.relativePath !== relativePath) errors.push(`manifest 경로 불일치: ${nodeId}`);
    // parent가 있으면 manifest 등록 여부를 확인한다.
    if (node.frontMatter.parent && !governance.nodes.has(node.frontMatter.parent)) errors.push(`존재하지 않는 parent: ${nodeId} -> ${node.frontMatter.parent}`);
    // 각 manifest 노드는 human map에 정확히 한 번 존재해야 한다.
    if (!mappedIds.has(nodeId)) errors.push(`human map 누락 노드: ${nodeId}`);
  }
  // 모든 노드에 대해 부모 순환을 실제 탐색한다.
  for (const [nodeId] of manifestEntries) addWithParents(nodeId, governance.nodes, new Set());
  // router가 직접 로드하는 모든 노드 ID를 수집한다.
  const routerNodeIds = new Set(arrayValue(governance.router.default_load));
  // 각 route load를 수집한다.
  for (const rule of arrayValue(governance.router.rules)) for (const nodeId of arrayValue(rule.load)) routerNodeIds.add(nodeId);
  // 미등록 router 노드는 fail-closed 오류다.
  for (const nodeId of routerNodeIds) if (!governance.nodes.has(nodeId)) errors.push(`router의 미등록 노드: ${nodeId}`);
  // 사용자용 Rule 파일의 실제 경로를 manifest 기준으로 해석한다.
  const ruleFile = path.resolve(GOVERNANCE_ROOT, governance.manifest.human_reference?.path ?? '');
  // manifest가 기준선 경로까지 선언해야 섹션 동기화 계약이 명시된다.
  if (governance.manifest.human_reference?.section_baseline !== 'traceability/rule-section-baseline.yaml') errors.push('manifest human_reference.section_baseline 불일치');
  // Rule 파일이 없으면 나머지 포인터 검사를 중지한다.
  if (!fs.existsSync(ruleFile)) {
    // 누락 경로를 오류로 기록한다.
    errors.push(`manifest human_reference 파일 누락: ${displayPath(ruleFile)}`);
  } else {
    // 실제 Rule SHA-256을 계산한다.
    const actualRuleHash = sha256(ruleFile);
    // manifest 해시와 실제 해시를 대조한다.
    if (actualRuleHash !== governance.manifest.human_reference?.sha256) errors.push(`Rule SHA-256 불일치: manifest=${governance.manifest.human_reference?.sha256} actual=${actualRuleHash}`);
    // 계획 생성에 사용한 Rule hash가 다르면 동시 수정 또는 오래된 계획으로 판단한다.
    if (options.expectedRuleSha && options.expectedRuleSha !== actualRuleHash) errors.push(`expected Rule SHA-256 불일치: expected=${options.expectedRuleSha} actual=${actualRuleHash}`);
    // 섹션 기준선이 없으면 추가·삭제·번호 변경을 안전하게 탐지할 수 없다.
    if (!fs.existsSync(RULE_SECTION_BASELINE_FILE)) {
      // 기준선 부재를 명확한 차단 오류로 기록한다.
      errors.push(`Rule 섹션 기준선 파일 누락: ${displayPath(RULE_SECTION_BASELINE_FILE)}`);
    } else {
      // 기준선과 현재 Rule의 차이를 계산한다.
      const syncStatus = createSyncStatus(governance);
      // 기준선 자체가 manifest Rule 원본을 가리켜야 한다.
      if (!syncStatus.baselineMatchesManifest) errors.push(`Rule 섹션 기준선 source_rule_sha256 불일치: baseline=${syncStatus.baselineRuleHash} manifest=${governance.manifest.human_reference?.sha256}`);
      // 어떤 변경도 남아 있으면 노드·map·기준선 갱신 전에는 검증을 통과시키지 않는다.
      if (!syncStatus.inSync) errors.push(`Rule 섹션 기준선 불일치: added=${syncStatus.added.join(', ') || '-'} changed=${syncStatus.changed.join(', ') || '-'} removed=${syncStatus.removed.join(', ') || '-'}`);
      // 매핑 없는 새 정책은 AI가 의미상 소유 노드를 결정할 때까지 자동 적용하지 않는다.
      if (syncStatus.unmappedSections.length > 0) errors.push(`매핑되지 않은 Rule 변경 섹션: ${syncStatus.unmappedSections.join(', ')}`);
    }
    // Rule 원문을 읽는다.
    const ruleText = readUtf8(ruleFile);
    // Markdown 코드 펜스 개수를 검사한다.
    const fenceCount = (ruleText.match(/^```/gm) ?? []).length;
    // 홀수 펜스는 문서 구조 오류다.
    if (fenceCount % 2 !== 0) errors.push(`Rule Markdown 코드 펜스 불균형: ${fenceCount}`);
    // Rule의 모든 포인터 인용 줄을 수집한다.
    const pointerLines = ruleText.split(/\r?\n/).filter((line) => line.includes('경로: .agent-governance/'));
    // 각 포인터 경로와 노드 ID를 manifest에 대조한다.
    for (const line of pointerLines) {
      // 포인터의 실제 경로 값을 추출한다.
      const pathMatch = line.match(/경로:\s*([^\]|]+)/);
      // 경로를 추출하지 못하면 포인터 형식 오류다.
      if (!pathMatch) {
        // 원문 줄을 오류에 포함한다.
        errors.push(`Rule 포인터 경로 파싱 실패: ${line}`);
        // 다음 포인터로 이동한다.
        continue;
      }
      // 프로젝트 루트 기준 절대 파일 경로를 계산한다.
      const pointerFile = path.resolve(PROJECT_ROOT, pathMatch[1].trim());
      // 포인터 파일 존재 여부를 확인한다.
      if (!fs.existsSync(pointerFile)) errors.push(`Rule 포인터 대상 누락: ${pathMatch[1].trim()}`);
      // 주 노드·보조 노드·노드 필드의 모든 값을 추출한다.
      const nodeFieldPattern = /(?:주 노드|보조 노드|노드):\s*([^|]+)/g;
      // 같은 포인터 줄에서 여러 노드 필드를 반복 처리한다.
      for (const match of line.matchAll(nodeFieldPattern)) {
        // 쉼표로 구분된 각 노드 ID를 정규화한다.
        for (const nodeId of match[1].split(',').map((value) => value.trim()).filter(Boolean)) {
          // manifest 미등록 노드는 오류다.
          if (!governance.nodes.has(nodeId)) errors.push(`Rule 포인터의 미등록 노드: ${nodeId}`);
        }
      }
    }
    // 필수 백업 서버 정책이 Rule에 존재하는지 확인한다.
    if (!ruleText.includes('HUMAN-2.6-BACKUP') || !ruleText.includes('192.168.0.24')) errors.push('백업 서버 사용자 정책이 Rule에 없습니다.');
    // DB 스키마 보류 HUMAN ID가 Rule에 존재하는지 확인한다.
    if (!ruleText.includes('HUMAN-3.1.1-DB-DEFERRAL')) errors.push('DB 스키마 보류 정책이 Rule에 없습니다.');
    // 결정적 Rule 동기화 정책이 Rule에 존재하는지 확인한다.
    if (!ruleText.includes('HUMAN-11.7')) errors.push('결정적 Rule 동기화 정책이 Rule에 없습니다.');
  }
  // manifest source_documents의 실제 경로와 해시를 모두 검사한다.
  for (const source of arrayValue(governance.manifest.source_documents)) {
    // manifest 위치 기준으로 원본 절대 경로를 계산한다.
    const sourceFile = path.resolve(GOVERNANCE_ROOT, source.path);
    // 원본 파일 누락을 오류로 기록한다.
    if (!fs.existsSync(sourceFile)) {
      // 누락 경로를 표시한다.
      errors.push(`source_documents 파일 누락: ${source.path}`);
      // 해시 계산을 건너뛴다.
      continue;
    }
    // 원본 해시를 manifest 기준선과 대조한다.
    if (sha256(sourceFile) !== source.sha256) errors.push(`source_documents 해시 불일치: ${source.path}`);
  }
  // data-model 노드가 DB 보류 정책을 실제로 포함하는지 확인한다.
  const dataModel = governance.nodes.get('engineering.data-model');
  // 필수 ID와 제안 번호가 모두 있어야 한다.
  if (!dataModel?.text.includes('HUMAN-3.1.1-DB-DEFERRAL') || !dataModel?.text.includes('[제안-013]')) errors.push('engineering.data-model의 DB 보류 투영이 없습니다.');
  // Rule sync 노드가 manifest에 등록되었는지 확인한다.
  if (!governance.nodes.has('governance.rule-sync')) errors.push('governance.rule-sync 노드가 없습니다.');
  // router가 실제 context loader를 선언하는지 확인한다.
  if (governance.router.routing_policy?.context_loader !== 'tooling/governance-tool.mjs') errors.push('router context_loader가 거버넌스 도구를 가리키지 않습니다.');
  // 운영 manifest와 사용자 Rule 원장의 활성 상태를 검사한다.
  if (governance.manifest.status !== 'active') errors.push('manifest가 active 상태가 아닙니다.');
  if (governance.manifest.replaces_root_sources !== true) errors.push('manifest가 루트 거버넌스 활성화를 선언하지 않았습니다.');
  if (governance.humanMap.status !== 'active') errors.push('human-rule-map이 active 상태가 아닙니다.');
  // Codex capability를 정규 YAML로 읽는다.
  const codexCapability = parseYamlFile(path.join(GOVERNANCE_ROOT, governance.manifest.capabilities?.codex ?? ''));
  // 활성 프로파일이 실측이 필요한 속성을 과장하지 않는지 확인한다.
  if (codexCapability.status !== 'active-profile-runtime-verification-required') errors.push('Codex capability가 활성 runtime verification 상태가 아닙니다.');
  // IDE Undo를 검증된 속성으로 선언하면 안 된다.
  if (arrayValue(codexCapability.file_edit?.verified_properties).includes('ide-undo-compatible')) errors.push('Codex IDE Undo가 검증된 속성으로 잘못 선언되었습니다.');
  // 실제 parser와 lockfile 경로가 존재하는지 확인한다.
  for (const toolingPath of [governance.manifest.tooling?.package, governance.manifest.tooling?.lockfile, governance.manifest.tooling?.command]) {
    // 값 누락 또는 파일 누락을 오류로 처리한다.
    if (!toolingPath || !fs.existsSync(path.resolve(GOVERNANCE_ROOT, toolingPath))) errors.push(`tooling 파일 누락: ${toolingPath ?? '<미정>'}`);
  }
  // 세 플랫폼 진입점이 동일한 프로젝트 루트 동기화 명령을 안내하는지 정적 smoke 검사한다.
  const bootstrapFiles = ['AGENTS.md', 'GEMINI.md', 'CLAUDE.md'];
  // 각 진입점의 존재와 필수 명령 문자열을 확인한다.
  for (const bootstrapFile of bootstrapFiles) {
    // 프로젝트 루트의 플랫폼별 진입점 경로를 계산한다.
    const bootstrapPath = path.join(PROJECT_ROOT, bootstrapFile);
    // 누락된 진입점은 플랫폼별 절차 편차를 만들므로 차단한다.
    if (!fs.existsSync(bootstrapPath)) {
      // 누락 파일명을 오류에 기록한다.
      errors.push(`플랫폼 bootstrap 파일 누락: ${bootstrapFile}`);
      // 원문 검사는 건너뛴다.
      continue;
    }
    // 진입점 원문을 한 번만 읽는다.
    const bootstrapText = readUtf8(bootstrapPath);
    // Rule 변경의 세 읽기 전용 명령과 stale hash 방어가 모두 안내되어야 한다.
    for (const requiredText of ['sync-status', 'sync-plan', '--expected-rule-sha']) if (!bootstrapText.includes(requiredText)) errors.push(`플랫폼 bootstrap 동기화 절차 누락: ${bootstrapFile} -> ${requiredText}`);
  }
  // Node 18 미만에서는 고정 ESM 도구 실행을 지원하지 않으므로 현재 런타임도 점검한다.
  const nodeMajorVersion = Number.parseInt(process.versions.node.split('.')[0], 10);
  // 지원하지 않는 런타임은 도구 결과를 신뢰할 수 없으므로 차단한다.
  if (!Number.isInteger(nodeMajorVersion) || nodeMajorVersion < 18) errors.push(`Node 런타임 버전 미지원: ${process.versions.node}`);
  // 과거 qualitative 보고서가 최신 근거로 오인되지 않도록 상태 표기를 확인한다.
  const historicalReport = path.join(PROJECT_ROOT, 'qualitative_validation_report.md');
  // 보고서가 존재하지만 historical 표기가 없으면 경고한다.
  if (fs.existsSync(historicalReport) && !readUtf8(historicalReport).includes('과거 검증 기록')) warnings.push('qualitative_validation_report.md에 과거 검증 기록 표기가 필요합니다.');
  // 검증 요약과 세부 결과를 반환한다.
  return {
    schemaVersion: 1,
    governanceVersion: governance.manifest.governance_version,
    platformBootstrap: { files: bootstrapFiles, nodeVersion: process.versions.node, nodeSupported: Number.isInteger(nodeMajorVersion) && nodeMajorVersion >= 18 },
    parser: { package: 'yaml', configuredVersion: configuredYamlVersion, lockedVersion: lockedYamlVersion, installedVersion: installedYamlVersion, filesParsed: parsedYamlFiles.length, files: parsedYamlFiles },
    counts: { manifestNodes: manifestEntries.length, humanMapNodes: mappings.length, errors: errors.length, warnings: warnings.length },
    errors,
    warnings,
    status: errors.length === 0 ? 'pass' : 'fail',
  };
}

// 사용법을 짧은 문자열로 반환한다.
function helpText() {
  // 세 하위 명령과 반복 옵션 예시를 제공한다.
  return [
    'Usage:',
    '  node .agent-governance/tooling/governance-tool.mjs validate [--expected-rule-sha <sha256>]',
    '  node .agent-governance/tooling/governance-tool.mjs catalog',
    '  node .agent-governance/tooling/governance-tool.mjs context --intent <id> [--intent <id>] --path <path> [--path <path>] [--section <n>] [--small-model]',
    '  node .agent-governance/tooling/governance-tool.mjs sync-status',
    '  node .agent-governance/tooling/governance-tool.mjs sync-plan --expected-rule-sha <sha256> --section <n> [--section <n>]',
    '  node .agent-governance/tooling/governance-tool.mjs snapshot',
    '',
    'The tool is read-only and writes JSON to stdout.',
  ].join('\n');
}

// 객체 결과를 안정적인 들여쓰기 JSON으로 표준 출력한다.
function printJson(value) {
  // 유니코드를 보존한 JSON을 출력한다.
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

// 명령행 진입점을 실행하고 모든 오류를 JSON과 비정상 종료 코드로 변환한다.
function main() {
  // 현재 프로세스 인수를 파싱한다.
  const { command, options } = parseArguments(process.argv.slice(2));
  // help 요청은 파일을 읽지 않고 사용법만 출력한다.
  if (command === 'help' || command === '--help' || command === '-h') {
    // 도움말을 표준 출력한다.
    process.stdout.write(`${helpText()}\n`);
    // 정상 종료한다.
    return;
  }
  // 모든 실행 명령에 필요한 거버넌스 파일을 정규 파싱한다.
  const governance = loadGovernance();
  // validate 명령은 전체 불변식 검사를 수행한다.
  if (command === 'validate') {
    // 검증 결과를 계산한다.
    const result = validateGovernance(governance, options);
    // 결과 JSON을 출력한다.
    printJson(result);
    // 오류가 있으면 비정상 종료 코드를 설정한다.
    if (result.status !== 'pass') process.exitCode = 1;
    // 다른 명령 분기로 이동하지 않는다.
    return;
  }
  // catalog 명령은 지원 intent·path·route 전체를 결정적으로 출력한다.
  if (command === 'catalog') {
    // 정규화 전 참고할 route 카탈로그를 출력한다.
    printJson(createCatalog(governance));
    // 정상 종료한다.
    return;
  }
  // context 명령은 router 기반 결정적 노드 pack을 출력한다.
  if (command === 'context') {
    // 최소 한 개 intent 또는 path가 없으면 모호한 요청으로 실패한다.
    if (options.intents.length === 0 && options.paths.length === 0) throw new Error('context에는 --intent 또는 --path가 필요합니다.');
    // 계산한 context 구조를 출력한다.
    printJson(createContext(governance, options));
    // 정상 종료한다.
    return;
  }
  // sync-plan 명령은 Rule 섹션 기반 갱신 계획을 출력한다.
  if (command === 'sync-plan') {
    // 계산한 동기화 계획을 출력한다.
    printJson(createSyncPlan(governance, options));
    // 정상 종료한다.
    return;
  }
  // sync-status 명령은 Rule 섹션 기준선과 현재 상태의 차이만 읽기 전용으로 보고한다.
  if (command === 'sync-status') {
    // 추가·삭제·변경 섹션과 영향 노드를 출력한다.
    printJson(createSyncStatus(governance));
    // 정상 종료한다.
    return;
  }
  // snapshot 명령은 초기 기준선 또는 계획 반영 시 사람이 검토할 digest 초안을 출력한다.
  if (command === 'snapshot') {
    // 현재 Rule과 map 기반의 기준선 초안을 출력한다.
    printJson(createSnapshot(governance));
    // 정상 종료한다.
    return;
  }
  // 알 수 없는 하위 명령은 자동 해석하지 않는다.
  throw new Error(`알 수 없는 명령: ${command}`);
}

// 최상위 예외를 사용자와 AI가 읽을 수 있는 JSON 오류로 변환한다.
// 직접 실행일 때만 CLI 진입점을 호출해 테스트에서 함수만 import할 수 있게 한다.
if (process.argv[1] && path.resolve(process.argv[1]) === TOOL_FILE) try {
  // 실제 명령을 실행한다.
  main();
} catch (error) {
  // Error 객체와 기타 throw 값을 모두 문자열 메시지로 정규화한다.
  const message = error instanceof Error ? error.message : String(error);
  // 실패 상태와 메시지를 표준 오류에 JSON으로 출력한다.
  process.stderr.write(`${JSON.stringify({ status: 'fail', error: message }, null, 2)}\n`);
  // 셸과 호출 AI가 실패를 감지하도록 종료 코드를 설정한다.
  process.exitCode = 1;
}

// 회귀 테스트는 동일한 섹션 비교·digest 구현을 직접 검증한다.
export { compareRuleSections, mappingSourceSectionDigest, parseRuleSections };

