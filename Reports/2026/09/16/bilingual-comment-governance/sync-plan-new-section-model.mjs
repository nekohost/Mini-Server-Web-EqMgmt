#!/usr/bin/env node
// [역할] sync-plan 신규 Rule 섹션의 명시적 기존 노드 매핑 로직을 독립 검증합니다.
// [의존성 관계] 실제 governance-tool 수정 전 의미 모델이며 Node.js 표준 assert만 사용합니다.
// [변경 시 영향도] 이 모델과 실제 sync-plan의 매핑 검증은 같은 fail-closed 계약을 유지해야 합니다.
import assert from 'node:assert/strict'; // 단위 계약을 명시적으로 검증합니다.

function resolveMappings(existingMappings, manifestNodes, sections, explicitPairs) { // 신규 섹션을 기존 node mapping에 병합합니다.
  const requested = new Set(sections); // sync-status가 요구한 전체 섹션입니다.
  const nodeIds = new Set(Object.keys(manifestNodes)); // manifest 등록 노드만 허용합니다.
  const byNode = new Map(existingMappings.map((mapping) => [mapping.node_id, { ...mapping, human_rule_sections: [...mapping.human_rule_sections] }])); // 원본을 변경하지 않습니다.
  const explicit = new Map(); // section별 사용자가 지정한 신규 매핑입니다.
  for (const pair of explicitPairs) { // `section=node` 형식을 검증합니다.
    const separator = pair.indexOf('='); // 첫 등호를 구분자로 사용합니다.
    if (separator <= 0 || separator === pair.length - 1) throw new Error(`invalid mapping: ${pair}`); // 두 값 모두 필수입니다.
    const section = pair.slice(0, separator); // Rule 섹션 ID입니다.
    const nodeId = pair.slice(separator + 1); // 기존 node ID입니다.
    if (!requested.has(section)) throw new Error(`mapping section not requested: ${section}`); // 계획 외 섹션을 추가하지 않습니다.
    if (!nodeIds.has(nodeId) || !byNode.has(nodeId)) throw new Error(`mapping node not existing human-map node: ${nodeId}`); // 신규/미등록 node 추론을 막습니다.
    if (explicit.has(section) && explicit.get(section) !== nodeId) throw new Error(`conflicting mapping: ${section}`); // 하나의 신규 섹션을 둘로 갈라놓지 않습니다.
    explicit.set(section, nodeId); // 검증된 명시 매핑을 저장합니다.
  }
  const proposed = []; // sync-plan이 human-rule-map에 추가해야 할 명시 매핑입니다.
  for (const section of sections) { // 모든 변경 섹션이 하나 이상의 node에 연결되어야 합니다.
    const current = existingMappings.filter((mapping) => mapping.human_rule_sections.includes(section)); // 기존 mapping을 찾습니다.
    if (current.length > 0) { // 이미 연결된 섹션은 명시 신규 매핑이 필요 없습니다.
      if (explicit.has(section)) throw new Error(`mapping already exists: ${section}`); // 충돌·중복 의도를 차단합니다.
      continue; // 기존 계약을 그대로 사용합니다.
    }
    const nodeId = explicit.get(section); // 신규 섹션의 사용자 명시 대상을 찾습니다.
    if (!nodeId) throw new Error(`unmapped section requires explicit mapping: ${section}`); // 자동 추론하지 않습니다.
    const mapping = byNode.get(nodeId); // 기존 human map의 해당 node를 가져옵니다.
    if (!mapping.human_rule_sections.includes(section)) mapping.human_rule_sections.push(section); // digest 계산용 임시 mapping을 확장합니다.
    proposed.push({ section, nodeId }); // 실제 map 갱신 근거를 출력합니다.
  }
  const targetNodeIds = new Set(); // 변경 섹션이 영향을 주는 node를 집계합니다.
  for (const section of sections) { // 기존/신규 매핑을 모두 반영합니다.
    for (const mapping of byNode.values()) if (mapping.human_rule_sections.includes(section)) targetNodeIds.add(mapping.node_id); // 직접 연관 node만 선택합니다.
  }
  return { mappings: [...byNode.values()].filter((mapping) => targetNodeIds.has(mapping.node_id)), proposed }; // 대상 mapping과 신규 연결을 반환합니다.
}

const existing = [ // Mini-Server 실제 구조를 축약한 fixture입니다.
  { node_id: 'engineering.code-comments', human_rule_sections: ['1-3', '4-3-1', '4-3-4'] },
  { node_id: 'workflow.completion-history', human_rule_sections: ['7-4-1', '7-4-3'] },
  { node_id: 'workflow.multi-agent-handoff', human_rule_sections: ['7-5-1', '7-5-4'] },
];
const manifest = { 'engineering.code-comments': 'engineering/code-comments.md', 'workflow.completion-history': 'workflow/completion-history.md', 'workflow.multi-agent-handoff': 'workflow/multi-agent-handoff.md' }; // 등록 노드 fixture입니다.
let cases = 0; // 통과 케이스를 셉니다.
function passes(fn, label) { fn(); cases += 1; console.log(`PASS ${label}`); } // 성공 계약 helper입니다.
function fails(fn, pattern, label) { assert.throws(fn, pattern); cases += 1; console.log(`PASS ${label}`); } // 실패 계약 helper입니다.
passes(() => { // 기존+신규 섹션을 한 계획에서 결합합니다.
  const result = resolveMappings(existing, manifest, ['1-3', '4-3-5', '7-4-4', '7-5-5'], ['4-3-5=engineering.code-comments', '7-4-4=workflow.completion-history', '7-5-5=workflow.multi-agent-handoff']);
  assert.deepEqual(result.proposed, [
    { section: '4-3-5', nodeId: 'engineering.code-comments' },
    { section: '7-4-4', nodeId: 'workflow.completion-history' },
    { section: '7-5-5', nodeId: 'workflow.multi-agent-handoff' },
  ]); // 신규 연결 근거가 정확해야 합니다.
  assert.ok(result.mappings.find((item) => item.node_id === 'engineering.code-comments').human_rule_sections.includes('4-3-5')); // digest용 mapping도 확장되어야 합니다.
}, 'explicit mappings augment existing nodes');
fails(() => resolveMappings(existing, manifest, ['4-3-5'], []), /requires explicit mapping/, 'unmapped section fails closed'); // 명시 대상 없이는 실패합니다.
fails(() => resolveMappings(existing, manifest, ['4-3-5'], ['4-3-5=unknown.node']), /not existing human-map node/, 'unknown node rejected'); // 신규 node 추론을 금지합니다.
fails(() => resolveMappings(existing, manifest, ['4-3-5'], ['7-4-4=workflow.completion-history']), /not requested/, 'out-of-plan mapping rejected'); // 계획 범위 밖 mapping을 막습니다.
fails(() => resolveMappings(existing, manifest, ['1-3'], ['1-3=engineering.code-comments']), /already exists/, 'existing mapping override rejected'); // 이미 있는 mapping을 바꾸지 않습니다.
fails(() => resolveMappings(existing, manifest, ['4-3-5'], ['4-3-5=engineering.code-comments', '4-3-5=workflow.completion-history']), /conflicting mapping/, 'conflicting explicit mappings rejected'); // 한 섹션의 충돌을 막습니다.
console.log(JSON.stringify({ ok: true, cases }, null, 2)); // Staging 증거를 출력합니다.
