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
    set innerHTML(value) { this.children = []; this.value = ''; }
    append(...children) { children.forEach(c => { c.parent = this; this.children.push(c); }); }
    appendChild(child) { this.append(child); }
    add(option) { this.append(option); }
    remove() { this.parent.children = this.parent.children.filter(c => c !== this); }
    addEventListener(name, handler) { this.listeners[name] = handler; }
    dispatchEvent(event) { this.listeners[event.type]?.(event); }
    removeAttribute() {}
    querySelectorAll(selector) { return this.children.flatMap(c => [...(c.className?.includes(selector.slice(1)) ? [c] : []), ...c.querySelectorAll(selector)]); }
}

// [역할] 운영 IIFE에 메모리 캐시와 DOM을 주입합니다. [의존성 관계] LineupApp. [변경 시 영향도] 실제 서버 접근 없이 동선 재현.
async function fixture(nodes, options = []) {
    const elements = new Map();
    const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
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

test('empty catalog offers root creation', async () => {
    const f = await fixture([]);
    assert.equal(f.panels[0].parentId, null);
    assert.equal(f.app.getSelectedOptionData(), null);
});

test('approved creation reselects root and permits new option on that node', async () => {
    const f = await fixture([]);
    f.snapshot.nodes.push({id: 10, parent_id: null, category_id: 1, manufacturer_id: 1, name: 'New', depth: 1});
    await f.callbacks.onApproved({node_id:10}, {category_id:1, manufacturer_id:1});
    f.get('OptionSelect').value = '__new__'; f.get('NewOptionName').value = '32GB';
    assert.equal(f.app.getSelectedOptionData().lineup_node_id, '10');
    f.callbacks.onBusy(true);
    assert.equal(f.app.getSelectedOptionData(), null);
});

test('node with children still exposes its own option and root change clears it', async () => {
    const nodes = [{id: 10, parent_id: null, category_id:1, manufacturer_id:1, name:'Root', depth:1}, {id:11, parent_id:10, category_id:1, manufacturer_id:1, name:'Child', depth:2}];
    const f = await fixture(nodes, [{id:20, lineup_node_id:10, option_name:'Original'}]);
    const select = f.get('dynamicTreeContainer').children[0].children[0];
    select.value='10'; select.dispatchEvent({type:'change'});
    f.get('OptionSelect').value='20';
    assert.equal(f.app.getSelectedOptionData().option_id, '20');
    f.app.onRootChange();
    assert.equal(f.app.getSelectedOptionData(), null);
});
