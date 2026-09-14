// Approved real-domain smoke test with the existing restricted test account.
// Password is read only into memory via SSH; no cookie/credential/trace files.
// Only login, preference updates and session extension may POST. No equipment writes.
import {readFileSync, mkdirSync, writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {readabilitySnapshot, assertReadability} from '../../../../../tests/helpers/readability.mjs';
import {responsiveShellSnapshot, assertResponsiveShell} from '../../../../../tests/helpers/responsive_shell.mjs';
const here = fileURLToPath(new URL('./', import.meta.url));
const root = path.resolve(here, '../../../../..');
const workflowVariant = process.env.EQM_LIVE_VARIANT === 'menu-workflows';
const unifiedUi = workflowVariant || process.env.EQM_LIVE_VARIANT === 'unified-ui';
const headingRollback = process.env.EQM_LIVE_VARIANT === 'heading-rollback';
const shellVariant = unifiedUi || headingRollback || process.env.EQM_LIVE_VARIANT === 'responsive-shell';
const readabilityVariant = shellVariant || process.env.EQM_LIVE_VARIANT === 'readability';
const compactVariant = readabilityVariant || process.env.EQM_LIVE_VARIANT === 'compact-nav';
const headerCsvVariant = compactVariant || process.env.EQM_LIVE_VARIANT === 'header-csv';
const output = path.resolve(here, workflowVariant ? '../menu-workflows/portrait' : unifiedUi ? '../unified-ui/portrait' : headingRollback ? '../heading-rollback/portrait' : shellVariant ? '../responsive-shell/portrait' : readabilityVariant ? '../table-button-readability/portrait' : compactVariant ? '../compact-navigation/portrait' : headerCsvVariant ? '../header-csv/portrait' : '../ui-navigation-search/portrait-corrected');
const origin = 'https://nekohost.org';
if (process.env.EQM_LIVE_EDGE !== 'approved') throw new Error('Requires approved test-account smoke test.');
const {chromium, devices} = createRequire(import.meta.url)('playwright');
const quote = s => "'" + s.replaceAll("'", "'\\''") + "'";
function credentials() {
    const code = 'from pathlib import Path; import sys; sys.stdout.write(Path("/home/nekohost/.local/share/mini-server-eqmgmt/test-accounts/guide_test_user.credentials").read_text())';
    const result = spawnSync('ssh', ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'eqmgmt-backup',
        '/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python -c ' + quote(code)], {encoding: 'utf8', timeout: 15000});
    if (result.status !== 0) throw new Error('Credential read failed (details suppressed).');
    let fields;
    try { fields = JSON.parse(result.stdout); }
    catch {
        fields = Object.fromEntries([...result.stdout.matchAll(/^\s*([A-Za-z_ ]+)\s*[:=]\s*(.*?)\s*$/gm)]
            .map(m => [m[1].trim().toLowerCase().replaceAll(' ', '').replaceAll('_', ''), m[2]]));
    }
    const login = fields.LoginId || fields.login_id || fields.loginid || fields.username;
    const password = fields.Password || fields.password;
    result.stdout = '';
    if (login !== 'guide_test_user' || typeof password !== 'string' || !password) throw new Error('Credential format/account mismatch (values suppressed).');
    return {login, password};
}

const browser = await chromium.launch({channel: 'msedge', headless: true});
const context = await browser.newContext({...devices['Pixel 7'], viewport: {width: 390, height: 844}, reducedMotion: 'reduce'});
const evidence = {origin, mode: 'mobile-emulation', engine: 'headless Microsoft Edge / Chromium', touch: true,
    screens: [], dialogs: [], pageErrors: [], httpErrors: [], forbiddenRequests: [], steps: []};
