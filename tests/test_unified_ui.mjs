import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const read=n=>readFileSync(new URL('../'+n,import.meta.url),'utf8');
test('all workspace menus use the navigation h1 and retain reference help',()=>{
    for(const name of ['admin_center','mypage','dashboard','users_management','permissions','master_management','lineup_management','approvals','my_approvals','audit_logs','access_logs','access_logs_error_ips','maintenance_admin','backup_restore','index']) {
        const html=read('templates/'+name+'.html');
        assert.doesNotMatch(html,/<h1\b/,name+': no duplicate body heading');
        assert.match(html,/{% block workspace_help %}/,name+': reference description remains available');
        assert.doesNotMatch(html,/aria-labelledby="lineup-page-title"/,name+': no removed heading reference');
    }
    const frame=read('templates/miniserver_frame.html');
    assert.match(frame,/<h1 id="app-page-title" class="app-nav-title/);
    assert.match(frame,/<main aria-labelledby="app-page-title"/);
    assert.ok(frame.indexOf('{% block content %}')<frame.indexOf('class="app-workspace-help"'),'help follows work');
    assert.doesNotMatch(frame,/<details[^>]*\bopen\b/,'help starts collapsed');
});
test('the portal and both equipment modes start at their actual work',()=>{
    assert.doesNotMatch(read('templates/portal.html'),/<h1\b/);
    const index=read('templates/index.html');
    assert.doesNotMatch(index,/<h1\b/);
    assert.match(index,/equipment-compact-view/);
    assert.match(index,/{% if mode == 'my' %}equipment-owned-view/);
    assert.match(index,/{% block workspace_help %}{% if mode == 'public' %}/);
    assert.match(read('static/css/layout.css'),/\.app-main:not\(\.assistant-container\) \{ padding-top: 1rem; \}/);
});
test('audit-specific settings preserve both shared frame preference functions',async()=>{
    const load=()=>{},save=()=>{},requests=[];
    const sandbox={loadUserSettings:load,saveUserSettings:save,document:{addEventListener(){}},console,
        getCSRFToken:()=> 'synthetic-csrf',fetch:async(url,options)=>{requests.push({url,options});return {ok:true};}};
    sandbox.window=sandbox;
    for(const [,code] of read('templates/audit_logs.html').matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g))vm.runInNewContext(code,sandbox);
    assert.equal(sandbox.loadUserSettings,load);
    assert.equal(sandbox.saveUserSettings,save);
    assert.equal(typeof sandbox.loadAuditLogSettings,'function');
    await sandbox.saveAuditLogSettings({audit_log_page_size:50});
    assert.equal(requests.length,1);
    assert.equal(requests[0].url,'/api/user_settings');
    assert.equal(requests[0].options.method,'POST');
    assert.equal(requests[0].options.headers['X-CSRFToken'],'synthetic-csrf');
    assert.equal(JSON.parse(requests[0].options.body).audit_log_page_size,50);
});
test('my/public share one search/action region without duplicating IDs or submitting CSV toggle',()=>{
    const html=read('templates/roadmap_equipment.html'), index=read('templates/index.html');
    for(const id of ['roadmap-filter','roadmap-csv-toggle','includeMineCheckbox','btnToggleDrafts'])assert.equal(html.split('id="'+id+'"').length-1,1,id);
    assert.ok(!index.includes('id="includeMineCheckbox"'));
    assert.match(html,/<button type="button" id="roadmap-csv-toggle"/);
    assert.ok(html.indexOf('equipment-action-region')<html.indexOf('equipment-search-region'));
    assert.ok(html.indexOf('equipment-search-region')<html.indexOf('equipment-list-status'));
    assert.ok(html.indexOf('equipment-toolbar')<html.indexOf('id="roadmap-advanced"'));
});
test('card sequence has no forced row groups; nickname is retained and timer preserves styling',()=>{
    const css=read('static/css/layout.css'),nav=read('templates/miniserver_frame.html'),timer=read('static/js/session_timer.js');
    assert.ok(!css.includes('data-admin-group-start'));assert.ok(!read('static/js/menu_cards.js').includes('adminGroupStart'));
    assert.ok(!nav.includes('app-nav-user-short'));assert.ok(nav.includes('{{ user.NickName }}'));assert.ok(nav.includes('{{ user.Role }}'));
    assert.ok(!timer.includes('badge.className'));assert.ok(timer.includes("badge.dataset.sessionState = 'warning'"));
});
