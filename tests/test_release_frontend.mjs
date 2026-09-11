import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const read = path => readFileSync(new URL('../' + path, import.meta.url), 'utf8');
const script = read('static/js/webmcp.js');
async function fixture({ secure = true, supported = true, fail = false, response, scope = 'type=my' } = {}) {
    const tools = [], requests = [], events = {};
    const context = { document: supported ? { modelContext: { async registerTool(tool, opts) {
        if (fail) throw new Error('unsupported'); tools.push({ ...tool, signal: opts.signal });
    } } } : {}, console: { info() {} }, AbortController, URLSearchParams,
        isSecureContext: secure, getEquipmentListScope: () => new URLSearchParams(scope),
        addEventListener: (name, handler) => { events[name] = handler; },
        fetch: async (url, options) => { requests.push({ url, options }); return response || { ok: true, json: async () => [
            { EquipmentId: 1, Name: '<img src=x>', ModelName: 'Leaf', FullModelName: 'Root / Leaf', Memo: 'private', SerialNumber: 'secret', OptionName: '16GB' },
            { EquipmentId: 2, Name: 'Other', ModelName: 'Other' }
        ] }; }
    };
    context.window = context;
    await vm.runInNewContext(script, context);
    return { tools, requests, events };
}

test('all changed inline scripts parse without an app/server', () => {
    for (const path of ['templates/index.html', 'templates/dashboard.html', 'templates/lineup_management.html']) {
        for (const [, code] of read(path).matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
            new vm.Script(code.replace(/\{\{[\s\S]*?\}\}/g, 'fixture').replace(/\{%[\s\S]*?%\}/g, ''));
        }
    }
});
test('unsupported and insecure browsers retain UI without registering', async () => {
    assert.equal((await fixture({ secure: false })).tools.length, 0);
    assert.equal((await fixture({ supported: false })).tools.length, 0);
    assert.equal((await fixture({ fail: true })).tools.length, 0);
});
test('read tools search full paths, bound output and retain current scope', async () => {
    const f = await fixture({ scope: 'type=public&include_mine=false' });
    assert.deepEqual(f.tools.map(t => t.name), ['search_equipment', 'view_equipment_list']);
    const output = JSON.parse(await f.tools[0].execute({ query: 'Root', limit: 1 }));
    assert.equal(output.total, 1); assert.equal(output.equipments[0].model, 'Root / Leaf');
    assert.equal(output.equipments[0].name, '<img src=x>');
    assert.ok(!JSON.stringify(output).includes('secret')); assert.ok(!JSON.stringify(output).includes('private'));
    assert.equal(f.requests[0].url, '/api/equipment?type=public&include_mine=false');
    assert.equal(f.requests[0].options.method, 'GET');
    assert.equal(f.tools[0].annotations.readOnlyHint, true);
});
test('caller cannot change scope, send invalid pages or exceed limits', async () => {
    const f = await fixture();
    for (const input of [{ type: 'public' }, { user_id: 1 }, { limit: 101 }, { offset: -1 }, { query: 1 }, null, []]) {
        await assert.rejects(f.tools[0].execute(input));
    }
    assert.equal(f.requests.length, 0);
});
test('session errors and malformed API output are not exposed as tool results', async () => {
    for (const response of [{ ok: false }, { ok: true, json: async () => ({ login: true }) }]) {
        const f = await fixture({ response }); await assert.rejects(f.tools[0].execute({}));
    }
});
test('lifecycle cancellation unregisters and forwards request abort', async () => {
    const f = await fixture(), controller = new AbortController();
    await f.tools[0].execute({}, { signal: controller.signal });
    assert.equal(f.requests[0].options.signal, controller.signal);
    f.events.pagehide(); assert.equal(f.tools[0].signal.aborted, true);
});
test('declarative registration is add-only with manual submit, no dangerous tools', () => {
    const html = read('templates/index.html'), manifest = JSON.parse(read('Resources/metadata/.well-known/webmcp.json'));
    assert.ok(!html.includes('toolautosubmit'));
    assert.ok(html.includes("if (!id && window.isSecureContext && document.modelContext)"));
    assert.ok(html.includes("form.removeAttribute('toolname')"));
    assert.ok(html.includes('type="submit" id="btnFormalSubmit"'));
    assert.ok(!html.includes('id="UserId" name='));
    assert.equal(manifest.tools.length, 3);
});
test('full model and option UI use escaped text and show draft usage', () => {
    assert.ok(read('templates/index.html').includes("escapeHtml(item.FullModelName || item.ModelName || '-')"));
    assert.ok(read('templates/dashboard.html').includes("escapeDashboardText(eq.FullModelName || eq.ModelName || '-')"));
    const html = read('templates/lineup_management.html');
    assert.ok(html.includes('active_equipment_count + opt.draft_equipment_count'));
    assert.ok(html.includes('unusedOptionsOnly')); assert.ok(html.includes('/api/equipment_option'));
});
