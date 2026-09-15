// Opt-in static browser QA; no Flask/app import, DB access, or live HTTP requests.
// EDGE_LAYOUT_BROWSER=1 node --test tests/test_edge_layout_browser.mjs
// Requires Playwright (NODE_PATH if bundled), Edge, and read-only Jinja rendering via
// eqmgmt-backup SSH. Local templates + synthetic context travel over stdin;
// the remote interpreter uses DictLoader and writes no files. App scripts only run
// in explicitly mocked control tests; every external HTTP request is blocked.
import {readFileSync, readdirSync, mkdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readabilitySnapshot, assertReadability} from './helpers/readability.mjs';
import {responsiveShellSnapshot, assertResponsiveShell} from './helpers/responsive_shell.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const read = name => readFileSync(path.join(root, name), 'utf8');
function assertCentered(rects, width, label) {
    assert.ok(rects.length, label + ': visible content required');
    const left = Math.min(...rects.map(r => r.x));
    const right = Math.max(...rects.map(r => r.x + r.width));
    assert.ok(Math.abs((left + right) / 2 - width / 2) < 1, label + ': centered visible group');
}
const pages = ['portal', 'admin_center', 'mypage', 'dashboard', 'index', 'audit_logs',
    'access_logs', 'access_logs_error_ips', 'users_management', 'master_management',
    'permissions', 'approvals', 'my_approvals', 'lineup_management', 'backup_restore', 'maintenance_admin'];
const widths = [320, 390, 640, 768, 1024, 1440, 1920, 2560];
const screenshotDir = process.env.EDGE_LAYOUT_SCREENSHOTS;
const renderScript = [
    'import sys, json, jinja2',
    'data = json.load(sys.stdin)',
    'env = jinja2.Environment(loader=jinja2.DictLoader(data["templates"]), autoescape=True)',
    'env.globals["url_for"] = lambda endpoint, **kw: "/static/" + kw["filename"] if endpoint == "static" else "/" + endpoint',
    'for name, source in data["templates"].items():',
    '    env.parse(source, name=name)',
    'result = {name: env.get_template(name + ".html").render(**data["context"]) for name in data["pages"]}',
    'result["index_public"] = env.get_template("index.html").render(**dict(data["context"], mode="public"))',
    'print(json.dumps(result, ensure_ascii=False))'
].join('\n');
const shellQuote = s => "'" + s.replaceAll("'", "'\\''") + "'";
function renderTemplates() {
    const templates = Object.fromEntries(readdirSync(path.join(root, 'templates'))
        .filter(n => n.endsWith('.html')).map(n => [n, read('templates/' + n)]));
    const result = spawnSync('ssh', ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'eqmgmt-backup',
        '/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python -c ' + shellQuote(renderScript)], {
        input: JSON.stringify({templates, pages, context: {
            user: {UserId: 999999, LoginId: 'edge_fixture', Name: '검증 사용자', NickName: '테스트', Role: 'USER', Email: 'layout@example.test'},
            mode: 'my', csrf_token: 'offline-fixture', maintenance: {state: 'NORMAL'}, restore_confirmation: '복원 확인'
        }}), encoding: 'utf8', timeout: 20000, maxBuffer: 20 * 1024 * 1024
    });
    assert.equal(result.status, 0, 'Read-only Jinja rendering failed: ' + (result.error || result.stderr));
    return JSON.parse(result.stdout);
}
const tick = String.fromCharCode(96);
const widgetMarkup = () => read('templates/portal.html').match(new RegExp('widget\\.innerHTML = ' + tick + '([\\s\\S]*?)' + tick + ';'))[1]
    .replace(/\$\{data\.\w+\}/g, '42');

test('layout hooks and account control IDs stay explicit and unique (offline)', () => {
    const account = read('templates/mypage.html');
    for (const id of ['account-profile', 'account-preferences', 'account-security', 'account-danger',
        'roadmap-skin', 'roadmap-opt-in', 'roadmap-preferences-save', 'roadmap-preferences-message',
        'passwordForm', 'withdrawForm', 'profileForm', 'profileModal', 'emailModal']) {
        assert.equal(account.split('id="' + id + '"').length - 1, 1, id);
    }
    assert.ok(read('templates/root_frame.html').includes("filename='css/layout.css'"));
    assert.ok(read('templates/miniserver_frame.html').includes('class="app-main '));
    assert.ok(!read('static/css/roadmap.css').includes('data-layout-skin'));
    assert.ok(!read('static/css/layout.css').includes('.rounded-xl'));
});

test('previous navigation requires a same-origin, non-authentication history entry', () => {
    const fixture = {window: {}, URL, document: {readyState: 'loading', addEventListener() {}}};
    vm.runInNewContext(read('static/js/navigation.js'), fixture);
    const can = fixture.window.AppNavigation.canGoBack;
    assert.equal(can('https://fixture.test/my_equipment', 'https://fixture.test/portal', 2), true);
    for (const referrer of ['', 'https://outside.test/', 'https://fixture.test.evil.test/',
        'http://fixture.test/portal', 'https://fixture.test/login', 'https://fixture.test/logout/']) {
        assert.equal(can('https://fixture.test/my_equipment', referrer, 2), false, referrer);
    }
    assert.equal(can('https://fixture.test/my_equipment', 'https://fixture.test/portal', 1), false);
});

