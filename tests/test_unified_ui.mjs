import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read=n=>readFileSync(new URL('../'+n,import.meta.url),'utf8');
test('all authenticated menus declare a shared title and description without embedded functions',()=>{
    for(const name of ['portal','admin_center','index','mypage','dashboard','users_management','permissions','master_management','lineup_management','approvals','my_approvals','audit_logs','access_logs','access_logs_error_ips','maintenance_admin','backup_restore']) {
        const html=read('templates/'+name+'.html'),header=html.match(/<header class="app-page-heading app-content-header">[\s\S]*?<\/header>/)?.[0];
        assert.ok(header,name);assert.ok(header.includes('app-content-title'));assert.ok(header.includes('app-content-description'));
        assert.ok(!/<button|<input|<form/.test(header),name+': heading is not a toolbar');
    }
});
test('my/public share one search/action region without duplicating IDs or submitting CSV toggle',()=>{
    const html=read('templates/roadmap_equipment.html'), index=read('templates/index.html');
    for(const id of ['roadmap-filter','roadmap-csv-toggle','includeMineCheckbox','btnToggleDrafts'])assert.equal(html.split('id="'+id+'"').length-1,1,id);
    assert.ok(!index.includes('id="includeMineCheckbox"'));
    assert.match(html,/<button type="button" id="roadmap-csv-toggle"/);
    assert.ok(html.indexOf('equipment-search-region')<html.indexOf('equipment-action-region'));
});
test('card sequence has no forced row groups; nickname is retained and timer preserves styling',()=>{
    const css=read('static/css/layout.css'),nav=read('templates/miniserver_frame.html'),timer=read('static/js/session_timer.js');
    assert.ok(!css.includes('data-admin-group-start'));assert.ok(!read('static/js/menu_cards.js').includes('adminGroupStart'));
    assert.ok(!nav.includes('app-nav-user-short'));assert.ok(nav.includes('{{ user.NickName }}'));assert.ok(nav.includes('{{ user.Role }}'));
    assert.ok(!timer.includes('badge.className'));assert.ok(timer.includes("badge.dataset.sessionState = 'warning'"));
});
