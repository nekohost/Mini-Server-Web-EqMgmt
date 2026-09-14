import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const read = name => readFileSync(new URL('../' + name, import.meta.url), 'utf8');

test('menu labels strip annotations and decorative prefixes without rewriting data', () => {
    const sandbox = {window:{}}; vm.runInNewContext(read('static/js/menu_cards.js'),sandbox);
    const label = sandbox.window.MenuCards.menuLabel;
    assert.equal(label('내 정보 (마이페이지)'), '내 정보');
    assert.equal(label('🛠️ 관리자 센터 (관리 (확장))'), '관리자 센터');
    assert.equal(label('나의 장비'), '나의 장비');
    const nav = read('templates/miniserver_frame.html');
    assert.match(nav, />메인 포털<\/span>/);
    assert.ok(!/<i\b|app-nav-avatar/.test(nav));
    assert.ok(!nav.includes('>메인메뉴<'));
    const timer = read('static/js/session_timer.js');
    for(const mode of ['라이트','다크','시스템']) assert.ok(timer.includes(mode));
    assert.ok(!timer.includes('⏱'));
    for(const name of ['register','reset_password']) {
        assert.ok(!/<title>[^<]*Staging|block title %}[^\n]*Staging|<h1[^>]*>[^<]*Staging/.test(read('templates/'+name+'.html')));
    }
});

test('account safety actions are profile buttons and native closed dialogs', () => {
    const html = read('templates/mypage.html');
    assert.ok(!html.includes('마이페이지'));
    assert.ok(!/<i\b/.test(html));
    for(const id of ['passwordModal','withdrawModal']) {
        assert.match(html, new RegExp('<dialog id="'+id+'"[^>]*>'));
        assert.ok(!new RegExp('<dialog id="'+id+'"[^>]*\\bopen\\b').test(html));
    }
    assert.equal((html.match(/class="account-panel /g)||[]).length,2);
    assert.ok(html.includes("if (accountActionBusy) event.preventDefault()"));
    assert.ok(html.includes('if (accountActionBusy) return;'));
});

test('role editor and personal inbox keep mutation surfaces separate', () => {
    const roles=read('static/js/permissions.js'), own=read('static/js/my_approvals.js');
    assert.ok(roles.includes('rowsFor(role).map'));
    assert.ok(roles.includes('beforeunload'));
    assert.ok(roles.includes("'X-CSRFToken'"));
    assert.ok(!own.includes("method: 'POST'"));
    assert.ok(!own.includes('innerHTML'));
    assert.ok(own.includes("fetch('/api/my_approvals?'"));
});
