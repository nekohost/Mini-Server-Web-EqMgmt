// [역할] 거버넌스 도구의 validate·context·sync-plan·fail-closed 동작을 읽기 전용으로 회귀 검증한다.
// [의존성 관계] governance-tool.mjs, Node child_process와 assert, npm yaml 패키지에 의존한다.
// [변경 시 영향도] 명령 출력 스키마나 router 정책을 변경하면 이 테스트의 기대값과 검증 보고서를 함께 갱신해야 한다.

// 현재 Node 실행 파일로 하위 명령을 격리 실행하기 위해 child_process를 사용한다.
import { spawnSync } from 'node:child_process';
// 검증 실패를 명확한 예외로 처리하기 위해 strict assert를 사용한다.
import assert from 'node:assert/strict';
// YAML 파서가 실제 오류를 탐지하는지 독립 검사하기 위해 parseDocument를 사용한다.
import { parseDocument } from 'yaml';
// CLI와 같은 섹션 비교 및 node digest 구현을 단위 회귀로 확인한다.
import { compareRuleSections, mappingSourceSectionDigest, parseRuleSections } from './governance-tool.mjs';

// 정상 종료하는 거버넌스 명령을 실행하고 JSON을 반환한다.
function runSuccess(args) {
  // 현재 Node와 같은 런타임으로 거버넌스 도구를 실행한다.
  const result = spawnSync(process.execPath, ['governance-tool.mjs', ...args], { encoding: 'utf8' });
  // 정상 시나리오는 종료 코드 0이어야 한다.
  assert.equal(result.status, 0, `명령 실패: ${args.join(' ')}\n${result.stderr}`);
  // 표준 출력 JSON을 객체로 반환한다.
  return JSON.parse(result.stdout);
}

// 실패해야 하는 거버넌스 명령을 실행하고 오류 JSON을 반환한다.
function runFailure(args) {
  // 현재 Node와 같은 런타임으로 거버넌스 도구를 실행한다.
  const result = spawnSync(process.execPath, ['governance-tool.mjs', ...args], { encoding: 'utf8' });
  // fail-closed 시나리오는 종료 코드 0이면 안 된다.
  assert.notEqual(result.status, 0, `실패해야 할 명령이 성공했습니다: ${args.join(' ')}`);
  // 예외 명령은 표준 오류, 검증 실패는 표준 출력 JSON을 사용하므로 비어 있지 않은 쪽을 반환한다.
  return JSON.parse(result.stderr.trim() || result.stdout.trim());
}

// 실행한 테스트 이름을 결과에 누적한다.
const passed = [];

// 전체 YAML·front matter·양방향 추적성 검증을 실행한다.
const validation = runSuccess(['validate']);
// 전체 검증 상태가 pass인지 확인한다.
assert.equal(validation.status, 'pass');
// manifest와 human map의 노드 수가 모두 40개인지 확인한다.
assert.deepEqual(validation.counts, { manifestNodes: 40, humanMapNodes: 40, errors: 0, warnings: 0 });
// 정규 YAML 파서가 섹션 기준선을 포함한 10개 제어 파일을 실제 파싱했는지 확인한다.
assert.equal(validation.parser.filesParsed, 10);
// 선언·잠금·설치 버전이 모두 yaml 2.9.0으로 일치하는지 확인한다.
assert.equal(validation.parser.configuredVersion, '2.9.0');
// 잠금 버전의 일치를 확인한다.
assert.equal(validation.parser.lockedVersion, '2.9.0');
// 설치 버전의 일치를 확인한다.
assert.equal(validation.parser.installedVersion, '2.9.0');
// 통과 목록에 검증 시나리오를 추가한다.
passed.push('validate parses YAML/front matter and checks bidirectional invariants');

// 지원 intent와 path route 전체 카탈로그를 생성한다.
const catalog = runSuccess(['catalog']);
// Rule 개정 intent가 카탈로그에 포함되는지 확인한다.
assert.ok(catalog.knownIntents.includes('edit-rule'));
// schema-change와 frontend-change route가 모두 포함되는지 확인한다.
assert.ok(catalog.routes.some((route) => route.id === 'schema-change'));
// 프론트엔드 route 존재를 독립적으로 확인한다.
assert.ok(catalog.routes.some((route) => route.id === 'frontend-change'));
// 통과 목록에 route 카탈로그 시나리오를 추가한다.
passed.push('catalog exposes every supported intent and path route');