const allowedHosts = new Set(['nekohost.org', 'cdn.tailwindcss.com', 'cdnjs.cloudflare.com', 'cdn.jsdelivr.net']);
await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (!allowedHosts.has(url.hostname)) return route.abort();
    if (!['GET', 'HEAD'].includes(request.method()) && !(url.origin === origin && request.method() === 'POST'
        && ['/login', '/api/user_settings', '/api/extend_session'].includes(url.pathname))) {
        evidence.forbiddenRequests.push({method: request.method(), path: url.pathname});
        return route.abort();
    }
    await route.continue();
});
const page = await context.newPage();
page.on('pageerror', error => evidence.pageErrors.push(error.message.slice(0, 200)));
page.on('response', response => {
    if (new URL(response.url()).origin === origin && response.status() >= 500)
        evidence.httpErrors.push({path: new URL(response.url()).pathname, status: response.status()});
});
mkdirSync(path.join(output, 'screenshots'), {recursive: true});
let original, loggedIn = false, failure;
async function goto(route) {
    const response = await page.goto(origin + route, {waitUntil: 'networkidle'});
    assert.equal(response.status(), 200);
    if (route !== '/login') await page.waitForFunction(() => window.userSettings && window.userSettings.layout_skin);
}
async function capture(skin, route, width, height, state = '') {
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const m = await page.evaluate(() => {
        const rect = el => {const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height};};
        return {width: innerWidth, height: innerHeight, scale: visualViewport.scale,
            portrait: matchMedia('(orientation: portrait)').matches,
            touch: navigator.maxTouchPoints, hover: matchMedia('(hover: hover)').matches,
            overflow: document.documentElement.scrollWidth - innerWidth,
            links: [...document.querySelectorAll('.app-nav-links .app-nav-link')].map(rect),
            linkGroup: rect(document.querySelector('.app-nav-links')),
            historyGroup: document.querySelector('.app-nav-history') && rect(document.querySelector('.app-nav-history')),
            rightChildren: [...document.querySelectorAll('.app-nav-tools > *, .app-nav-account > *')].map(rect),
            header: rect(document.querySelector('body > nav')),
            main: rect(document.querySelector('main')),
            controls: [...document.querySelectorAll('.app-nav-title, .app-nav-links, .app-nav-controls, .app-nav-controls > *')].map(rect),
            navRow: rect(document.querySelector('.app-nav-row')), navTitle: rect(document.querySelector('.app-nav-title')),
            navControls: rect(document.querySelector('.app-nav-controls')),
            search: [...document.querySelectorAll('.roadmap-search-basic > button, #roadmap-keyword')].map(rect),
            descriptions: [...document.querySelectorAll('.menu-card-description')].map(el => ({
                height: el.getBoundingClientRect().height, clamp: getComputedStyle(el).webkitLineClamp,
                fullTitle: el.textContent === el.title
            })),
            tables: [...document.querySelectorAll('main .overflow-x-auto')].map(el => ({
                width: el.clientWidth, scrollWidth: el.scrollWidth
            }))
        };
    });
    assert.equal(m.width, width); assert.equal(m.height, height);
    assert.equal(m.scale, 1); assert.equal(m.portrait, true); assert.ok(m.touch > 0); assert.equal(m.hover, false);
    assert.ok(m.overflow <= 1, skin + route + '@' + width + ': horizontal overflow');
    assert.ok(m.controls.every(box => box.y + box.height <= m.header.y + m.header.height + 1), 'wrapped controls must be contained by header');
    assert.ok(m.main.y >= m.header.y + m.header.height - 1, 'header and main must not overlap');
    if (headerCsvVariant) {
        assert.ok(Math.abs(m.navTitle.x + m.navTitle.width / 2 - width / 2) < 1);
        assert.ok(Math.abs(m.links[0].x - m.navRow.x) < 1);
        assert.ok(Math.abs(m.navControls.x + m.navControls.width - m.navRow.x - m.navRow.width) < 1);
    }
    if (m.search.length) assert.equal(m.search[1].y, m.search[2].y, 'search and mode switch remain adjacent');
    assert.equal(m.links.length, route === '/portal' ? 2 : 3);
    if (compactVariant && !shellVariant) {
        const centerY = r => r.y + r.height / 2;
        const [home, back, parent] = m.links;
        assert.ok(Math.abs(centerY(home) - centerY(m.historyGroup)) < 1);
        assert.ok(back.x > home.x + home.width);
        if (parent) { assert.equal(back.x, parent.x); assert.ok(parent.y >= back.y + back.height - 1); }
        else assert.ok(Math.abs(centerY(home) - centerY(back)) < 1);
        assert.ok(Math.abs(centerY(m.linkGroup) - centerY(m.navControls)) < 1);
        assert.ok(m.navTitle.y + m.navTitle.height <= Math.min(m.linkGroup.y, m.navControls.y) + 1);
        assert.ok(m.linkGroup.x + m.linkGroup.width <= m.navControls.x + 1);
        assert.ok(m.rightChildren.every(r => r.x >= m.navControls.x - 1 && r.x + r.width <= m.navControls.x + m.navControls.width + 1));
        assert.ok(m.header.height < 120);
    } else if (!shellVariant) assert.ok(m.links.every(link => link.y === m.links[0].y));
    for (const box of [...m.links, ...m.search]) {
        assert.ok(box.x >= 0 && box.x + box.width <= width + 1, 'control not clipped');
        assert.ok(box.height >= 24 && box.width >= 24, 'control hit area too small');
    }
    for (const desc of m.descriptions) {
        assert.equal(desc.height, 60); assert.equal(desc.clamp, '3'); assert.equal(desc.fullTitle, true);
    }
    if (shellVariant) {
        m.shell = await page.evaluate(responsiveShellSnapshot);
        assertResponsiveShell(assert, m.shell, skin + route + '@' + width);
    }
    if (readabilityVariant) {
        m.readability = await page.evaluate(readabilitySnapshot);
        assertReadability(assert, m.readability, skin + route + '@' + width);
    }
    evidence.screens.push({skin, route, state, ...m});
    if ([320, 390].includes(width)) await page.screenshot({
        path: path.join(output, 'screenshots', skin + '-' + route.slice(1) + '-' + width + (state ? '-' + state : '') + '.png'),
        fullPage: false, mask: [page.locator('input[type="password"]')]
    });
}
async function checkDialog(skin, selector, width) {
    const result = await page.evaluate(readabilitySnapshot);
    assertReadability(assert, result, skin + '/' + selector + '@' + width);
    assert.ok(await page.locator(selector).evaluate(el => [...el.querySelectorAll('button')]
        .filter(b => b.getBoundingClientRect().width > 0).every(b => {
            const r = b.getBoundingClientRect(); return r.x >= 0 && r.right <= innerWidth + 1;
        })), selector + ': modal buttons reachable');
    evidence.dialogs.push({skin, selector, width, ...result});
    await page.screenshot({path: path.join(output, 'screenshots', skin + '-' + selector.slice(1) + '-' + width + '.png'),
        mask: [page.locator('input[type="password"]')], fullPage: false});
}
async function searchTap(selector) {
    const result = page.waitForResponse(r => new URL(r.url()).pathname === '/api/equipment');
    await page.locator(selector).tap();
    assert.equal((await result).status(), 200);
}
try {
    await goto('/login');
    let creds = credentials();
    await page.locator('#LoginId').fill(creds.login);
    await page.locator('#Password').fill(creds.password);
    creds.password = ''; creds = null;
    await Promise.all([page.waitForURL(origin + '/portal'), page.locator('#loginForm button[type="submit"]').tap()]);
    loggedIn = true;
    original = await page.evaluate(async () => (await (await fetch('/api/user_settings')).json()).settings);
    if (shellVariant) {
        const extended = page.waitForResponse(r => new URL(r.url()).pathname === '/api/extend_session');
        await page.locator('#session-timer-badge').focus();
        await page.locator('#session-timer-badge').press('Enter');
        assert.equal((await extended).status(), 200);
        evidence.steps.push('native session-extension button works with Enter');
    }
    for (const skin of ['standard', 'edge']) {
        await goto('/mypage');
        await page.locator('#roadmap-skin').selectOption(skin);
        const save = page.waitForResponse(r => new URL(r.url()).pathname === '/api/user_settings' && r.request().method() === 'POST');
        await page.locator('#roadmap-preferences-save').tap();
        assert.equal((await save).status(), 200);
        await page.waitForFunction(skin => document.documentElement.dataset.layoutSkin === skin, skin);
        for (const route of ['/portal', '/my_equipment', '/public_equipment', '/mypage', '/dashboard', ...(workflowVariant ? ['/my_approvals'] : [])]) {
            await goto(route);
            if (route === '/portal') await page.waitForFunction(() => document.querySelectorAll('.menu-card').length > 0);
            if (route.includes('equipment')) await page.waitForFunction(() => document.getElementById('roadmap-page').textContent.length > 0);
            if (route === '/dashboard') await page.waitForFunction(() => document.getElementById('statTotalEq').textContent !== '-');
            for (const [width, height] of [[320, 568], [360, 800], [390, 844], [412, 915]]) {
                await page.setViewportSize({width, height});
                await page.evaluate(() => scrollTo(0, 0));
                await capture(skin, route, width, height);
                if (route.includes('equipment')) {
                    if (headerCsvVariant) {
                        assert.equal(await page.locator('#roadmap-csv-actions').isVisible(), false);
                        await page.locator('#roadmap-csv-toggle').tap();
                        assert.equal(await page.locator('#roadmap-csv-actions').isVisible(), true);
                        await page.evaluate(() => scrollTo(0, 0));
                        await capture(skin, route, width, height, 'csv');
                        await page.locator('#roadmap-csv-toggle').tap();
                        assert.equal(await page.locator('#roadmap-csv-actions').isVisible(), false);
                        await page.evaluate(() => scrollTo(0, 0));
                    }
                    assert.equal(await page.locator('#roadmap-advanced').isVisible(), false);
                    await searchTap('#roadmap-search-toggle');
                    assert.equal(await page.locator('#roadmap-advanced').isVisible(), true);
                    await capture(skin, route, width, height, 'advanced');
                    // Real select interaction, then tap submit and collapse; read-only queries only.
                    await page.locator('#roadmap-filter [name="status"]').selectOption('ACTIVE');
                    await searchTap('#roadmap-filter button[type="submit"]');
                    await searchTap('#roadmap-search-toggle');
                    assert.equal(await page.locator('#roadmap-advanced').isVisible(), false);
                    const values = await page.evaluate(() => Object.fromEntries(Roadmap.parameters()));
                    assert.equal(Object.hasOwn(values, 'status'), false);
                    assert.equal(await page.locator('#roadmap-filter [name="status"]').inputValue(), 'ACTIVE');
                }
            }
            if (readabilityVariant && ['/my_equipment', '/mypage'].includes(route)) {
                for (const width of [320, 390]) {
                    await page.setViewportSize({width, height: 844});
                    if (route === '/my_equipment') {
                        await page.locator('#btnOpenAddModal').tap();
                        await page.locator('#equipmentModal').waitFor({state: 'visible'});
                        await checkDialog(skin, '#equipmentModal', width);
                        await page.locator('#equipmentModalHeader [onclick="closeModal()"]').tap();
                    } else {
                        await page.locator('[onclick="openProfileModal()"]').tap();
                        await checkDialog(skin, '#profileModal', width);
                        await page.locator('#profileModal [onclick="closeProfileModal()"]').first().tap();
                        await page.locator('button[onclick*="emailModal"][onclick*="remove"]').tap();
                        await checkDialog(skin, '#emailModal', width);
                        await page.locator('#emailModal button[onclick*="add"]').tap();
                        if (workflowVariant) {
                            for (const [button, dialog] of [['openPasswordModal','passwordModal'],['openWithdrawModal','withdrawModal']]) {
                                await page.locator('#' + button).tap();
                                assert.equal(await page.locator('#' + dialog).evaluate(el => el.open), true);
                                await checkDialog(skin, '#' + dialog, width);
                                await page.keyboard.press('Escape');
                                assert.equal(await page.locator('#' + dialog).evaluate(el => el.open), false);
                                assert.equal(await page.locator('#' + button).evaluate(el => el === document.activeElement), true);
                            }
                        }
                    }
                }
            }
            if (unifiedUi && route === '/my_equipment') {
                for (const width of [320, 390]) {
                    await page.setViewportSize({width, height: 844});
                    const draftResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/api/equipment'
                        && new URL(r.url()).searchParams.get('is_draft') === '1');
                    await page.locator('#btnToggleDrafts').tap();
                    assert.equal((await draftResponse).status(), 200);
                    assert.equal(await page.locator('#btnOpenAddModal').isVisible(), false);
                    assert.equal(await page.locator('#pageMainHeader').innerText(), workflowVariant ? '나의 임시저장 목록' : '📁 나의 임시저장 목록');
                    await page.evaluate(() => scrollTo(0, 0));
                    await capture(skin, route, width, 844, 'drafts');
                    const normalResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/api/equipment'
                        && !new URL(r.url()).searchParams.has('is_draft'));
                    await page.locator('#btnToggleDrafts').tap();
                    assert.equal((await normalResponse).status(), 200);
                    assert.equal(await page.locator('#btnOpenAddModal').isVisible(), true);
                    assert.equal(await page.locator('#pageMainHeader').innerText(), '나의 장비');
                }
                evidence.steps.push(skin + ': draft list and return action at 320/390; read-only equipment queries');
            }
        }
        await goto('/portal');
        await page.waitForFunction(() => document.querySelectorAll('.menu-card').length > 0);
        await Promise.all([page.waitForURL(url => url.pathname === '/my_equipment'),
            page.locator('#menuContainer a[href="/my_equipment"]').tap()]);
        assert.equal(await page.locator('#smart-back-btn').isEnabled(), true);
        await Promise.all([page.waitForURL(url => url.pathname === '/portal'), page.locator('#smart-back-btn').tap()]);
        await page.waitForFunction(() => document.querySelectorAll('.menu-card').length > 0);
        await Promise.all([page.waitForURL(url => url.pathname === '/public_equipment'),
            page.locator('#menuContainer a[href="/public_equipment"]').tap()]);
        await Promise.all([page.waitForURL(url => url.pathname === '/portal'), page.locator('#parent-menu-link').tap()]);
    }
    assert.equal((await context.request.get(origin + '/api/users')).status(), 403);
    assert.deepEqual(evidence.pageErrors, []); assert.deepEqual(evidence.httpErrors, []);
    assert.deepEqual(evidence.forbiddenRequests, []);
    evidence.steps.push(workflowVariant ? 'two skins x six screens x four portrait viewports' : 'two skins x five screens x four portrait viewports', '16 advanced-search portrait states',
        'touch search, hidden-filter exclusion, history back and parent navigation; user permission unchanged');
    if (headerCsvVariant) evidence.steps.push('16 CSV disclosure states; bounded left/center/right navigation');
    evidence.status = 'pass';
} catch (error) {
    failure = error; evidence.status = 'failed'; evidence.error = error.message.slice(0, 400);
} finally {
    if (loggedIn && original) {
        try {
            await goto('/mypage');
            evidence.preferencesRestored = await page.evaluate(async original => {
                const response = await fetch('/api/user_settings', {method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken()},
                    body: JSON.stringify({theme: original.theme || 'system', layout_skin: original.layout_skin,
                        deadline_email_opt_in: original.deadline_email_opt_in})});
                const {settings} = await response.json();
                return response.ok && settings.theme === (original.theme || 'system') &&
                    settings.layout_skin === original.layout_skin && settings.deadline_email_opt_in === original.deadline_email_opt_in;
            }, original);
            assert.equal(evidence.preferencesRestored, true);
            await page.goto(origin + '/logout', {waitUntil: 'networkidle'});
            evidence.loggedOut = page.url().includes('/login');
            assert.equal(evidence.loggedOut, true);
        } catch { failure ||= new Error('Test-account cleanup requires attention'); evidence.cleanupError = true; }
    }
    await context.close(); await browser.close();
    writeFileSync(path.join(output, 'portrait-verification.json'), JSON.stringify(evidence, null, 2) + '\n');
}
console.log(JSON.stringify({status: evidence.status, measurements: evidence.screens.length,
    preferencesRestored: evidence.preferencesRestored, loggedOut: evidence.loggedOut, error: evidence.error,
    pageErrors: evidence.pageErrors, httpErrors: evidence.httpErrors, steps: evidence.steps}));
if (failure) process.exitCode = 1;
