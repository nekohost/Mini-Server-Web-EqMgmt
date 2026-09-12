// [역할] 등록 선택기의 상태 전이를 격리 검증합니다. [의존성 관계] Node vm·운영 템플릿. [변경 시 영향도] 생성 후 선택과 옵션 연결.
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

// 브라우저·네트워크 없이 선택기에서 사용하는 DOM 부분만 재현합니다.
class Element {
    constructor(tag = 'div') {
        this.tag = tag; this.children = []; this.dataset = {}; this.value = ''; this.listeners = {}; this.classes = new Set();
        this.classList = { add: (...v) => v.forEach(x => this.classes.add(x)), remove: (...v) => v.forEach(x => this.classes.delete(x)), contains: v => this.classes.has(v), toggle: (v, yes) => yes ? this.classes.add(v) : this.classes.delete(v) };
    }
    set innerHTML(value) { // 운영 선택기의 option 문자열을 메모리 DOM으로 변환합니다.
        this.children = []; this.value = ''; // 기존 자식과 선택값을 초기화합니다.
        if (this.tag !== 'select') return; // select 이외의 HTML은 이번 상태 테스트에서 해석하지 않습니다.
        for (const match of String(value).matchAll(/<option value="([^"]*)">([^<]*)<\/option>/g)) { // 정적 option만 추출합니다.
            const option = new Element('option'); option.value = match[1]; option.text = match[2]; this.add(option); // 실제 select.options와 같은 순서를 보존합니다.
        }
    }
    append(...children) { children.forEach(c => { c.parent = this; this.children.push(c); }); }
    appendChild(child) { this.append(child); }
    replaceChildren(...children) { this.children = []; this.append(...children); }
    add(option) { this.append(option); }
    remove() { this.parent.children = this.parent.children.filter(c => c !== this); }
    addEventListener(name, handler) { this.listeners[name] = handler; }
    dispatchEvent(event) { this.listeners[event.type]?.(event); }
    removeAttribute() {}
    setAttribute(name, value) { this[name] = value; }
    querySelectorAll(selector) { return this.children.flatMap(c => [...(c.className?.includes(selector.slice(1)) ? [c] : []), ...c.querySelectorAll(selector)]); }
}

// [역할] 운영 IIFE에 메모리 캐시와 DOM을 주입합니다. [의존성 관계] LineupApp. [변경 시 영향도] 실제 서버 접근 없이 동선 재현.
async function fixture(nodes, options = []) {
    const elements = new Map();
    const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
    ['CategorySelect','ManufacturerSelect','OptionSelect'].forEach(id => { get(id).tag = 'select'; }); // innerHTML option을 실제 선택 항목처럼 파싱할 요소를 지정합니다.
    const panels = [];
    let callbacks;
    const snapshot = { categories: [{id: 1, name: '서버'}], manufacturers: [{id: 1, name: '제조사'}], nodes, options };
    const document = {
        getElementById: get, createElement: tag => new Element(tag),
        querySelectorAll: selector => selector === '.kv-row' ? [] : get('dynamicTreeContainer').querySelectorAll(selector),
        querySelector: selector => {
            const parent = selector.match(/data-parent="([^"]+)"/)[1];
            return get('dynamicTreeContainer').children.find(row => String(row.dataset.parent) === parent)?.children.find(c => c.tag === 'select');
        }
    };
    const context = { document, console, alert() {}, escapeHtml: value => value, Event: class { constructor(type) {this.type=type;} },
        Option: class extends Element { constructor(text, value) { super('option'); this.text=text; this.value=String(value); } },
        sessionStorage: {getItem() { return null; }, setItem() {}, removeItem() {}},
        fetch: async () => ({ok: true, json: async () => snapshot}),
        createLineupNodeRegistration: config => { callbacks=config; return { mount: (el, data) => panels.push(data) }; }
    };
    context.window = context;
    const source = readFileSync(new URL('../templates/index.html', import.meta.url), 'utf8');
    const script = source.slice(source.indexOf('    window.LineupApp ='), source.indexOf('    function toggleDraftMode'));
    vm.runInNewContext(script, context);
    await context.LineupApp.init(true);
    get('CategorySelect').value = '1'; get('ManufacturerSelect').value = '1'; context.LineupApp.onRootChange();
    return { app: context.LineupApp, get, snapshot, panels, callbacks, document };
}