// 기준선과 현재 Rule이 동기화 상태인지 먼저 확인한다.
const syncStatus = runSuccess(['sync-status']);
// 초기 기준선과 현재 Rule 사이에 미반영 변경이 없는지 확인한다.
assert.equal(syncStatus.inSync, true);
// 계획 및 검증에 사용할 현재 Rule hash가 있는지 확인한다.
assert.match(syncStatus.currentRuleHash, /^[A-F0-9]{64}$/);
// 통과 목록에 동기화 상태 조회 시나리오를 추가한다.
passed.push('sync-status reports section-level Rule baseline state');

// Rule 3-1-1과 11-3의 동시성 보호 동기화 계획을 생성한다.
const syncPlan = runSuccess(['sync-plan', '--expected-rule-sha', syncStatus.currentRuleHash, '--section', '3-1-1', '--section', '11-3']);
// DB 보류 대상인 data-model 노드가 포함되는지 확인한다.
assert.ok(syncPlan.targetNodes.some((node) => node.nodeId === 'engineering.data-model'));
// Rule 동기화 절차 노드가 포함되는지 확인한다.
assert.ok(syncPlan.targetNodes.some((node) => node.nodeId === 'governance.rule-sync'));
// manifest와 human map이 필수 갱신 파일인지 확인한다.
assert.ok(syncPlan.requiredFiles.includes('manifest.yaml'));
// 섹션 기준선도 필수 갱신 파일인지 확인한다.
assert.ok(syncPlan.requiredFiles.includes('traceability/rule-section-baseline.yaml'));
// 계획이 관측한 Rule hash를 기준 hash로 보관하는지 확인한다.
assert.equal(syncPlan.baseRuleHash, syncStatus.currentRuleHash);
// 통과 목록에 동기화 계획 시나리오를 추가한다.
passed.push('sync-plan resolves Rule sections to nodes/map/manifest');

// 이전 계획의 hash를 사용한 동기화 계획은 fail-closed 해야 한다.
const stalePlan = runFailure(['sync-plan', '--expected-rule-sha', '0'.repeat(64), '--section', '3-1-1']);
// 오류 메시지가 예상 hash 불일치를 명시하는지 확인한다.
assert.match(stalePlan.error, /Rule SHA-256/);
// 통과 목록에 오래된 계획 차단 시나리오를 추가한다.
passed.push('sync-plan rejects stale Rule hash');

// 이전 계획의 hash를 사용한 최종 검증도 fail-closed 해야 한다.
const staleValidation = runFailure(['validate', '--expected-rule-sha', '0'.repeat(64)]);
// 검증 결과가 예상 hash 불일치와 실패 상태를 포함하는지 확인한다.
assert.ok(staleValidation.errors.some((error) => error.includes('expected Rule SHA-256 불일치')));
// 통과 목록에 오래된 검증 차단 시나리오를 추가한다.
passed.push('validate rejects stale Rule hash');

// 기준선 Rule의 독립된 섹션 샘플을 파싱한다.
const baselineSections = parseRuleSections('## 1. 기준 A\n원문\n## 2. 기준 B\n원문\n');
// 내용 변경·삭제·추가를 함께 포함한 현재 Rule 샘플을 파싱한다.
const revisedSections = parseRuleSections('## 1. 기준 A\n수정 원문\n## 3. 새 기준\n원문\n');
// 두 섹션 집합의 추가·삭제·내용 변경을 계산한다.
const sectionDiff = compareRuleSections(revisedSections, baselineSections.sections);
// 같은 번호의 본문 hash 변경을 변경으로 탐지하는지 확인한다.
assert.deepEqual(sectionDiff.changed, ['1']);
// 새 번호 섹션을 추가로 탐지하는지 확인한다.
assert.deepEqual(sectionDiff.added, ['3']);
// 제거 또는 번호 변경된 섹션을 삭제로 탐지하는지 확인한다.
assert.deepEqual(sectionDiff.removed, ['2']);
// 동일 mapping의 섹션 hash만 달라져도 node digest가 바뀌는지 계산한다.
const baselineDigest = mappingSourceSectionDigest({ node_id: 'test.node', human_rule_sections: ['1'] }, baselineSections.sections);
// 변경된 Rule 섹션으로 새 node digest를 계산한다.
const revisedDigest = mappingSourceSectionDigest({ node_id: 'test.node', human_rule_sections: ['1'] }, revisedSections.sections);
// hash-only Rule 수정이 노드 반영 누락으로 드러나는지 확인한다.
assert.notEqual(baselineDigest, revisedDigest);
// 통과 목록에 섹션 단위 변경·추가·삭제·digest 회귀를 추가한다.
passed.push('section baseline detects changed, added, removed, and hash-only node drift');

