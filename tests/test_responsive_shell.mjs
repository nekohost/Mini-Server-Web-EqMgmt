import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const read=name=>readFileSync(new URL('../'+name,import.meta.url),'utf8');
const sandbox={window:{},document:{readyState:'loading',addEventListener(){}},URL};
vm.runInNewContext(read('static/js/navigation.js'),sandbox);
const {weightedLength,titleLines}=sandbox.window.AppNavigation;
const lines=(...args)=>Array.from(titleLines(...args));
test('title unit counts use graphemes and half-width whitespace, not page names',()=>{
    assert.equal(weightedLength('가나다라마 바사아자차'),10.5);
    assert.equal(weightedLength('가나다라마 바사아자'),9.5);
    assert.equal(weightedLength('  나의   장비\n'),4.5);
    assert.equal(weightedLength('👨‍👩‍👧‍👦 e\u0301'),2.5);
});
test('long titles balance whole words at the 10-unit threshold and actual width',()=>{
    assert.deepEqual(lines('가나다라마 바사아자'),['가나다라마 바사아자']);
    assert.deepEqual(lines('가나다라마 바사아자차'),['가나다라마','바사아자차']);
    const text='장비 카탈로그 변경 요청 검토';
    const result=lines(text,6,weightedLength);
    assert.equal(result.join(' '),text);
    assert.ok(result.length>=3);
    assert.ok(result.every(line=>weightedLength(line)<=6));
    assert.deepEqual(lines('단일긴단어가분리되지않음',3,weightedLength),['단일긴단어가분리되지않음']);
    assert.deepEqual(lines(''),[]);
});
test('admin order groups related menus, preserves unknown entries and never adds access',()=>{
    const env={window:{}}; vm.runInNewContext(read('static/js/menu_cards.js'),env);
    const input=['future_two','backup_restore','permissions','lineup_management','future_one','users_management','master_management','approvals','access_logs','audit_logs','maintenance_admin'].map(MenuCode=>({MenuCode}));
    const original=input.slice(), output=Array.from(env.window.MenuCards.orderAdmin(input));
    assert.deepEqual(output.map(m=>m.MenuCode),['users_management','permissions','master_management','lineup_management','approvals','audit_logs','access_logs','maintenance_admin','backup_restore','future_two','future_one']);
    assert.deepEqual(input,original); assert.equal(new Set(output).size,input.length);
    assert.deepEqual(Array.from(env.window.MenuCards.orderAdmin([input[1]])).map(m=>m.MenuCode),['backup_restore']);
});
test('selection actions start visible/disabled; native timer button retains extension listener',()=>{
    const html=read('templates/users_management.html');
    for(const id of ['btnForceSelected','btnDeactivateSelected','btnReactivateSelected','btnDeleteSelected']) {
        const tag=html.match(new RegExp('<button[^>]+id="'+id+'"[^>]*>'))[0];
        assert.ok(tag.includes(' disabled')); assert.ok(!tag.includes('class="hidden'));
    }
    assert.match(read('templates/miniserver_frame.html'),/<button id="session-timer-badge" type="button"/);
    assert.ok(read('static/js/session_timer.js').includes("badge.addEventListener('click', extendSession)"));
});