test('Edge/Standard real-template responsive browser matrix (opt-in)', {
    skip: process.env.EDGE_LAYOUT_BROWSER !== '1', timeout: 240000
}, async t => {
    const runCase = (name, fn) => t.test(name, {skip: Boolean(process.env.EDGE_LAYOUT_CASE && !name.includes(process.env.EDGE_LAYOUT_CASE))}, fn);
    const rendered = renderTemplates();
    const {chromium} = createRequire(import.meta.url)('playwright');
    const browser = await chromium.launch({channel: 'msedge', headless: true});
    const context = await browser.newContext({viewport: {width: 1440, height: 1080}});
    // Block every network request, including CSS/fonts/images. Synthetic fixtures only.
    await context.route('**/*', route => route.abort());
    const page = await context.newPage();
    if (screenshotDir) mkdirSync(path.resolve(root, screenshotDir), {recursive: true});
    async function load(name, skin = 'edge') {
        await page.evaluate(() => window.AppNavigation?.destroy?.());
        await page.setContent(rendered[name].replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
            .replace(/<link\b[^>]*>/gi, ''));
        await page.evaluate(skin => document.documentElement.dataset.layoutSkin = skin, skin);
        await page.addStyleTag({content: read('static/css/roadmap.css') + '\n' + read('static/css/layout.css') + '\n' + read('static/css/components.css')});
        // Deterministic snapshots must not capture a light/dark transition halfway.
        await page.addStyleTag({content: '*, *::before, *::after { transition: none !important; animation: none !important; }'});
        await page.addScriptTag({content: read('static/js/tailwindcss.js')});
        await page.evaluate(() => {
            tailwind.config = {darkMode: 'class', theme: {extend: {colors: {brand: {
                50: '#f0f9ff', 500: '#0284c7', 600: '#0284c7', 700: '#0369a1'
            }}}}};
        });
        if (name === 'portal' || name === 'admin_center') {
            await page.addScriptTag({content: read('static/js/menu_cards.js')});
            await page.evaluate(name => window.MenuCards.render(document.querySelector(name === 'portal' ? '#menuContainer' : '#admin-menus-grid'),
                Array.from({length: 9}, () => ({Url: '/my_equipment', MenuName: '장비 관리', Description: '장비 목록과 상태를 확인하고 필요한 정보를 관리합니다.'}))), name);
        }
        await page.evaluate(skin => {
            const select = document.getElementById('roadmap-skin');
            if (select) select.value = skin;
            const badge = document.getElementById('session-timer-badge');
            badge.innerHTML = '<span class="app-session-full">29분 남음</span><span class="app-session-short">29분</span>';
            badge.className = 'app-nav-control text-slate-600';
            badge.dataset.sessionState = 'normal';
            // CDN font is blocked: preserve icon boxes with neutral fixture glyphs.
            for (const icon of document.querySelectorAll('nav i')) icon.textContent = '◇';
        }, skin);
        // Generic table/layout cases exercise the selected-role state. Dedicated workflow
        // tests separately verify the real editor starts with only the role selector.
        if (name === 'permissions') await page.locator('#permission-detail').evaluate(el => el.hidden = false);
        await page.waitForFunction(() => getComputedStyle(document.querySelector('.app-main')).paddingTop === '32px');
        await page.addScriptTag({content: read('static/js/navigation.js')});
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    }
    async function screenshot(name) {
        if (screenshotDir) await page.screenshot({path: path.resolve(root, screenshotDir, name + '.png'), fullPage: true});
    }
    async function measure() {
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const result = await page.evaluate(() => {
            const rect = el => {const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height};};
            const grid = document.querySelector('.edge-card-grid');
            const cards = grid ? [...grid.children].map(rect) : [];
            const panels = [...document.querySelectorAll('.account-panel')].map(rect);
            const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
            return {
                width: innerWidth, overflow: document.documentElement.scrollWidth - innerWidth,
                main: rect(document.querySelector('.app-main')), cards, panels,
                nav: rect(document.querySelector('.app-nav-inner')),
                navRow: rect(document.querySelector('.app-nav-row')),
                title: rect(document.querySelector('.app-nav-title')),
                links: rect(document.querySelector('.app-nav-links')),
                controls: rect(document.querySelector('.app-nav-controls')),
                menuButtons: [...document.querySelectorAll('.app-nav-links .app-nav-link')].map(rect),
                history: rect(document.querySelector('.app-nav-history')),
                tools: rect(document.querySelector('.app-nav-tools')),
                account: rect(document.querySelector('.app-nav-account')),
                rightChildren: [...document.querySelectorAll('.app-nav-tools > *, .app-nav-account > *, .app-nav-role')].filter(el => el.getBoundingClientRect().width > 0).map(rect),
                pageHeadings: [...document.querySelectorAll('.app-page-heading')].map(rect),
                columns: cards.filter(c => Math.abs(c.y - cards[0].y) < 1).length,
                duplicates: ids.filter((id, i) => ids.indexOf(id) !== i),
                filters: [...document.querySelectorAll('.edge-filter-region')].map(rect),
                centeredRegions: [...document.querySelectorAll('.account-layout, .edge-filter-region, .edge-overview-region, .edge-panel-grid')]
                    .filter(el => el.getBoundingClientRect().width > 0).map(rect),
                metricGroups: [...document.querySelectorAll('.edge-metric-grid')]
                    .filter(el => el.getBoundingClientRect().width > 0)
                    .map(el => [...el.children].filter(c => c.getBoundingClientRect().width > 0).map(rect)),
                scrollRegions: [...document.querySelectorAll('main .overflow-x-auto')].filter(el => el.getBoundingClientRect().width > 0).map(rect)
            };
        });
        return {...result, shell: await page.evaluate(responsiveShellSnapshot)};
    }
    try {
        await runCase('portal cards add columns without stretching; Standard retains three', async () => {
            await load('portal');
            assert.equal(await page.locator('#dashboardWidget').evaluate(el => getComputedStyle(el).display), 'none');
            const columns = {};
            for (const width of widths) {
                await page.setViewportSize({width, height: 1080});
                const m = await measure();
                columns[width] = m.columns;
                assert.ok(m.cards.every(c => c.width <= 367), 'card width at ' + width);
                assertCentered(m.cards, width, 'portal @' + width);
            }
            assert.equal(columns[390], 1);
            assert.equal(columns[1440], 4);
            assert.equal(columns[1920], 5);
            assert.equal(columns[2560], 7);
            await page.setViewportSize({width: 1920, height: 1080});
            const cardStyle = await page.locator('#menuContainer > a').first().evaluate(el => {
                const css = getComputedStyle(el);
                return [css.padding, css.borderRadius, getComputedStyle(el.querySelector('h2')).fontSize];
            });
            await page.locator('#dashboardWidget').evaluate((el, markup) => {
                el.classList.remove('hidden'); el.innerHTML = markup;
            }, widgetMarkup());
            await screenshot('portal-edge-1920');
            await page.locator('#menuContainer').evaluate(el => [...el.children].slice(2).forEach(c => c.remove()));
            assert.ok((await measure()).cards.every(c => c.width <= 305), 'two cards still bounded');
            assertCentered((await measure()).cards, 1920, 'only two menu cards');
            for (const group of (await measure()).metricGroups) assertCentered(group, 1920, 'only two widget cards');
            assert.ok(await page.locator('#dashboardWidget > div').first().evaluate(el => el.getBoundingClientRect().width <= 225));
            await load('portal', 'standard');
            assert.equal((await measure()).columns, 3);
            assert.equal((await measure()).main.width, 1024);
            assert.deepEqual(await page.locator('#menuContainer > a').first().evaluate(el => {
                const css = getComputedStyle(el);
                return [css.padding, css.borderRadius, getComputedStyle(el.querySelector('h2')).fontSize];
            }), cardStyle, 'Standard/Edge preserve card padding, corners and text size');
            t.diagnostic('Edge portal columns: ' + JSON.stringify(columns));
        });
        await runCase('account settings group together and reflow without changing control contracts', async () => {
            await load('mypage');
            for (const selector of ['[name="theme_setting"]', '#roadmap-skin', '#roadmap-opt-in', '#roadmap-preferences-save']) {
                assert.ok(await page.locator('#account-preferences ' + selector).count(), selector);
            }
            for (const width of [390, 1024, 1199, 1200, 1440, 2560]) {
                await page.setViewportSize({width, height: 1080});
                const {panels} = await measure();
                assert.ok(panels.every(p => p.width <= 613), 'account input panel width at ' + width);
                assert.equal(panels[1].x > panels[0].x, width >= 1200, 'two columns at ' + width);
            }
            await page.setViewportSize({width: 1440, height: 1080});
            await page.evaluate(() => document.documentElement.classList.add('dark'));
            await page.locator('[name="theme_setting"][value="dark"]').check();
            assert.equal(await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(15, 23, 42)');
            await screenshot('mypage-edge-dark-1440');
            await page.setViewportSize({width: 390, height: 1080});
            await page.evaluate(() => document.documentElement.classList.remove('dark'));
            await page.locator('[name="theme_setting"][value="light"]').check();
            assert.equal(await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(241, 245, 249)');
            await screenshot('mypage-edge-390');
            await page.setViewportSize({width: 1920, height: 1080});
            for (const modal of ['emailModal', 'profileModal']) {
                const radius = await page.locator('#' + modal + ' > div').evaluate(el => {
                    el.parentElement.classList.remove('hidden');
                    return getComputedStyle(el).borderRadius;
                });
                assert.equal(radius, '12px', 'Edge does not flatten modal corners');
                const modalWidth = await page.locator('#' + modal + ' > div').evaluate(el => el.getBoundingClientRect().width);
                assert.ok(modalWidth <= 448);
                await page.locator('#' + modal).evaluate(el => el.classList.add('hidden'));
            }
            await load('mypage', 'standard');
            const m = await measure();
            assert.equal(m.main.width, 672);
            assert.equal(m.panels[0].x, m.panels[1].x);
        });
        await runCase('all authenticated screens: bounded controls, wide lists, unique IDs and no page overflow', async () => {
            const overflow = [];
            for (const name of [...pages, 'index_public']) {
                await load(name);
                for (const width of widths) {
                    await page.setViewportSize({width, height: 1080});
                    const m = await measure();
                    if (m.overflow > 1) overflow.push(name + '@' + width + ': ' + m.overflow + 'px');
                    assert.deepEqual(m.duplicates, [], name + ': duplicate IDs');
                    assert.ok(m.filters.every(f => f.width <= 1217), name + ': filters remain bounded');
                    for (const region of m.centeredRegions) assertCentered([region], width, name + ' region @' + width);
                    for (const group of m.metricGroups) if (group.length) assertCentered(group, width, name + ' metrics @' + width);
                    if (m.cards.length) assertCentered(m.cards, width, name + ' cards @' + width);
                    if (name === 'access_logs' && width === 390) {
                        const columns = await page.locator('.edge-metric-grid').evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length);
                        assert.equal(columns, 2, 'mobile compact metrics retain Standard two-column density');
                    }
                    if (width === 1920 && ['index', 'index_public', 'audit_logs', 'access_logs', 'users_management', 'master_management', 'approvals', 'my_approvals'].includes(name)) {
                        assert.ok(m.scrollRegions.some(r => r.width > 1750), name + ': list should use Edge canvas');
                    }
                    if (width === 1920 && name === 'permissions') {
                        const panel = await page.locator('.permission-detail-panel').boundingBox();
                        const workspace = await page.locator('.permission-workspace').boundingBox();
                        assert.ok(workspace.width > 1800 && m.scrollRegions.some(r => r.width >= panel.width - 44), 'role sidebar and permission table share the Edge canvas');
                    }
                }
            }
            assert.deepEqual(overflow, [], 'Page-level overflow (table-local scrolling is allowed)');
        });
        await runCase('Standard retains bounded main widths on every screen', async () => {
            await page.setViewportSize({width: 1920, height: 1080});
            for (const name of [...pages, 'index_public']) {
                await load(name, 'standard');
                const {main} = await measure();
                assert.ok(main.width >= 672 && main.width <= 1280, name + ': original Standard container');
            }
        });
        await runCase('both skins use bounded navigation, true centered titles and Standard page-heading widths', async () => {
            for (const name of [...pages, 'index_public']) {
                for (const width of [320, 390, 599, 600, 768, 960, 1024, 1920, 2560]) {
                    await page.setViewportSize({width, height: width < 640 ? 844 : 1080});
                    await load(name, 'standard');
                    const standard = await measure();
                    await load(name, 'edge');
                    const edge = await measure();
                    for (const m of [standard, edge]) {
                        assert.ok(m.nav.width <= 1280, name + ': nav width limit');
                        assertCentered([m.nav], width, name + ': nav');
                        assertCentered([m.title], width, name + ': title');
                        assert.ok(Math.abs(m.links.x - m.navRow.x) < 1, 'left navigation');
                        assert.ok(Math.abs(m.controls.x + m.controls.width - m.navRow.x - m.navRow.width) < 1, 'right controls');
                        assert.ok(m.overflow <= 1, name + '@' + width);
                        assertResponsiveShell(assert, m.shell, name + '@' + width);
                        assert.ok(m.nav.height < 120, name + '@' + width + ': compact navigation height');
                    }
                    assert.deepEqual(edge.nav, standard.nav, name + ': same nav boundary in both skins');
                    for (const [index, heading] of edge.pageHeadings.entries()) {
                        assert.ok(Math.abs(heading.width - standard.pageHeadings[index].width) <= 2, name + ': Standard heading width');
                        assertCentered([heading], width, name + ': page heading');
                    }
                    if (name === 'index' && [390, 768, 960].includes(width)) await screenshot('compact-equipment-' + width);
                }
            }
        });
        await runCase('dynamic titles reflow at whole words after text/viewport changes', async () => {
            await load('index');
            for (const width of [320, 390, 599, 600, 1920, 320]) {
                await page.setViewportSize({width, height: 844});
                for (const text of ['가나다라마 바사아자', '가나다라마 바사아자차', '장비 카탈로그 변경 요청 검토', '<img onerror=alert(1)> 새 메뉴']) {
                    await page.locator('.app-nav-title').evaluate((el,text)=>el.textContent=text,text);
                    const m = await measure();
                    assert.equal(m.shell.titleText,text);
                    assert.equal(await page.locator('.app-nav-title').getAttribute('aria-label'),text);
                    assert.equal(await page.locator('.app-nav-title img').count(),0);
                    assert.ok(m.overflow<=1);
                    if(width<600){
                        assert.equal(m.shell.titleLines.map(line=>line.text).join(' '),text);
                        if(text==='가나다라마 바사아자차') assert.equal(m.shell.titleLines.length,2);
                    } else assert.equal(m.shell.titleLines.length,0);
                }
            }
        });
        await runCase('selection buttons remain visible, reset on reload and never execute without selection', async () => {
            await load('users_management');
            await page.setViewportSize({width:320,height:844});
            const script=[...rendered.users_management.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(code=>code.includes('function renderUsers'));
            await page.evaluate(()=>{ window.selectionRequests=[]; window.fetch=async(...args)=>{selectionRequests.push(args[0]);throw new Error('No network in selection fixture');}; });
            await page.addScriptTag({content:script});
            const buttons=page.locator('[data-selection-action]');
            const state=()=>buttons.evaluateAll(items=>items.map(el=>({visible:el.getBoundingClientRect().width>0,disabled:el.disabled})));
            assert.ok((await state()).every(b=>b.visible&&b.disabled));
            await buttons.evaluateAll(items=>items.forEach(el=>el.click()));
            assert.deepEqual(await page.evaluate(()=>selectionRequests),[]);
            await screenshot('users-unselected-320');
            await page.evaluate(()=>renderUsers([1,2].map(UserId=>({UserId,LoginId:'fixture'+UserId,Name:'합성 사용자',NickName:'검증',Role:'user',IsDeactivated:'N',CreatedAt:'2026-09-14',Status:'ACTIVE'}))));
            await page.locator('.user-checkbox').first().check();
            assert.ok((await state()).every(b=>b.visible&&!b.disabled));
            assert.equal(await page.locator('#selectAllCheckbox').evaluate(el=>el.indeterminate),true);
            await page.locator('#selectAllCheckbox').check();
            assert.equal(await page.locator('.user-checkbox:checked').count(),2);
            await page.locator('#selectAllCheckbox').uncheck();
            assert.ok((await state()).every(b=>b.visible&&b.disabled));
            await page.locator('.user-checkbox').first().check();
            await page.evaluate(()=>renderUsers([]));
            assert.ok((await state()).every(b=>b.visible&&b.disabled));
            assert.equal(await page.locator('#selectAllCheckbox').isChecked(),false);
            assert.deepEqual(await page.evaluate(()=>selectionRequests),[]);
        });
        await runCase('admin related menu order survives rendering without changing portal order', async () => {
            await page.mouse.move(0,0); // A hovered card is translated, but does not create a grid gap.
            await load('admin_center');
            const entries=[['permissions','메뉴 권한 관리'],['audit_logs','보안 감사 로그'],['users_management','사용자 관리'],['approvals','전자결재함'],['master_management','마스터 데이터 관리'],['access_logs','웹 접근 로그'],['maintenance_admin','서버 점검 관리'],['backup_restore','DB 백업 및 복원'],['lineup_management','라인업 노드 관리']];
            await page.evaluate(entries=>MenuCards.render(document.querySelector('#admin-menus-grid'),MenuCards.orderAdmin(entries.map(([MenuCode,MenuName])=>({MenuCode,MenuName,Url:'/'+MenuCode,Description:'메뉴 배열 검증용 합성 설명'})))),entries);
            assert.deepEqual(await page.locator('#admin-menus-grid > a').evaluateAll(items=>items.map(el=>el.getAttribute('href'))),['/users_management','/permissions','/master_management','/lineup_management','/approvals','/audit_logs','/access_logs','/maintenance_admin','/backup_restore']);
            await page.setViewportSize({width:1440,height:1080});
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
            assert.equal(await page.locator('[data-admin-group-start]').count(),0);
            for(const skin of ['standard','edge']) for(const width of [320,390,768,1024,1440,1920,2560]) {
                await page.evaluate(skin=>document.documentElement.dataset.layoutSkin=skin,skin);
                await page.setViewportSize({width,height:1080});
                await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
                const cards=await page.locator('#admin-menus-grid > a').evaluateAll(items=>items.map(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,start:getComputedStyle(el).gridColumnStart};}));
                const columns=new Set(cards.map(c=>c.x)).size,rows=[...new Set(cards.map(c=>c.y))];
                assert.ok(cards.every(c=>c.start==='auto'),'no forced grid gaps');
                for(const y of rows.slice(0,-1))assert.equal(cards.filter(c=>c.y===y).length,columns,'every non-final row is filled');
                assert.ok(rows.every(y=>cards.find(c=>c.y===y).x===cards[0].x),'rows start at the first column');
            }
            await page.setViewportSize({width:1440,height:1080});
            await screenshot('admin-related-order-1440');
            await page.setViewportSize({width:390,height:844}); await screenshot('admin-related-order-390');
        });
        await runCase('draft-list return action stays within the shared toolbar at narrow widths', async () => {
            for(const skin of ['standard','edge'])for(const width of [320,390,768,1024]) {
                await page.setViewportSize({width,height:844});await load('index',skin);
                await page.locator('#btnOpenAddModal').evaluate(el=>el.classList.add('hidden'));
                await page.locator('#btnToggleDrafts').evaluate(el=>el.textContent='🔙 나의 장비 목록으로 돌아가기');
                await page.locator('#pageMainHeader').evaluate(el=>el.textContent='나의 임시저장 목록');
                const m=await measure();assert.ok(m.overflow<=1,'draft toolbar overflow '+skin+width);
                assertResponsiveShell(assert,m.shell,'draft '+skin+width);
                assertReadability(assert,await page.evaluate(readabilitySnapshot),'draft '+skin+width);
            }
        });
        await runCase('long nicknames preserve exactly three narrow right rows and full account metadata', async () => {
            for(const skin of ['standard','edge'])for(const width of [320,360,390,412,599])for(const role of ['user','admin']) {
                await page.setViewportSize({width,height:844});await load('index',skin);
                const before=await measure(),nickname=('아주 긴 닉네임 테스트 ').repeat(20);
                await page.locator('.app-nav-nickname').evaluate((el,text)=>el.textContent=text,nickname);
                await page.locator('.app-nav-role').evaluate((el,text)=>el.textContent='('+text+')',role);
                await page.locator('.app-nav-user').evaluate((el,label)=>{el.title=label;el.setAttribute('aria-label',label);},nickname+' ('+role+') · 마이페이지로 이동');
                const after=await measure();assertResponsiveShell(assert,after.shell,'long nickname '+skin+width+role);
                assert.equal(after.shell.right.height,before.shell.right.height,'long nickname cannot add a row');
                assert.ok(after.overflow<=1);
                assert.equal(await page.locator('.app-nav-nickname').evaluate(el=>el.scrollWidth>el.clientWidth),true);
                assert.equal(await page.locator('.app-nav-nickname').textContent(),nickname);
                assert.ok((await page.locator('.app-nav-user').getAttribute('aria-label')).includes(nickname));
                assert.equal(await page.locator('.app-nav-avatar').count(),0);
                if(width===320&&role==='admin')await screenshot('nickname-three-rows-'+skin+'-320');
            }
        });
        await runCase('right controls share card surfaces in light/dark and preserve role/logout/warning colors', async () => {
            await load('index');await page.setViewportSize({width:390,height:844});
            for(const dark of [false,true]) {
                await page.evaluate(dark=>document.documentElement.classList.toggle('dark',dark),dark);
                await page.locator('#session-timer-badge').evaluate(el=>el.dataset.sessionState='warning');
                const m=await measure();assertResponsiveShell(assert,m.shell,'right cards '+dark);
                assert.ok(m.shell.rightCards.every(c=>c.background===(dark?'rgb(30, 41, 59)':'rgb(255, 255, 255)')));
                const colors=await page.evaluate(()=>Object.fromEntries(['.app-nav-logout','.app-nav-role','#session-timer-badge'].map(s=>[s,getComputedStyle(document.querySelector(s)).color])));
                assert.equal(colors['.app-nav-logout'],dark?'rgb(248, 113, 113)':'rgb(220, 38, 38)');
                assert.equal(colors['.app-nav-role'],dark?'rgb(96, 165, 250)':'rgb(37, 99, 235)');
                assert.equal(colors['#session-timer-badge'],colors['.app-nav-logout']);
            }
        });
        await runCase('navigation keeps long identities and session warnings inside the viewport', async () => {
            await load('mypage');
            await page.locator('.app-nav-nickname').evaluate(el => el.textContent = '아주긴닉네임'.repeat(10));
            await page.locator('.app-nav-role').evaluate(el => el.textContent = '(SUPER_ADMIN)');
            await page.locator('#session-timer-badge').evaluate(el => el.innerHTML = '<span class="app-session-full"><strong>4:59</strong> 남음 · 연장</span><span class="app-session-short">4:59</span>');
            for (const width of widths) {
                await page.setViewportSize({width, height: 1080});
                const m = await measure();
                assert.ok(m.overflow <= 1, 'navigation @' + width);
                assert.ok(m.rightChildren.every(r => r.x >= m.controls.x - 1 && r.x + r.width <= m.controls.x + m.controls.width + 1), 'long identity/timer must not intrude outside right column @' + width);
                assert.ok(await page.locator('#session-timer-badge').evaluate(el => el.scrollWidth - el.clientWidth <= 1), 'structured countdown stays inside badge @' + width);
                assert.equal(await page.locator('.app-nav-controls a[href="/logout"]').evaluate(el => getComputedStyle(el).whiteSpace), 'nowrap');
            }
        });
        await runCase('sparse/empty tables keep horizontal headers; buttons preserve whole words', async () => {
            for (const name of Object.keys(rendered)) {
                for (const skin of ['standard', 'edge']) {
                    await load(name, skin);
                    for (const width of [320, 390, 768, 1920]) {
                        await page.setViewportSize({width, height: 1080});
                        assertReadability(assert, await page.evaluate(readabilitySnapshot), name + '/' + skin + '@' + width);
                    }
                    await page.evaluate(() => {
                        for (const table of document.querySelectorAll('table')) {
                            const body = table.tBodies[0];
                            if (body) body.innerHTML = '<tr>' + '<td>1</td>'.repeat(table.querySelectorAll('thead th').length) + '</tr>';
                        }
                    });
                    await page.setViewportSize({width: 320, height: 800});
                    const result = await page.evaluate(readabilitySnapshot);
                    assertReadability(assert, result, name + '/' + skin + '/short data');
                    if (['index', 'index_public', 'audit_logs', 'access_logs_error_ips', 'users_management', 'master_management', 'permissions', 'approvals'].includes(name)) {
                        assert.ok(result.scrollers.some(s => s.scrollWidth > s.width), name + ': short data still scrolls for headers');
                    }
                    if (skin === 'edge' && ['index', 'master_management'].includes(name)) await screenshot('readable-' + name + '-320');
                }
            }
        });
        await runCase('dialog actions keep full words and fit narrow panels (offline)', async () => {
            for (const [name, id] of [['index', 'equipmentModal'], ['index', 'roadmap-csv-dialog'], ['mypage', 'emailModal'], ['mypage', 'profileModal'], ['mypage', 'passwordModal'], ['mypage', 'withdrawModal'], ['my_approvals', 'my-approval-detail'], ['master_management', 'editModal'], ['master_management', 'mergeModal']]) {
                await load(name);
                const panel = page.locator('#' + id);
                await panel.evaluate(el => el.tagName === 'DIALOG' ? el.showModal() : el.classList.remove('hidden'));
                if (id === 'equipmentModal') await page.locator('#btnSaveDraft').evaluate(el => el.classList.remove('hidden'));
                for (const width of [320, 390, 768]) {
                    await page.setViewportSize({width, height: 800});
                    assertReadability(assert, await page.evaluate(readabilitySnapshot), name + '/' + id + '@' + width);
                    assert.ok(await panel.evaluate(el => [...el.querySelectorAll('button')].filter(b => b.getBoundingClientRect().width > 0).every(b => {
                        const r = b.getBoundingClientRect(); return r.x >= 0 && r.right <= innerWidth + 1;
                    })), 'modal action remains reachable: ' + id);
                }
            }
        });
        await runCase('balanced button fallback and dynamic CSV headers (offline)', async () => {
            await load('index');
            await page.setViewportSize({width: 320, height: 800});
            await page.evaluate(() => {
                const box = document.createElement('section'); box.id = 'readability-fixture';
                box.innerHTML = '<button style="font:16px/24px sans-serif;width:156px;padding:8px">데이터베이스 복원 시작</button>' +
                    '<div class="roadmap-scroll" style="width:180px"><table><thead><tr><th>장비명</th><th>옵션 ID</th><th>시리얼</th><th>공개</th></tr></thead><tbody><tr><td>1</td><td>1</td><td>1</td><td>1</td></tr></tbody></table></div>';
                document.querySelector('main').append(box);
            });
            const result = await page.evaluate(readabilitySnapshot);
            assertReadability(assert, result, 'balanced and dynamic fixture');
            const lines = await page.locator('#readability-fixture button').evaluate(el => {
                const range = document.createRange(); range.selectNodeContents(el);
                return [...range.getClientRects()].filter(r => r.width > 0).map(r => r.width);
            });
            assert.equal(lines.length, 2);
            assert.ok(Math.min(...lines) / Math.max(...lines) > .65, 'balanced whole-word lines');
            assert.ok(result.scrollers.at(-1).scrollWidth > result.scrollers.at(-1).width);
        });
        await runCase('long table rows scroll inside the table, without enlarging page', async () => {
            for (const name of ['index', 'audit_logs', 'access_logs', 'dashboard']) {
                await load(name);
                const body = page.locator('main .overflow-x-auto tbody').first();
                await body.evaluate(el => {
                    const count = el.closest('table').querySelectorAll('thead th').length || 8;
                    el.innerHTML = '<tr>' + '<td class="px-4 py-3 whitespace-nowrap">검증용 긴 모델명 ABC-1234567890</td>'.repeat(count) + '</tr>';
                });
                for (const width of [390, 1920]) {
                    await page.setViewportSize({width, height: 1080});
                    assert.ok((await measure()).overflow <= 1, name + '@' + width);
                }
                if (name === 'index') await screenshot('equipment-edge-1920');
                if (name === 'dashboard') await screenshot('dashboard-edge-1920');
            }
        });
        await runCase('reorganized controls preserve settings save, error recovery and profile/password bindings (mocked)', async () => {
            await load('mypage');
            await page.evaluate(() => {
                window.userSettings = {theme: 'light', layout_skin: 'edge', deadline_email_opt_in: false};
                window.getCSRFToken = () => 'offline-fixture';
                window.fixtureRequests = [];
                window.fetch = async (url, options) => {
                    window.fixtureRequests.push({url, ...options});
                    return {ok: !window.fixtureError, json: async () => window.fixtureError
                        ? {message: '검증용 저장 오류'} : {settings: {...window.userSettings, ...JSON.parse(options.body)}}};
                };
                window.saveUserSettings = settings => window.fixtureTheme = settings;
            });
            await page.addScriptTag({content: read('static/js/roadmap_preferences.js')});
            await page.evaluate(() => document.dispatchEvent(new Event('DOMContentLoaded')));
            const accountScript = [...rendered.mypage.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)]
                .map(match => match[1]).find(code => code.includes('function openProfileModal'));
            assert.ok(accountScript);
            await page.addScriptTag({content: accountScript});
            await page.locator('[name="theme_setting"][value="dark"]').check();
            assert.deepEqual(await page.evaluate(() => window.fixtureTheme), {theme: 'dark'});
            await page.locator('#roadmap-skin').selectOption('standard');
            await page.locator('#roadmap-opt-in').check();
            await page.locator('#roadmap-preferences-save').click();
            await page.waitForFunction(() => document.getElementById('roadmap-preferences-message').textContent === '설정을 저장했습니다.');
            const request = await page.evaluate(() => window.fixtureRequests[0]);
            assert.equal(request.url, '/api/user_settings');
            assert.equal(request.method, 'POST');
            assert.equal(request.headers['X-CSRFToken'], 'offline-fixture');
            assert.deepEqual(JSON.parse(request.body), {layout_skin: 'standard', deadline_email_opt_in: true});
            assert.equal(await page.evaluate(() => document.documentElement.dataset.layoutSkin), 'standard');
            await page.evaluate(() => window.fixtureError = true);
            await page.locator('#roadmap-preferences-save').click();
            await page.waitForFunction(() => document.getElementById('roadmap-preferences-message').textContent === '검증용 저장 오류');
            assert.equal(await page.locator('#roadmap-preferences-save').isEnabled(), true);
            await page.locator('[onclick="openProfileModal()"]').click();
            assert.equal(await page.locator('#editLoginId').inputValue(), 'edge_fixture');
            await page.evaluate(() => closeProfileModal());
            await page.locator('#openPasswordModal').click();
            await page.locator('#current_pw').fill('fixture-only');
            await page.locator('#new_pw').fill('one');
            await page.locator('#new_pw_confirm').fill('two');
            await page.locator('#passwordForm button[type="submit"]').click();
            assert.equal(await page.locator('#pwMessage').innerText(), '새 비밀번호가 일치하지 않습니다.');
            assert.equal(await page.evaluate(() => window.fixtureRequests.length), 2, 'mismatch sends no password request');
        });
        await runCase('adjacent navigation, explicit parent hierarchy and uniform safe three-line descriptions', async () => {
            await load('portal');
            assert.equal(await page.locator('#parent-menu-link').count(), 0, 'root parent link is not rendered');
            for (const [name, parent] of [['index', '/portal'],
                ['permissions', '/admin_center'], ['audit_logs', '/admin_center'],
                ['access_logs_error_ips', '/access_logs']]) {
                await load(name);
                assert.equal(await page.locator('#parent-menu-link').getAttribute('href'), parent);
            }
            for (const skin of ['standard', 'edge']) {
                await load('portal', skin);
                for (const width of [320, 390, 1920]) {
                    await page.setViewportSize({width, height: 1080});
                    const links = await page.locator('.app-nav-links > *').evaluateAll(elements => elements.map(el => {
                        const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, right: r.right};
                    }));
                    assert.equal(links.length, 2);
                    if (width >= 600) {
                        assert.equal(links[0].y, links[1].y);
                        assert.ok(links[1].x - links[0].right <= 5);
                    } else assert.ok(links[1].y > links[0].y);
                    assert.ok((await measure()).overflow <= 1);
                    assert.equal(await page.evaluate(() => {
                        const nav = document.querySelector('body > nav').getBoundingClientRect();
                        return [...document.querySelectorAll('.app-nav-title, .app-nav-links, .app-nav-controls')]
                            .every(el => el.getBoundingClientRect().bottom <= nav.bottom)
                            && document.querySelector('main').getBoundingClientRect().top >= nav.bottom;
                    }), true, 'wrapped controls must remain inside header and above main');
                }
                await page.setViewportSize({width: 1440, height: 1080});
                const descriptions = ['짧은 설명', '카드의 설명입니다. '.repeat(8),
                    '<img src=x onerror=alert(1)> "전체 설명" '.repeat(30)];
                await page.evaluate(descriptions => MenuCards.render(document.getElementById('menuContainer'), [
                    ...descriptions.map(Description => ({Url: '/my_equipment', MenuName: '동일 제목', Description})),
                    ...['javascript:alert(1)', '//outside.test', '/\\outside.test'].map(Url => ({Url, MenuName: '거부'}))
                ]), descriptions);
                assert.equal(await page.locator('.menu-card').count(), 3);
                assert.equal(await page.locator('.menu-card img').count(), 0);
                const measurements = await page.locator('.menu-card').evaluateAll(cards => cards.map(card => {
                    const desc = card.querySelector('.menu-card-description');
                    return {height: card.getBoundingClientRect().height, descriptionHeight: desc.getBoundingClientRect().height,
                        clamp: getComputedStyle(desc).webkitLineClamp, text: desc.textContent, title: card.title};
                }));
                for (const [index, m] of measurements.entries()) {
                    assert.equal(m.height, measurements[0].height);
                    assert.equal(m.descriptionHeight, 60);
                    assert.equal(m.clamp, '3');
                    assert.equal(m.text, descriptions[index]);
                    assert.equal(m.title, descriptions[index]);
                }
                await page.locator('.menu-card').last().hover();
                assert.equal(await page.locator('.menu-card').last().evaluate(el => el.getBoundingClientRect().height), measurements[0].height);
                await screenshot('three-line-cards-' + skin);
            }
        });
        await runCase('role-first editor preserves drafts and submits only the chosen role', async () => {
            await load('permissions');
            await page.addScriptTag({content:read('static/js/menu_cards.js')});
            await page.evaluate(()=>{
                const menus=[['root','상위 메뉴',null],['child','세부 메뉴 (설명)','root'],['other','독립 메뉴',null]];
                window.permissionCalls=[];
                window.permissionFixture=Array.from({length:12},(_,i)=>i===0?'admin':i===1?'user':'role-'+i).flatMap(Role=>menus.map(([MenuCode,MenuName,ParentMenuCode])=>({Role,MenuCode,MenuName,ParentMenuCode,IsAllowed:Role==='admin'?1:0})));
                window.confirm=()=>true;window.getCSRFToken=()=> 'fixture';
                window.fetch=async(url,options={})=>{
                    permissionCalls.push({url,...options});
                    if(options.method==='POST')return {ok:!window.permissionFail,json:async()=>({success:!window.permissionFail,error:'검증용 저장 오류'})};
                    return {ok:true,json:async()=>permissionFixture};
                };
            });
            await page.addScriptTag({content:read('static/js/permissions.js')});
            await page.waitForFunction(()=>document.querySelectorAll('.permission-role').length===12);
            assert.equal(await page.locator('#permission-detail').isVisible(),false);
            await page.locator('.permission-role[data-role="user"]').click();
            assert.equal(await page.locator('#permTableBody tr').count(),3);
            assert.equal(await page.locator('#permTableBody').innerText().then(s=>s.includes('(설명)')),false);
            await page.locator('tr[data-menu="child"] input').check();
            assert.equal(await page.locator('tr[data-menu="root"] input').isChecked(),true);
            assert.equal(await page.locator('tr[data-menu="root"] input').isDisabled(),true);
            await page.locator('.permission-role[data-role="role-2"]').click();
            await page.locator('tr[data-menu="other"] input').check();
            await page.locator('.permission-role[data-role="user"]').click();
            assert.equal(await page.locator('tr[data-menu="child"] input').isChecked(),true);
            await page.locator('#permission-save').click();
            const post=await page.evaluate(()=>permissionCalls.find(c=>c.method==='POST'));
            assert.ok(JSON.parse(post.body).every(row=>row.Role==='user'));
            assert.equal(post.headers['X-CSRFToken'],'fixture');
            assert.equal(await page.locator('#permission-save').isDisabled(),true);
            await page.locator('.permission-role[data-role="role-2"]').click();
            assert.equal(await page.locator('tr[data-menu="other"] input').isChecked(),true);
            await page.evaluate(()=>window.permissionFail=true);
            await page.locator('#permission-save').click();
            assert.equal(await page.locator('#permission-message').innerText(),'검증용 저장 오류');
            assert.equal(await page.locator('#permission-save').isEnabled(),true);
            for(const skin of ['standard','edge'])for(const width of [320,390,768,1024,1920]){
                await page.evaluate(skin=>document.documentElement.dataset.layoutSkin=skin,skin);
                await page.setViewportSize({width,height:844});const m=await measure();assert.ok(m.overflow<=1);
                const boxes=await page.locator('.permission-role-panel,.permission-detail-panel').evaluateAll(items=>items.map(el=>{const r=el.getBoundingClientRect();return{x:r.x,y:r.y,right:r.right,bottom:r.bottom};}));
                if(width>=1024)assert.ok(boxes[0].right<=boxes[1].x);else assert.ok(boxes[0].bottom<=boxes[1].y);
                assertReadability(assert,await page.evaluate(readabilitySnapshot),'permissions '+skin+width);
                if(skin==='edge'&&[390,1920].includes(width))await screenshot('role-first-'+width);
            }
            await page.locator('#permission-role-search').fill('role-11');assert.equal(await page.locator('.permission-role').count(),1);
            await page.locator('#permission-menu-search').fill('독립');assert.equal(await page.locator('#permTableBody tr').count(),1);
            // Clear only fixture dirty state through a successful mock save before navigating.
            await page.evaluate(()=>window.permissionFail=false);await page.locator('#permission-save').click();
        });
        await runCase('lineup drilldown shows direct children, preserves options and bounds cycles', async () => {
            await load('lineup_management');
            await page.evaluate(()=>{
                window.nodeCalls=[];window.getCSRFToken=()=> 'fixture';
                const base={category_id:1,manufacturer_id:1,status:'APPROVED',depth:1,child_count:0,option_count:0};
                window.nodeFixture={success:true,categories:[{id:1,name:'분류',is_approved:1},{id:2,name:'다른 분류',is_approved:1}],manufacturers:[{id:1,name:'제조사',is_approved:1}],
                    nodes:[{...base,id:1,parent_id:null,name:'첫 루트',child_count:2,option_count:1},{...base,id:2,parent_id:1,name:'선택할 자식',depth:2,child_count:1},
                        {...base,id:3,parent_id:1,name:'형제 노드',depth:2},{...base,id:4,parent_id:2,name:'손자 노드',depth:3},
                        {...base,id:5,parent_id:null,name:'다른 루트'},{...base,id:8,parent_id:9,name:'순환 A'},{...base,id:9,parent_id:8,name:'순환 B'}],
                    options:[{id:11,lineup_node_id:1,option_name:'사용 중 옵션',status:'APPROVED',active_equipment_count:1,draft_equipment_count:0,specs_json:'{}'}]};
                window.fetch=async(url,options={})=>{nodeCalls.push({url,...options});return {ok:true,json:async()=>nodeFixture};};
            });
            const script=[...rendered.lineup_management.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(s=>s.includes('initializeLineupManagement'));
            await page.addScriptTag({content:script});
            await page.waitForFunction(()=>document.querySelector('[data-node-id="1"]'));
            assert.equal(await page.locator('[data-node-id]').count(),2);
            assert.equal(await page.locator('[data-selected-node]').count(),0);
            await page.locator('[data-node-id="1"]').click();
            assert.deepEqual(await page.locator('[data-node-id]').evaluateAll(items=>items.map(el=>el.dataset.nodeId)),['2','3']);
            assert.equal(await page.locator('[data-selected-node="1"]').count(),1);
            await page.locator('.node-detail-panel summary').click();
            assert.ok((await page.locator('.node-detail-panel').innerText()).includes('사용 중 옵션'));
            for(const skin of ['standard','edge'])for(const width of [320,390,768,1024,1920]){
                await page.evaluate(skin=>document.documentElement.dataset.layoutSkin=skin,skin);await page.setViewportSize({width,height:844});
                assert.ok((await measure()).overflow<=1);assertReadability(assert,await page.evaluate(readabilitySnapshot),'nodes '+skin+width);
                if(skin==='edge'&&[390,1920].includes(width))await screenshot('lineup-drilldown-'+width);
            }
            await page.locator('#unusedOptionsOnly').check();assert.ok(!(await page.locator('.node-detail-panel').innerText()).includes('사용 중 옵션'));
            await page.locator('#unusedOptionsOnly').uncheck();
            await page.locator('[data-node-id="2"]').click();assert.equal(await page.locator('[data-node-id="4"]').count(),1);assert.equal(await page.locator('[data-node-id="3"]').count(),0);
            await page.locator('[data-path-node="1"]').click();assert.equal(await page.locator('[data-node-id="3"]').count(),1);
            await page.locator('.node-breadcrumb button').first().click();
            await page.locator('[data-orphan-node="8"]').click();await page.locator('[data-node-id="9"]').click();
            assert.equal(await page.locator('[data-node-id="8"]').isDisabled(),true);
            await page.locator('#categoryFilter').selectOption('2');assert.equal(await page.locator('[data-selected-node]').count(),0);
            assert.ok((await page.locator('#treeContainer').innerText()).includes('등록된 노드가 없습니다.'));
            assert.ok((await page.evaluate(()=>nodeCalls)).every(call=>!call.method));
        });
        await runCase('account safety forms are closed modals with focus return and retained confirmation', async () => {
            await load('mypage');
            await page.evaluate(()=>{window.accountCalls=[];window.getCSRFToken=()=> 'fixture';window.showGlobalLoading=()=>{};window.hideGlobalLoading=()=>{};
                window.confirm=()=>false;window.fetch=async(url,options)=>{accountCalls.push({url,...options});return {ok:false,json:async()=>({error:'인증 실패',message:'인증 실패'})};};});
            const script=[...rendered.mypage.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(s=>s.includes('function openProfileModal'));
            await page.addScriptTag({content:'(()=>{'+script+';Object.assign(window,{openProfileModal,closeProfileModal,openAccountDialog,closeAccountDialog,applyThemeSetting,sendPin,verifyPin});})();'});
            assert.equal(await page.locator('.account-panel').count(),2);
            for(const [opener,id,input] of [['openPasswordModal','passwordModal','current_pw'],['openWithdrawModal','withdrawModal','withdraw_pw']]){
                assert.equal(await page.locator('#'+id).isVisible(),false);
                assert.equal(await page.locator('#account-profile #'+opener).count(),1);
                await page.locator('#'+opener).click();assert.equal(await page.locator('#'+input).evaluate(el=>el===document.activeElement),true);
                await page.locator('#'+input).fill('fixture-only-password');
                await page.keyboard.press('Escape');assert.equal(await page.locator('#'+id).isVisible(),false);
                await page.waitForFunction(input=>document.getElementById(input).value==='',input);
                assert.equal(await page.locator('#'+input).inputValue(),'');assert.equal(await page.locator('#'+opener).evaluate(el=>el===document.activeElement),true);
            }
            await page.locator('#openWithdrawModal').click();await page.locator('#withdraw_pw').fill('fixture-only-password');
            await page.locator('#withdrawForm button[type="submit"]').click();assert.deepEqual(await page.evaluate(()=>accountCalls),[]);
            await page.evaluate(()=>window.confirm=()=>true);await page.locator('#withdrawForm button[type="submit"]').click();
            assert.equal(await page.locator('#withdrawMessage').innerText(),'인증 실패');
            assert.equal((await page.evaluate(()=>accountCalls))[0].url,'/api/users/withdraw');
            await page.keyboard.press('Escape');await page.locator('#openPasswordModal').click();
            await page.locator('#current_pw').fill('fixture-only-password');await page.locator('#new_pw').fill('fixture-new-password');await page.locator('#new_pw_confirm').fill('fixture-new-password');
            await page.locator('#passwordForm button[type="submit"]').click();assert.equal(await page.locator('#pwMessage').innerText(),'인증 실패');
            const password=await page.evaluate(()=>accountCalls.at(-1));assert.equal(password.url,'/api/change_password');assert.equal(password.headers['X-CSRFToken'],'fixture');
            await page.keyboard.press('Escape');
        });
        await runCase('personal approval history filters pages and safely displays completed details', async () => {
            await load('my_approvals');
            await page.evaluate(()=>{window.approvalCalls=[];window.fetch=async(url,options={})=>{
                approvalCalls.push({url,...options});const q=new URL(url,'https://fixture.test').searchParams, page=Number(q.get('page'));
                return {ok:true,json:async()=>({success:true,total:q.get('status')?1:26,page,pages:q.get('status')?1:2,per_page:25,
                    data:[{RequestId:page,RequestType:'ADD_CATEGORY',RequestDataJSON:JSON.stringify({name:'<img src=x onerror=alert(1)> 검증'}),Status:q.get('status')||'PENDING',RejectReason:q.get('status')==='REJECTED'?'<script>검증</script> 반려 사유':null,CreatedAt:'2026-09-14',UpdatedAt:'2026-09-15'}]})};};});
            await page.addScriptTag({content:read('static/js/my_approvals.js')});await page.waitForFunction(()=>document.getElementById('my-approvals-page').textContent.includes('26건'));
            assert.equal(await page.locator('#my-approvals-body img').count(),0);
            await page.locator('#my-approvals-next').click();assert.ok((await page.locator('#my-approvals-page').innerText()).includes('2/2'));
            await page.locator('#my-approvals-status').selectOption('REJECTED');await page.locator('#my-approvals-filter button').click();
            assert.ok((await page.locator('#my-approvals-body').innerText()).includes('반려 사유'));
            await page.locator('#my-approvals-body button').click();assert.equal(await page.locator('#my-approval-detail').isVisible(),true);
            assert.ok((await page.locator('#my-approval-detail-summary').innerText()).includes('2026-09-15'));
            assert.equal(await page.locator('#my-approval-detail script').count(),0);
            await page.keyboard.press('Escape');
            for(const width of [320,390,1024,1920]){await page.setViewportSize({width,height:844});assert.ok((await measure()).overflow<=1);assertReadability(assert,await page.evaluate(readabilitySnapshot),'own approvals '+width);}
            assert.ok((await page.evaluate(()=>approvalCalls)).every(call=>!call.method));
        });
        await runCase('simple/advanced search preserves values but excludes hidden filters; URL and reset contracts', async () => {
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            await page.route('https://ux.fixture.test/**', route => route.fulfill({contentType: 'text/html', body: '<html><body></body></html>'}));
            async function searchFixture(query = '') {
                await page.goto('https://ux.fixture.test/my_equipment' + query);
                await load('index');
                await page.evaluate(() => {
                    window.getCSRFToken = () => 'fixture';
                    window.getEquipmentListScope = () => new URLSearchParams({scope: 'my'});
                    window.fixtureSearches = [];
                    window.fetchEquipment = () => {
                        const values = Object.fromEntries(Roadmap.parameters());
                        fixtureSearches.push(values);
                        Roadmap.received({total: 50, page: Number(values.page), pages: 2});
                    };
                    window.fetch = async () => ({ok: true, json: async () => ({
                        categories: [{CategoryId: 7, Name: '분류'}], manufacturers: [{ManufacturerId: 9, Name: '제조사'}]
                    })});
                });
                await page.addScriptTag({content: read('static/js/roadmap_equipment.js')});
                await page.evaluate(async () => { await Roadmap.init(); fetchEquipment(); });
            }
            await searchFixture();
            await page.setViewportSize({width: 320, height: 568});
            assert.equal(await page.locator('.roadmap-search-basic').evaluate(el => {
                const buttons = [...el.querySelectorAll('button')].map(b => b.getBoundingClientRect());
                return buttons[0].y === buttons[1].y;
            }), true, 'search and mode switch stay adjacent on portrait phones');
            assert.equal(await page.locator('#roadmap-advanced').isVisible(), false);
            assert.equal(await page.locator('#roadmap-search-toggle').textContent(), '조건검색');
            assert.deepEqual(await page.evaluate(() => Object.fromEntries(Roadmap.parameters())), {scope: 'my', page: '1', paginated: '1'});
            await page.locator('#roadmap-keyword').fill('완성 모델');
            await page.locator('#roadmap-keyword').press('Enter');
            assert.equal(new URL(page.url()).searchParams.get('keyword'), '완성 모델');
            const queriesBeforeCSV = await page.evaluate(() => fixtureSearches.length);
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
            await page.locator('#roadmap-csv-toggle').press('Enter');
            assert.equal(await page.locator('#roadmap-csv-actions').isVisible(), false);
            assert.equal(await page.evaluate(() => fixtureSearches.length), queriesBeforeCSV, 'CSV disclosure does not search');
            assert.equal(await page.locator('#roadmap-keyword').inputValue(), '완성 모델');
            await page.locator('#roadmap-search-toggle').click();
            assert.equal(await page.locator('#roadmap-search-toggle').getAttribute('aria-expanded'), 'true');
            await page.locator('[name="category_id"]').selectOption('7');
            await page.locator('[name="manufacturer_id"]').selectOption('9');
            await page.locator('#roadmap-filter button[type="submit"]').click();
            await page.locator('#roadmap-next').click();
            assert.equal(new URL(page.url()).searchParams.get('page'), '2');
            await page.locator('#roadmap-search-toggle').click();
            assert.deepEqual(await page.evaluate(() => Object.fromEntries(Roadmap.parameters())), {scope: 'my', keyword: '완성 모델', page: '1', paginated: '1'});
            assert.equal(new URL(page.url()).searchParams.has('category_id'), false);
            assert.equal(await page.locator('[name="category_id"]').inputValue(), '7');
            assert.equal(await page.locator('[name="category_id"]').isDisabled(), true);
            await page.locator('#roadmap-search-toggle').click();
            assert.equal(new URL(page.url()).searchParams.get('category_id'), '7');
            assert.equal(new URL(page.url()).searchParams.get('manufacturer_id'), '9');
            await page.setViewportSize({width: 1440, height: 1080});
            await page.evaluate(() => scrollTo(0, 0));
            await measure();
            await screenshot('equipment-advanced-1440');
            await page.locator('#roadmap-filter button[type="reset"]').click();
            await page.waitForFunction(() => !new URL(location.href).searchParams.has('keyword'));
            assert.equal(await page.locator('[name="category_id"]').inputValue(), '');
            await page.locator('#roadmap-search-toggle').click();
            await page.evaluate(() => scrollTo(0, 0));
            await screenshot('equipment-simple-1440');
            await searchFixture('?keyword=test&category_id=7&manufacturer_id=9&page=2');
            assert.equal(await page.locator('#roadmap-advanced').isVisible(), true);
            assert.equal(await page.locator('[name="category_id"]').inputValue(), '7');
            assert.equal(await page.evaluate(() => Roadmap.parameters().get('page')), '2');
            await searchFixture('?sort=newest&per_page=25');
            assert.equal(await page.locator('#roadmap-advanced').isVisible(), false);
            await searchFixture('?search_mode=advanced');
            assert.equal(await page.locator('#roadmap-advanced').isVisible(), true);
            assert.deepEqual(errors, []);
        });
    } finally {
        await context.close();
        await browser.close();
    }
});