test('modal keeps header/footer fixed and only body scrollable', () => {
    const source = readFileSync(new URL('../templates/index.html', import.meta.url), 'utf8');
    const panel = source.indexOf('id="equipmentModalPanel"');
    const header = source.indexOf('id="equipmentModalHeader"');
    const body = source.indexOf('id="equipmentModalBody"');
    const footer = source.indexOf('id="equipmentModalFooter"');
    assert.ok(panel >= 0 && header > panel && body > header && footer > body);
    assert.match(source, /max-height: calc\(100dvh - 2rem\)/);
    assert.match(source, /id="equipmentModalHeader" class="shrink-0 /);
    assert.match(source, /id="equipmentModalBody" class="min-h-0 flex-1 overflow-y-auto p-6"/);
    assert.match(source, /id="equipmentModalFooter" class="shrink-0 /);
});

test('category and manufacturer selection does not show add panel until sentinel is chosen', async () => {
    const f = await fixture([]);
    assert.equal(f.panels.length, 0);
    const rootSelect = f.get('dynamicTreeContainer').children[0].children[0];
    assert.ok(rootSelect.children.some(option => option.value === '__add_node__'));
    assert.equal(f.app.getSelectedOptionData(), null);
});

test('empty catalog label explains that no model exists', async () => {
    const f = await fixture([]);
    const rootSelect = f.get('dynamicTreeContainer').children[0].children[0];
    assert.equal(rootSelect.children[0].text, '-- 등록된 모델 없음 (➕ 노드 추가 선택) --');
});

test('openModal resets the independent modal body scroll position', () => {
    const source = readFileSync(new URL('../templates/index.html', import.meta.url), 'utf8');
    assert.match(source, /const modalBody = document\.getElementById\('equipmentModalBody'\);/);
    assert.match(source, /if \(modalBody\) modalBody\.scrollTop = 0;/);
});

test('root add sentinel mounts root creation panel explicitly', async () => {
    const f = await fixture([]);
    const rootSelect = f.get('dynamicTreeContainer').children[0].children[0];
    rootSelect.value='__add_node__'; rootSelect.dispatchEvent({type:'change'});
    assert.equal(f.panels.length, 1);
    assert.equal(f.panels[0].parentId, null);
    assert.equal(f.panels[0].depth, 1);
});

test('existing node selection hides creation path and child sentinel mounts correct parent', async () => {
    const nodes = [{id:10,parent_id:null,category_id:1,manufacturer_id:1,name:'Root',depth:1}];
    const f = await fixture(nodes);
    const rootSelect = f.get('dynamicTreeContainer').children[0].children[0];
    rootSelect.value='10'; rootSelect.dispatchEvent({type:'change'});
    assert.equal(f.panels.length, 0);
    const childRow = f.get('dynamicTreeContainer').children.find(row => String(row.dataset.parent) === '10');
    const childSelect = childRow.children[0];
    assert.ok(childSelect.children.some(option => option.value === '__add_node__'));
    childSelect.value='__add_node__'; childSelect.dispatchEvent({type:'change'});
    assert.equal(f.panels.length, 1);
    assert.equal(f.panels[0].parentId, 10);
    assert.equal(f.panels[0].depth, 2);
});

test('approved creation reselects root and permits new option on that node', async () => {
    const f = await fixture([]);
    const rootSelect = f.get('dynamicTreeContainer').children[0].children[0];
    rootSelect.value='__add_node__'; rootSelect.dispatchEvent({type:'change'});
    f.snapshot.nodes.push({id:10,parent_id:null,category_id:1,manufacturer_id:1,name:'New',depth:1});
    await f.callbacks.onApproved({node_id:10},{category_id:1,manufacturer_id:1});
    f.get('OptionSelect').value='__new__'; f.get('NewOptionName').value='32GB';
    assert.equal(f.app.getSelectedOptionData().lineup_node_id,'10');
    f.callbacks.onBusy(true);
    assert.equal(f.app.getSelectedOptionData(),null);
});

test('node with children still exposes its own option and root change clears it', async () => {
    const nodes=[{id:10,parent_id:null,category_id:1,manufacturer_id:1,name:'Root',depth:1},{id:11,parent_id:10,category_id:1,manufacturer_id:1,name:'Child',depth:2}];
    const f=await fixture(nodes,[{id:20,lineup_node_id:10,option_name:'Original'}]);
    const select=f.get('dynamicTreeContainer').children[0].children[0];
    select.value='10'; select.dispatchEvent({type:'change'});
    f.get('OptionSelect').value='20';
    assert.equal(f.app.getSelectedOptionData().option_id,'20');
    f.app.onRootChange();
    assert.equal(f.app.getSelectedOptionData(),null);
});

test('edit restore selects the full node path and preserves an unchanged option', async () => {
    const nodes=[ // 3단계 가변 경로를 구성합니다.
        {id:10,parent_id:null,category_id:1,manufacturer_id:1,name:'Series',depth:1},
        {id:11,parent_id:10,category_id:1,manufacturer_id:1,name:'Generation',depth:2},
        {id:12,parent_id:11,category_id:1,manufacturer_id:1,name:'Model',depth:3}
    ];
    const f=await fixture(nodes,[{id:20,lineup_node_id:12,option_name:'16GB'}]); // 실제 옵션을 포함합니다.
    const result=f.app.restoreSelection({EquipmentId:7,CategoryId:1,ManufacturerId:1,LineupNodeId:12,OptionId:20,FullModelName:'Series / Generation / Model',OptionName:'16GB'}); // 목록 API 계약으로 복원합니다.
    assert.equal(result.restored,true); // 정상 승인 경로를 확인합니다.
    assert.equal(f.document.querySelector('.lineup-select-row[data-parent="root"] select').value,'10'); // 루트를 확인합니다.
    assert.equal(f.document.querySelector('.lineup-select-row[data-parent="10"] select').value,'11'); // 중간 노드를 확인합니다.
    assert.equal(f.document.querySelector('.lineup-select-row[data-parent="11"] select').value,'12'); // 대상 노드를 확인합니다.
    assert.equal(f.get('OptionSelect').value,'20'); // 기존 옵션이 실제 선택값입니다.
    const submission=f.app.getSubmissionState(); // VM 경계 객체는 값 단위로 검증합니다.
    assert.equal(submission.valid,true); // 미변경 수정은 유효합니다.
    assert.equal(submission.optionData,null); // stale option을 재전송하지 않습니다.
    assert.equal(submission.dirty,false); // 사용자 변경은 아직 없습니다.
    assert.equal(submission.preserved,true); // 기존 관계를 보존합니다.
});

test('edit restore supports an option attached to a node that also has children', async () => {
    const nodes=[{id:10,parent_id:null,category_id:1,manufacturer_id:1,name:'Root',depth:1},{id:11,parent_id:10,category_id:1,manufacturer_id:1,name:'Child',depth:2}]; // 중간 노드 옵션 구조입니다.
    const f=await fixture(nodes,[{id:20,lineup_node_id:10,option_name:'Root option'}]); // 부모 노드 자체 옵션을 둡니다.
    const result=f.app.restoreSelection({EquipmentId:8,CategoryId:1,ManufacturerId:1,LineupNodeId:10,OptionId:20,FullModelName:'Root',OptionName:'Root option'}); // 부모 노드 장비를 복원합니다.
    assert.equal(result.restored,true); // 자식 존재 여부와 무관하게 복원돼야 합니다.
    assert.equal(f.get('OptionSelect').value,'20'); // 부모 노드 옵션을 유지합니다.
});

test('an explicit option change becomes dirty while reselecting the original remains non-destructive', async () => {
    const nodes=[{id:10,parent_id:null,category_id:1,manufacturer_id:1,name:'Root',depth:1}]; // 단순 경로를 사용합니다.
    const options=[{id:20,lineup_node_id:10,option_name:'Old'},{id:21,lineup_node_id:10,option_name:'New'}]; // 변경 전후 옵션입니다.
    const f=await fixture(nodes,options); // 수정 fixture를 준비합니다.
    f.app.restoreSelection({EquipmentId:9,CategoryId:1,ManufacturerId:1,LineupNodeId:10,OptionId:20,FullModelName:'Root',OptionName:'Old'}); // 원본을 복원합니다.
    f.get('OptionSelect').value='21'; f.app.onOptionChange(); // 사용자가 다른 옵션을 선택합니다.
    let submission=f.app.getSubmissionState(); // 변경 상태를 읽습니다.
    assert.equal(submission.valid,true); // 완전한 변경 선택입니다.
    assert.equal(submission.optionData.option_id,'21'); // 새 옵션만 payload에 포함합니다.
    assert.equal(submission.optionData.isNew,false); // 기존 카탈로그 옵션입니다.
    assert.equal(submission.dirty,true); // 사용자 변경을 기록합니다.
    assert.equal(submission.preserved,false); // 원본 보존 모드는 해제됩니다.
    f.get('OptionSelect').value='20'; f.app.onOptionChange(); // 다시 원본 옵션을 선택합니다.
    submission=f.app.getSubmissionState(); // 원본 재선택 상태를 읽습니다.
    assert.equal(submission.valid,true); // 원본 재선택도 유효합니다.
    assert.equal(submission.optionData,null); // 동일 option_id 재전송은 생략합니다.
    assert.equal(submission.dirty,true); // 사용자가 선택을 조작한 사실은 유지합니다.
    assert.equal(submission.preserved,true); // 결과적으로 기존 관계를 보존합니다.
});

test('missing or mismatched catalog data preserves the current relationship without substitution', async () => {
    const f=await fixture([],[{id:20,lineup_node_id:99,option_name:'Detached'}]); // 승인 트리에 없는 현재 연결을 재현합니다.
    const result=f.app.restoreSelection({EquipmentId:10,CategoryId:1,ManufacturerId:1,LineupNodeId:99,OptionId:20,FullModelName:'Pending model',OptionName:'Detached'}); // 복원을 시도합니다.
    assert.equal(result.restored,false); // 임의의 다른 노드로 대체하지 않습니다.
    assert.equal(result.preserved,true); // 기존 option_id 보존 경로를 유지합니다.
    assert.equal(f.app.getSubmissionState().valid,true); // 기본 정보 수정은 가능해야 합니다.
    assert.equal(f.app.getSubmissionState().optionData,null); // 기존 연결을 재전송하지 않습니다.
    assert.match(f.get('catalogBindingStatus').textContent,/기존 연결은 유지/); // 사용자가 보존 동작을 알 수 있습니다.
});

test('cycles are bounded and a user root change invalidates preserved edit state', async () => {
    const nodes=[{id:10,parent_id:11,category_id:1,manufacturer_id:1,name:'A',depth:1},{id:11,parent_id:10,category_id:1,manufacturer_id:1,name:'B',depth:2}]; // 손상된 순환을 만듭니다.
    const f=await fixture(nodes,[{id:20,lineup_node_id:10,option_name:'Old'}]); // 기존 관계를 유지할 수 있게 합니다.
    const result=f.app.restoreSelection({EquipmentId:11,CategoryId:1,ManufacturerId:1,LineupNodeId:10,OptionId:20,FullModelName:'A / B',OptionName:'Old'}); // 제한된 역추적을 실행합니다.
    assert.equal(result.restored,false); // 순환 복원을 중단합니다.
    f.get('CategorySelect').value=''; f.app.onRootChange(); // 사용자가 카탈로그 변경을 시작합니다.
    assert.equal(f.app.getSubmissionState().valid,false); // 불완전 변경은 저장할 수 없습니다.
    assert.equal(f.app.getSubmissionState().dirty,true); // 원본 보존 모드가 해제됩니다.
});

test('modal integration restores edit selection and removes the previous placeholder warning', () => {
    const source = readFileSync(new URL('../templates/index.html', import.meta.url), 'utf8'); // 전체 모달 연결을 정적으로 확인합니다.
    assert.match(source,/window\.LineupApp\.restoreSelection\(item\)/); // 수정 데이터가 선택 복원 함수로 전달됩니다.
    assert.doesNotMatch(source,/기존 장비 수정 모드 트리 바인딩은 별도 제공 예정/); // 미구현 경고가 남지 않아야 합니다.
    assert.match(source,/const catalogSubmission = window\.LineupApp\.getSubmissionState\(\)/); // 저장 payload가 보존 상태를 사용합니다.
});
