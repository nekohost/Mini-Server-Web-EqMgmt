import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
// Release-specific rollback audit: deliberate later UI changes require a new baseline.
const read=name=>readFileSync(new URL('../'+name,import.meta.url));
const hash=value=>createHash('sha256').update(value).digest('hex');
const baseline=JSON.parse(read('Reports/2026/09/14/responsive-shell/baselines.json'));
const deployed=JSON.parse(read('Reports/2026/09/14/responsive-shell/deployment.json'));
const audit=(name,fn)=>test(name,{skip:process.env.EQM_AUDIT_HEADING_ROLLBACK!=='1'},fn);

audit('heading-only templates exactly restore the pre-improvement-2 sources (normalized EOL)',()=>{
    for(const name of ['index','master_management','access_logs','access_logs_error_ips','lineup_management','permissions','mypage']) {
        const path='templates/'+name+'.html';
        assert.equal(hash(read(path).toString().replaceAll('\r\n','\n')),baseline[path],path);
    }
});

audit('navigation and admin-group source artifacts are byte-identical to improvements 1/4',()=>{
    for(const path of ['static/js/navigation.js','static/js/session_timer.js','static/js/menu_cards.js','templates/miniserver_frame.html','templates/admin_center.html']) {
        assert.equal(hash(read(path)),deployed.files[path].after,path);
    }
});

audit('shared CSS and user header undo only the split heading, retaining selection affordances',()=>{
    const css=read('static/css/layout.css').toString(), users=read('templates/users_management.html').toString();
    assert.ok(!css.includes('.app-heading-'));
    assert.ok(!users.includes('app-heading-'));
    assert.ok(css.includes('[data-selection-action]:disabled'));
    assert.ok(css.includes('.menu-card[data-admin-group-start]'));
    assert.ok(css.includes('minmax(0, 1.25fr)'));
    assert.ok(css.includes('.equipment-page-actions button, .account-profile-heading > * { white-space: nowrap; }'));
    assert.ok(users.includes('app-page-heading mb-4 flex flex-col md:flex-row md:items-center justify-between gap-4'));
    assert.ok(users.includes('button.disabled = count === 0'));
    assert.equal((users.match(/data-selection-action disabled/g)||[]).length,4);
});
