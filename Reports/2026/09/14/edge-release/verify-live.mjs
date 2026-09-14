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
const uxVariant = headerCsvVariant || process.env.EQM_LIVE_VARIANT === 'ux';
const centeredVariant = uxVariant || process.env.EQM_LIVE_VARIANT === 'center';
const output = workflowVariant ? path.resolve(here, '../menu-workflows/live') : unifiedUi ? path.resolve(here, '../unified-ui/live') : headingRollback ? path.resolve(here, '../heading-rollback/live') : shellVariant ? path.resolve(here, '../responsive-shell/live') : readabilityVariant ? path.resolve(here, '../table-button-readability/live') : compactVariant ? path.resolve(here, '../compact-navigation/live') : headerCsvVariant ? path.resolve(here, '../header-csv/live') : uxVariant ? path.resolve(here, '../ui-navigation-search/live') : centeredVariant ? path.resolve(here, '../edge-center/live') : here;
const origin = 'https://nekohost.org';
if (process.env.EQM_LIVE_EDGE !== 'approved') throw new Error('Requires approved test-account smoke test.');
const {chromium} = createRequire(import.meta.url)('playwright');
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
const context = await browser.newContext({viewport: {width: 1920, height: 1080}, reducedMotion: 'reduce'});
const evidence = {origin, account: 'guide_test_user', screens: [], httpErrors: [], pageErrors: [], forbiddenRequests: [], steps: []};
const allowedHosts = new Set(['nekohost.org', 'cdn.tailwindcss.com', 'cdnjs.cloudflare.com', 'cdn.jsdelivr.net']);
await context.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url());
    if (!allowedHosts.has(url.hostname)) return route.abort();
    if (!['GET', 'HEAD'].includes(req.method()) && !(url.origin === origin && req.method() === 'POST'
        && ['/login', '/api/user_settings', '/api/extend_session'].includes(url.pathname))) {
        evidence.forbiddenRequests.push({method: req.method(), path: url.pathname});
        return route.abort();
    }
    await route.continue();
});
const page = await context.newPage();
page.on('pageerror', error => evidence.pageErrors.push(error.message.slice(0, 200)));
page.on('response', response => {
    const url = new URL(response.url());
    if (url.origin === origin && response.status() >= 500) evidence.httpErrors.push({path: url.pathname, status: response.status()});
});
let original, loggedIn = false, failure;
mkdirSync(path.join(output, 'screenshots'), {recursive: true});
async function goto(route) {
    const result = await page.goto(origin + route, {waitUntil: 'networkidle'});
    assert.equal(result.status(), 200, route);
    if (route !== '/login') {
        await page.waitForFunction(() => window.userSettings && Object.hasOwn(window.userSettings, 'layout_skin'));
        assert.ok(!page.url().includes('/login'), 'login must persist at ' + route);
    }
}
async function screenshot(name) {
    await page.screenshot({path: path.join(output, 'screenshots', name + '.png'), fullPage: true,
        mask: [page.locator('input[type="password"]')]});
}
async function metrics(route, width) {
    await page.setViewportSize({width, height: 1080});
    // setViewportSize completes before the browser's resize/ResizeObserver frame.
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const m = await page.evaluate(() => {
        const r = el => {const b = el.getBoundingClientRect(); return {x: b.x, y: b.y, width: b.width, height: b.height};};
        const grid = document.getElementById('menuContainer');
        return {width: innerWidth, skin: document.documentElement.dataset.layoutSkin,
            overflow: document.documentElement.scrollWidth - innerWidth,
            main: r(document.querySelector('.app-main')),
            nav: r(document.querySelector('.app-nav-inner')), navRow: r(document.querySelector('.app-nav-row')),
            navTitle: r(document.querySelector('.app-nav-title')), navLinks: r(document.querySelector('.app-nav-links')),
            navControls: r(document.querySelector('.app-nav-controls')),
            navButtons: [...document.querySelectorAll('.app-nav-links .app-nav-link')].map(r),
            navHistory: document.querySelector('.app-nav-history') && r(document.querySelector('.app-nav-history')),
            navTools: document.querySelector('.app-nav-tools') && r(document.querySelector('.app-nav-tools')),
            navAccount: document.querySelector('.app-nav-account') && r(document.querySelector('.app-nav-account')),
            rightChildren: [...document.querySelectorAll('.app-nav-tools > *, .app-nav-account > *')].map(r),
            pageHeadings: [...document.querySelectorAll('.app-page-heading')].map(r),
            cards: grid ? [...grid.children].map(r) : [],
            tracks: grid ? getComputedStyle(grid).gridTemplateColumns.split(' ').length : 0,
            panels: [...document.querySelectorAll('.account-panel')].map(r),
            centeredRegions: [...document.querySelectorAll('.account-layout, .edge-filter-region, .edge-overview-region, .edge-panel-grid')]
                .filter(el => el.getBoundingClientRect().width > 0).map(r),
            metricGroups: [...document.querySelectorAll('.edge-metric-grid')]
                .filter(el => el.getBoundingClientRect().width > 0)
                .map(el => [...el.children].filter(c => c.getBoundingClientRect().width > 0).map(r)),
            tables: [...document.querySelectorAll('main .overflow-x-auto')].filter(el => el.getBoundingClientRect().width).map(r)};
    });
    if (shellVariant) {
        m.shell = await page.evaluate(responsiveShellSnapshot);
        assertResponsiveShell(assert, m.shell, route + '@' + width);
    }
    if (readabilityVariant) {
        m.readability = await page.evaluate(readabilitySnapshot);
        assertReadability(assert, m.readability, route + '@' + width);
    }
    evidence.screens.push({route, ...m});
    assert.ok(m.overflow <= 1, route + '@' + width + ': no page overflow');
    if (headerCsvVariant) {
        assert.ok(m.nav.width <= 1280);
        assert.ok(Math.abs(m.navTitle.x + m.navTitle.width / 2 - width / 2) < 1, 'true title center');
        assert.ok(Math.abs(m.navLinks.x - m.navRow.x) < 1, 'left navigation');
        assert.ok(Math.abs(m.navControls.x + m.navControls.width - m.navRow.x - m.navRow.width) < 1, 'right controls');
        for (const heading of m.pageHeadings) {
            assert.ok(heading.width <= 1217);
            assert.ok(Math.abs(heading.x + heading.width / 2 - width / 2) < 1);
        }
    }
    if (compactVariant && !shellVariant) {
        const centerY = r => r.y + r.height / 2;
        const [home, back, parent] = m.navButtons;
        assert.ok(Math.abs(centerY(home) - centerY(m.navHistory)) < 1);
        assert.ok(back.x > home.x + home.width);
        if (parent) { assert.equal(parent.x, back.x); assert.ok(parent.y >= back.y + back.height - 1); }
        else assert.ok(Math.abs(centerY(home) - centerY(back)) < 1);
        if (width >= 600) {
            assert.ok(Math.abs(centerY(m.navLinks) - centerY(m.navTitle)) < 1);
            assert.ok(Math.abs(centerY(m.navControls) - centerY(m.navTitle)) < 1);
        } else {
            assert.ok(m.navTitle.y + m.navTitle.height <= Math.min(m.navLinks.y, m.navControls.y) + 1);
            assert.ok(Math.abs(centerY(m.navLinks) - centerY(m.navControls)) < 1);
        }
        assert.ok(m.navLinks.x + m.navLinks.width <= m.navControls.x + 1);
        assert.ok(m.rightChildren.every(r => r.x >= m.navControls.x - 1 && r.x + r.width <= m.navControls.x + m.navControls.width + 1));
        assert.ok(m.navAccount.y >= m.navTools.y + m.navTools.height - 1);
        assert.ok(m.nav.height < 120, 'compact normal header height');
    }
    if (centeredVariant && m.skin === 'edge') {
        for (const group of [m.cards, ...m.metricGroups, ...m.centeredRegions.map(r => [r])]) {
            if (!group.length) continue;
            const left = Math.min(...group.map(r => r.x));
            const right = Math.max(...group.map(r => r.x + r.width));
            assert.ok(Math.abs((left + right) / 2 - width / 2) < 1, route + '@' + width + ': centered content');
        }
    }
    return m;
}
async function saveLayout(value) {
    await page.locator('#roadmap-skin').selectOption(value);
    const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/user_settings' && r.request().method() === 'POST');
    await page.locator('#roadmap-preferences-save').click();
    assert.equal((await response).status(), 200);
    await page.waitForFunction(value => document.documentElement.dataset.layoutSkin === value, value);
    await page.waitForFunction(() => document.getElementById('roadmap-preferences-message').textContent === '설정을 저장했습니다.');
}
try {
    await goto('/login');
    let creds = credentials();
    await page.locator('#LoginId').fill(creds.login);
    await page.locator('#Password').fill(creds.password);
    creds.password = ''; creds = null;
    await Promise.all([page.waitForURL(origin + '/portal'), page.locator('#loginForm button[type="submit"]').click()]);
    loggedIn = true;
    await page.waitForFunction(() => document.querySelectorAll('#menuContainer > a').length > 0);
    original = await page.evaluate(async () => (await (await fetch('/api/user_settings')).json()).settings);
    evidence.originalAppearance = {theme: original.theme || 'system', skin: original.layout_skin, deadlineOptIn: original.deadline_email_opt_in};
    evidence.steps.push('real login succeeded');
    for (const filename of ['css/layout.css', 'css/roadmap.css', ...(uxVariant ? ['js/navigation.js', 'js/menu_cards.js', 'js/roadmap_equipment.js', 'js/session_timer.js'] : [])]) {
        const response = await context.request.get(origin + '/static/' + filename);
        assert.equal(response.status(), 200);
        const actual = createHash('sha256').update(await response.body()).digest('hex');
        const expected = createHash('sha256').update(readFileSync(path.join(root, 'static', filename))).digest('hex');
        assert.equal(actual, expected, filename + ': domain bytes match local deployment');
    }
    evidence.steps.push('domain static asset hashes match deployment');
    await goto('/mypage');
    for (const selector of ['[name="theme_setting"]', '#roadmap-skin', '#roadmap-opt-in', '#roadmap-preferences-save']) {
        assert.ok(await page.locator('#account-preferences ' + selector).count(), selector);
    }
    await saveLayout('standard');
    assert.equal((await metrics('/mypage-standard', 1920)).main.width, 672);
    await saveLayout('edge');
    assert.ok((await metrics('/mypage-edge', 1920)).panels[1].x > 24);
    await page.reload({waitUntil: 'networkidle'});
    await page.waitForFunction(() => document.documentElement.dataset.layoutSkin === 'edge');
    assert.equal(await page.locator('#roadmap-skin').inputValue(), 'edge');
    assert.equal(await page.locator('#roadmap-opt-in').isChecked(), original.deadline_email_opt_in === true);
    evidence.steps.push('layout UI save and reload persistence; notification consent unchanged');
    let themeResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/api/user_settings' && r.request().method() === 'POST');
    await page.locator('[name="theme_setting"][value="dark"]').check();
    if (original.theme === 'dark') {
        // Existing dark selection emits no change; deliberately toggle first.
        await page.locator('[name="theme_setting"][value="light"]').check();
        assert.equal((await themeResponse).status(), 200);
        themeResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/api/user_settings' && r.request().method() === 'POST');
        await page.locator('[name="theme_setting"][value="dark"]').check();
    }
    assert.equal((await themeResponse).status(), 200);
    await page.waitForFunction(() => document.documentElement.classList.contains('dark'));
    await page.waitForFunction(() => getComputedStyle(document.body).backgroundColor === 'rgb(15, 23, 42)');
    await metrics('/mypage-dark-edge', 1440);
    await screenshot('01-mypage-edge-dark-1440');
    for (const width of [320, 390, 768, 1199, 1200, 1920, 2560]) {
        const m = await metrics('/mypage-edge', width);
        assert.equal(m.panels[1].x > m.panels[0].x, width >= 1200);
    }
    await page.locator('[onclick="openProfileModal()"]').click();
    assert.equal(await page.locator('#editLoginId').inputValue(), 'guide_test_user');
    await page.locator('#profileModal [onclick="closeProfileModal()"]').first().click();
    evidence.steps.push('profile modal loads test account; no profile submit');
    themeResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/api/user_settings' && r.request().method() === 'POST');
    await page.locator('[name="theme_setting"][value="light"]').check();
    assert.equal((await themeResponse).status(), 200);
    await page.waitForFunction(() => getComputedStyle(document.body).backgroundColor === 'rgb(241, 245, 249)');
    await metrics('/mypage-light-edge', 390);
    await screenshot('02-mypage-edge-mobile-390');
    await goto('/portal');
    await page.waitForFunction(() => document.querySelectorAll('#menuContainer > a').length > 0);
    evidence.menuCount = await page.locator('#menuContainer > a').count();
    for (const [width, expected] of [[390, 1], [1440, 4], [1920, 5], [2560, 7]]) {
        const m = await metrics('/portal', width);
        assert.equal(m.tracks, expected);
        assert.ok(m.cards.every(c => c.width <= (width < 640 ? width - 24 : 305)));
    }
    await metrics('/portal', 1920);
    await screenshot('03-portal-edge-1920');
    for (const route of ['/my_equipment', '/public_equipment']) {
        await goto(route);
        await page.waitForFunction(() => document.getElementById('roadmap-page').textContent.length > 0);
        const wide = await metrics(route, 1920);
        assert.ok(wide.tables.some(r => r.width > 1800), route + ': wide equipment table');
        await screenshot(route === '/my_equipment' ? '04-my-equipment-edge-1920' : '05-public-equipment-edge-1920');
        for (const width of [320, 390, 768, 1440]) await metrics(route, width);
        await page.locator('#roadmap-filter button[type="submit"]').click();
        await page.waitForFunction(() => document.getElementById('roadmap-page').textContent.length > 0);
    }
    if (uxVariant) {
        await goto('/portal');
        await page.waitForFunction(() => document.querySelectorAll('.menu-card').length > 0);
        assert.equal(await page.locator('#parent-menu-link').count(), 0);
        const descriptions = await page.locator('.menu-card-description').evaluateAll(elements => elements.map(el => ({
            height: el.getBoundingClientRect().height, clamp: getComputedStyle(el).webkitLineClamp,
            fullText: el.textContent === el.title && el.title === el.closest('a').title
        })));
        assert.ok(descriptions.every(d => d.height === 60 && d.clamp === '3' && d.fullText));
        await Promise.all([page.waitForURL(url => url.pathname === '/my_equipment'), page.locator('#menuContainer a[href="/my_equipment"]').click()]);
        assert.equal(await page.locator('#smart-back-btn').isEnabled(), true);
        await Promise.all([page.waitForURL(url => url.pathname === '/portal'), page.locator('#smart-back-btn').click()]);
        await page.waitForFunction(() => document.querySelectorAll('.menu-card').length > 0);
        await Promise.all([page.waitForURL(url => url.pathname === '/public_equipment'), page.locator('#menuContainer a[href="/public_equipment"]').click()]);
        assert.equal(await page.locator('#parent-menu-link').getAttribute('href'), '/portal');
        await Promise.all([page.waitForURL(url => url.pathname === '/portal'), page.locator('#parent-menu-link').click()]);
        evidence.steps.push('live history back, parent-to-portal, root parent omitted and native full-description title');
        for (const route of ['/my_equipment', '/public_equipment']) {
            await goto(route);
            await page.waitForFunction(() => document.getElementById('roadmap-page').textContent.length > 0);
            assert.equal(await page.locator('#roadmap-advanced').isVisible(), false);
            if (headerCsvVariant) {
                let requests = 0;
                const observe = request => { if (new URL(request.url()).pathname.startsWith('/api/equipment')) requests++; };
                page.on('request', observe);
                assert.equal(await page.locator('#roadmap-csv-actions').isVisible(), false);
                await page.locator('#roadmap-csv-toggle').click();
                assert.equal(await page.locator('#roadmap-csv-actions').isVisible(), true);
                assert.equal(await page.locator('#roadmap-csv-toggle').getAttribute('aria-expanded'), 'true');
                for (const selector of ['#roadmap-export', '#roadmap-import', 'a[href="/api/equipment/csv/export?template=1"]']) {
                    assert.equal(await page.locator('#roadmap-csv-actions ' + selector).isVisible(), true);
                }
                await page.locator('#roadmap-import').click();
                assert.equal(await page.locator('#roadmap-csv-dialog').evaluate(el => el.open), true);
                await page.locator('#roadmap-csv-dialog [data-roadmap-close]').click();
                await page.locator('#roadmap-csv-toggle').click();
                assert.equal(await page.locator('#roadmap-csv-actions').isVisible(), false);
                page.off('request', observe);
                assert.equal(requests, 0, 'CSV disclosure/dialog do not issue data requests');
            }
            for (const width of (compactVariant ? [320, 390, 599, 600, 768, 960, 1023, 1280, 1920] : [320, 390, 1920])) {
                await metrics(route + '-ux-nav', width);
                if (compactVariant) {
                    if ([768, 960].includes(width)) await screenshot(route.slice(1) + '-compact-' + width);
                    continue; // The metrics above assert the stacked layout, not the previous one-row button layout.
                }
                const links = await page.locator('.app-nav-links > *').evaluateAll(elements => elements.map(el => {
                    const r = el.getBoundingClientRect(); return {x: r.x, right: r.right, y: r.y};
                }));
                assert.equal(links[0].y, links[1].y);
                assert.equal(links[1].y, links[2].y);
                assert.ok(links[1].x - links[0].right <= 5 && links[2].x - links[1].right <= 5);
            }
            async function searchAction(action) {
                const pending = page.waitForResponse(r => new URL(r.url()).pathname === '/api/equipment');
                await action();
                const result = await pending;
                assert.equal(result.status(), 200);
                await page.waitForFunction(() => !document.getElementById('roadmap-page').textContent.includes('불러'));
                return new URL(result.url()).searchParams;
            }
            await page.locator('#roadmap-keyword').fill('UX-검증-검색어');
            let query = await searchAction(() => page.locator('#roadmap-keyword').press('Enter'));
            assert.equal(query.get('keyword'), 'UX-검증-검색어');
            assert.equal(query.has('status'), false);
            await searchAction(() => page.locator('#roadmap-search-toggle').click());
            assert.equal(await page.locator('#roadmap-advanced').isVisible(), true);
            await page.locator('#roadmap-filter [name="status"]').selectOption('REPAIR');
            query = await searchAction(() => page.locator('#roadmap-filter button[type="submit"]').click());
            assert.equal(query.get('status'), 'REPAIR');
            await screenshot(route.slice(1) + '-advanced-1920');
            query = await searchAction(() => page.locator('#roadmap-search-toggle').click());
            assert.equal(query.has('status'), false);
            assert.equal(query.get('keyword'), 'UX-검증-검색어');
            assert.equal(await page.locator('#roadmap-filter [name="status"]').inputValue(), 'REPAIR');
            assert.equal(await page.locator('#roadmap-filter [name="status"]').isDisabled(), true);
            query = await searchAction(() => page.locator('#roadmap-search-toggle').click());
            assert.equal(query.get('status'), 'REPAIR');
            await searchAction(() => page.locator('#roadmap-filter button[type="reset"]').click());
            assert.equal(await page.locator('#roadmap-keyword').inputValue(), '');
            assert.equal(await page.locator('#roadmap-filter [name="status"]').inputValue(), '');
            await searchAction(() => page.locator('#roadmap-search-toggle').click());
            await screenshot(route.slice(1) + '-simple-1920');
            await goto(route + '?status=ACTIVE');
            assert.equal(await page.locator('#roadmap-advanced').isVisible(), true);
            assert.equal(await page.locator('#roadmap-filter [name="status"]').inputValue(), 'ACTIVE');
        }
        evidence.steps.push('live my/public keyword Enter, advanced filters, collapse excludes hidden conditions, reopen restores, reset and legacy URLs');
    }
    await goto('/dashboard');
    await page.waitForFunction(() => document.getElementById('statTotalEq').textContent !== '-');
    const wideDashboard = await metrics('/dashboard', 1920);
    assert.equal(await page.evaluate(() => typeof Chart === 'function' && !!Chart.getChart('categoryChart') && !!Chart.getChart('manufacturerChart')), true);
    assert.ok(wideDashboard.main.width > 1800);
    await screenshot('06-dashboard-edge-1920');
    for (const width of [320, 390, 768, 1440]) await metrics('/dashboard', width);
    const admin = await context.request.get(origin + '/api/users');
    assert.equal(admin.status(), 403, 'test account remains unprivileged');
    evidence.steps.push('live portal, my/public lists, filters, rendered Chart.js and unprivileged API boundary');
    if (workflowVariant) {
        await goto('/portal');
        await page.locator('#menuContainer a[href="/my_approvals"]').waitFor();
        assert.equal((await page.locator('#menuContainer a[href="/my_approvals"] h2').innerText()).trim(), '나의 결재함');
        await Promise.all([page.waitForURL(url => url.pathname === '/my_approvals'), page.locator('#menuContainer a[href="/my_approvals"]').click()]);
        await page.waitForFunction(() => document.getElementById('my-approvals-page').textContent.includes('페이지'));
        assert.equal(await page.locator('.app-nav-links > a').first().innerText(), '메인 포털');
        assert.equal(await page.locator('.app-nav-inner i, .app-nav-avatar').count(), 0);
        for (const status of ['', 'PENDING', 'APPROVED', 'REJECTED']) {
            await page.locator('#my-approvals-status').selectOption(status);
            const request = page.waitForResponse(r => new URL(r.url()).pathname === '/api/my_approvals');
            await page.locator('#my-approvals-filter button').click();
            const response = await request;
            assert.equal(response.status(), 200);
            const data = await response.json();
            assert.equal(data.success, true);
            // Actual server has no requests; populated history is tested only in isolated DB.
            assert.equal(data.total, 0);
            assert.deepEqual(data.data, []);
        }
        for (const width of [320,390,768,1440,1920]) await metrics('/my_approvals', width);
        await screenshot('07-my-approvals-edge-1920');
        assert.equal((await context.request.get(origin + '/api/permissions')).status(), 403);
        const oldInbox = await context.request.get(origin + '/approvals', {maxRedirects: 0});
        assert.equal(oldInbox.status(), 302);
        assert.equal(oldInbox.headers().location, '/my_approvals');
        await goto('/mypage');
        assert.equal((await page.locator('.app-content-title').innerText()).trim(), '내 정보');
        assert.equal(await page.locator('main i').count(), 0);
        for (const [button, dialog] of [['openPasswordModal','passwordModal'],['openWithdrawModal','withdrawModal']]) {
            assert.equal(await page.locator('#' + dialog).evaluate(el => el.open), false);
            assert.equal(await page.locator('#account-profile #' + button).count(), 1);
            await page.locator('#' + button).click();
            assert.equal(await page.locator('#' + dialog).evaluate(el => el.open), true);
            await page.keyboard.press('Escape');
            assert.equal(await page.locator('#' + dialog).evaluate(el => el.open), false);
            assert.equal(await page.locator('#' + button).evaluate(el => el === document.activeElement), true);
        }
        await page.setViewportSize({width:320,height:568});
        const labels = {light:'라이트', dark:'다크', system:'시스템'};
        const next = {light:'dark', dark:'system', system:'light'};
        for (let i=0;i<3;i++) {
            const current = await page.evaluate(() => window.userSettings.theme || 'system');
            assert.equal(await page.locator('#theme-toggle-label').innerText(), labels[current]);
            const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/user_settings' && r.request().method() === 'POST');
            await page.locator('#theme-toggle-btn').click();
            assert.equal((await response).status(), 200);
            await page.waitForFunction(expected => document.getElementById('theme-toggle-label').textContent === expected, labels[next[current]]);
            await metrics('/mypage-theme-' + next[current],320);
        }
        evidence.steps.push('personal portal entry, all empty-status filters and legacy redirect; admin API denied',
            'password/withdraw dialogs open/Escape/focus return without submission; all three text theme modes at 320px');
    }
    assert.deepEqual(evidence.forbiddenRequests, []);
    assert.deepEqual(evidence.httpErrors, []);
    assert.deepEqual(evidence.pageErrors, []);
    evidence.status = 'pass';
} catch (error) {
    failure = error;
    evidence.status = 'failed';
    // Controlled assertion messages only; never request headers/body or credential values.
    evidence.error = error.message.slice(0, 400);
} finally {
    if (loggedIn && original) {
        try {
            if (!page.url().startsWith(origin) || page.url().includes('/login')) await goto('/mypage');
            const restored = await page.evaluate(async original => {
                const response = await fetch('/api/user_settings', {method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.getCSRFToken()},
                    body: JSON.stringify({theme: original.theme || 'system', layout_skin: original.layout_skin,
                        deadline_email_opt_in: original.deadline_email_opt_in})});
                if (!response.ok) return false;
                const {settings} = await response.json();
                return settings.theme === (original.theme || 'system') && settings.layout_skin === original.layout_skin
                    && settings.deadline_email_opt_in === original.deadline_email_opt_in;
            }, original);
            evidence.preferencesRestored = restored;
            if (!restored) failure ||= new Error('Test account preferences could not be restored');
            await page.goto(origin + '/logout', {waitUntil: 'networkidle'});
            evidence.loggedOut = page.url().includes('/login');
        } catch {
            evidence.cleanupError = 'restore/logout requires attention';
            failure ||= new Error('Test account cleanup failed');
        }
    }
    await context.close();
    await browser.close();
    writeFileSync(path.join(output, 'live-verification.json'), JSON.stringify(evidence, null, 2) + '\n');
}
console.log(JSON.stringify({status: evidence.status, steps: evidence.steps, measurements: evidence.screens.length,
    menuCount: evidence.menuCount, preferencesRestored: evidence.preferencesRestored, loggedOut: evidence.loggedOut,
    error: evidence.error, httpErrors: evidence.httpErrors, pageErrors: evidence.pageErrors}));
if (failure) process.exitCode = 1;