// Rule 개정의 작은 모델 context pack을 생성한다.
const ruleContext = runSuccess(['context', '--intent', 'edit-rule', '--path', 'Rule.md', '--section', '3-1-1', '--small-model']);
// Rule 유지보수 route가 매칭되는지 확인한다.
assert.ok(ruleContext.matchedRoutes.includes('human-rule-maintenance'));
// 변경 섹션의 data-model 노드가 동적으로 포함되는지 확인한다.
assert.ok(ruleContext.nodes.includes('engineering.data-model'));
// 모든 pack이 router가 반환한 작은 모델 계획 예산을 지키는지 확인한다.
assert.ok(ruleContext.packs.every((pack) => pack.estimatedTokens <= ruleContext.budget && pack.overBudget === false));
// 한글 과소평가를 줄이는 UTF-8 바이트 기반 estimator가 사용되는지 확인한다.
assert.equal(ruleContext.tokenEstimator, 'utf8-bytes-div-3-ceil');
// 이 예산이 특정 모델 토크나이저의 보장이 아닌 계획치로 표시되는지 확인한다.
assert.equal(ruleContext.tokenBudgetIsModelAgnosticEstimate, true);
// 통과 목록에 Rule context 시나리오를 추가한다.
passed.push('Rule maintenance dynamically loads pointed nodes and splits safe packs');

// DB 컬럼과 프론트엔드가 결합된 복합 context를 생성한다.
const compositeContext = runSuccess(['context', '--intent', 'add-column', '--intent', 'frontend', '--path', 'app.py', '--path', 'templates/index.html', '--small-model']);
// 스키마 route와 프론트엔드 route가 모두 매칭되는지 확인한다.
assert.deepEqual(compositeContext.matchedRoutes, ['schema-change', 'frontend-change']);
// 스키마와 반응형 프론트엔드 노드가 모두 포함되는지 확인한다.
assert.ok(compositeContext.nodes.includes('engineering.schema-evolution'));
// 반응형 프론트엔드 노드가 포함되는지 확인한다.
assert.ok(compositeContext.nodes.includes('engineering.frontend-responsive'));
// 작은 모델 context가 두 개 이상의 안전 pack으로 분할되는지 확인한다.
assert.equal(compositeContext.splitRequired, true);
// 통과 목록에 복합 route 시나리오를 추가한다.
passed.push('multiple intents and paths combine every matching route');

// 미등록 intent와 path를 fail-closed 해야 하는 시나리오를 실행한다.
const unknownRoute = runFailure(['context', '--intent', 'unknown-intent', '--path', 'unknown.file']);
// 오류 메시지에 intent와 path가 모두 포함되는지 확인한다.
assert.match(unknownRoute.error, /unknown-intent/);
// 미매칭 path도 명확히 보고되는지 확인한다.
assert.match(unknownRoute.error, /unknown\.file/);
// 통과 목록에 미등록 route 차단 시나리오를 추가한다.
passed.push('unknown intent/path fails closed');

// Rule 개정에서 section 누락을 fail-closed 해야 하는 시나리오를 실행한다.
const missingSection = runFailure(['context', '--intent', 'edit-rule', '--path', 'Rule.md']);
// 오류 메시지가 section 요구를 명시하는지 확인한다.
assert.match(missingSection.error, /--section/);
// 통과 목록에 section 누락 차단 시나리오를 추가한다.
passed.push('Rule maintenance without changed section fails closed');

// 고의로 중복 키가 있는 YAML 문자열을 정규 파서에 전달한다.
const invalidYaml = parseDocument('duplicate: 1\nduplicate: 2\n', { strict: true, uniqueKeys: true });
// 중복 키 YAML이 오류 없이 통과하지 않는지 확인한다.
assert.ok(invalidYaml.errors.length > 0);
// 통과 목록에 실제 YAML 오류 탐지 시나리오를 추가한다.
passed.push('regular YAML parser rejects duplicate keys');

// 전체 회귀 결과를 사람이 읽을 수 있는 JSON으로 출력한다.
process.stdout.write(`${JSON.stringify({ status: 'pass', tests: passed.length, passed }, null, 2)}\n`);

