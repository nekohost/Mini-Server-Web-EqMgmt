// [역할] 앱/DB를 구동하지 않는 문법·연결·순수 표시 검사. [의존성 관계] Node VM. [변경 시 영향도] staging overlay.
import {readFileSync, readdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const root = fileURLToPath(new URL('../', import.meta.url));
const read = name => readFileSync(path.join(root, name), 'utf8');

test('all candidate JavaScript and inline template scripts parse', () => {
    for (const name of readdirSync(path.join(root, 'static/js'))) new vm.Script(read('static/js/' + name), {filename: name});
    for (const name of readdirSync(path.join(root, 'templates'))) {
        for (const [,code] of read('templates/' + name).matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
            new vm.Script(code.replace(/\{\{[\s\S]*?\}\}/g, 'fixture').replace(/\{%[\s\S]*?%\}/g, ''), {filename: name});
        }
    }
});
test('equipment module escapes labels and marks due state', () => {
    const context = {window: {}, document: {}};
    vm.runInNewContext(read('static/js/roadmap_equipment.js'), context);
    const module = context.window.Roadmap;
    assert.equal(module.escape('<img onerror="x">'), '&lt;img onerror=&quot;x&quot;&gt;');
    const html = module.badges({StatusLabel: '<script>', WarrantyBadge: {state: 'expired', label: '2일 경과'}});
    assert.ok(!html.includes('<script>')); assert.ok(html.includes('data-state="expired"'));
});
test('every fixed DOM id used by new equipment module is present', () => {
    const html = read('templates/roadmap_equipment.html') + read('templates/index.html');
    for (const [,id] of read('static/js/roadmap_equipment.js').matchAll(/byId\('([^']+)'\)/g)) assert.ok(html.includes(`id="${id}"`), id);
});
test('skins are allowlisted and invalid preference uses standard', () => {
    const html = {dataset: {}}, skin = {}, checkbox = {};
    const context = {window: {}, document: {documentElement: html, addEventListener() {}, getElementById(id) {return id === 'roadmap-skin' ? skin : checkbox;}}};
    vm.runInNewContext(read('static/js/roadmap_preferences.js'), context);
    context.window.applyRoadmapSettings({layout_skin: 'edge', deadline_email_opt_in: true});
    assert.equal(html.dataset.layoutSkin, 'edge'); assert.equal(checkbox.checked, true);
    context.window.applyRoadmapSettings({layout_skin: '<script>', deadline_email_opt_in: 'true'});
    assert.equal(html.dataset.layoutSkin, 'standard'); assert.equal(checkbox.checked, false);
});
test('API/template integration preserves manufacturer and edit-selection contracts', () => {
    const html = read('templates/index.html'), app = read('app.py');
    assert.ok(html.includes('buildManufacturerModelDisplay(item, mfgDisplayName)'));
    assert.ok(html.includes('window.LineupApp.restoreSelection(item)'));
    assert.ok(html.includes('form.dataset.originalRevision = String(item.Revision)'));
    assert.ok(html.includes('window.Roadmap.parameters()'));
    assert.ok(app.includes('install_roadmap(app, globals())'));
    assert.ok(app.includes('assert_attachment_files(candidate, ROADMAP_ATTACHMENT_ROOT)'));
});
test('all expected new APIs are present behind shared login/CSRF', () => {
    const source = read('utils/roadmap_routes.py');
    for (const name of ['lifecycle','update_status','upload_attachment','delete_attachment','csv_export','csv_preview','csv_commit','full_backup']) {
        assert.ok(source.includes(`def ${name}(`), name);
    }
    const mutations = [...source.matchAll(/@blueprint\.(post|delete)\([^\n]+\)([\s\S]*?)    def /g)];
    assert.equal(mutations.length, 6);
    for (const [,method,decorators] of mutations) { assert.ok(decorators.includes('@login_required'), method); assert.ok(decorators.includes('@csrf_required'), method); }
});
