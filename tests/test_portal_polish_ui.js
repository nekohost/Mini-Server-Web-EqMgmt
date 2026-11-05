/* [MINI-COMMENT: PORTAL.POLISH.UI.REGRESSION]
 * [EN rev.1]
 * [Role] Drives the actual portal API loaders and records stable ordering, full-frame geometry and natural focus semantics.
 * [Dependencies] Candidate portal/frame/MenuCards, synthetic GET responses and real Chromium animation frames.
 * [Impact] Reloaded permission-filtered menus keep their relative order and never acquire an unauthorized admin card; no navigation, production account, database or model service is used.
 */
(function () {
    'use strict';
    const theme = new URLSearchParams(location.search).get('theme') || 'light';
    localStorage.theme = theme; document.documentElement.classList.toggle('dark', theme === 'dark');
    const originalFetch = window.fetch.bind(window), requests = [], clone = value => JSON.parse(JSON.stringify(value));
    const records = {
        admin_center: { MenuCode: 'admin_center', MenuName: '관리자 센터', Url: '/admin_center', Description: '사용자와 권한, 운영 상태를 확인합니다.' },
        my_equipment: { MenuCode: 'my_equipment', MenuName: '내 장비', Url: '/my_equipment', Description: '내가 보유한 장비와 자산을 관리합니다.' },
        public_equipment: { MenuCode: 'public_equipment', MenuName: '공개 장비', Url: '/public_equipment', Description: '공개된 장비 정보를 확인합니다.' },
        my_approvals: { MenuCode: 'my_approvals', MenuName: '내 결재함', Url: '/my_approvals', Description: '내 신청과 처리 결과를 확인합니다.' },
        equipment_ai: { MenuCode: 'equipment_ai', MenuName: 'AI 도우미', Url: '/assistant', Description: '대화로 장비 조회와 업무를 요청합니다.' },
        future_reports: { MenuCode: 'future_reports', MenuName: '추가된 자료 메뉴', Url: '/fixture/future_reports', Description: '새 메뉴의 API 상대 순서를 보존합니다. <img src=x onerror="window.__portalPwned=1"> ' + '긴설명'.repeat(30) }
    };
    const initial = ['admin_center', 'my_equipment', 'public_equipment', 'my_approvals', 'equipment_ai', 'future_reports'];
    let responseCodes = initial.slice(), payloads = [];

    /** [Role] Serves only synthetic portal/dashboard data while retaining the shared frame's isolated session/preferences routes. */
    window.fetch = async (path, options = {}) => {
        const url = new URL(path, location.origin), method = options.method || 'GET';
        requests.push({ path: url.pathname, method });
        if (url.pathname === '/api/portal/menus') {
            const payload = responseCodes.map(code => clone(records[code]));
            payloads.push(JSON.stringify(payload));
            return new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
        if (url.pathname === '/api/dashboard/stats') return new Response(JSON.stringify({ success: true, data: { my_equipments: 12, total_equipments: 34 } }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        if (url.pathname.startsWith('/api/ai/')) return new Response(JSON.stringify({ success: false, message: '포털에서는 AI API를 호출하지 않습니다.' }), { status: 422, headers: { 'Content-Type': 'application/json' } });
        return originalFetch(path, options);
    };

    document.addEventListener('DOMContentLoaded', async () => {
        const checks = [], stages = {}, report = document.createElement('pre'); report.id = 'browser-test-result'; report.hidden = true; document.body.append(report);
        const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
        const wait = async (test, name = 'condition') => { for (let count = 0; count < 1000; count++) { if (test()) return; await sleep(10); } throw new Error(name + ' timed out'); };
        const assert = (value, name) => { if (!value) throw new Error(name); checks.push(name); };
        const cards = () => [...document.querySelectorAll('#menuContainer > a.menu-card')];
        const code = card => Object.values(records).find(menu => new URL(menu.Url, location.origin).pathname === new URL(card.href).pathname)?.MenuCode;
        const rendered = () => cards().map(code);
        const expected = codes => codes.filter(value => value !== 'admin_center').concat(codes.filter(value => value === 'admin_center'));
        const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);
        const rectangle = element => { const rect = element.getBoundingClientRect(); return Object.fromEntries(['top', 'left', 'right', 'bottom', 'width', 'height'].map(key => [key, Math.round(rect[key] * 100) / 100])); };
        const publish = result => { report.textContent = JSON.stringify(result); if (parent !== window) parent.postMessage({ fixtureResult: report.textContent }, location.origin); };

        /** [Role] Measures real visual, DOM and default tab order after an API-driven portal render. */
        function inspect(name, codes) {
            const items = cards(), wanted = expected(codes), actual = rendered();
            assert(same(actual, wanted), name + '-admin-last-and-other-api-relative-order');
            assert(items.length === codes.length && new Set(actual).size === codes.length, name + '-all-and-only-permitted-api-menus');
            const admin = items.find(item => code(item) === 'admin_center');
            assert(!admin || items.at(-1) === admin, name + '-admin-is-last-dom-card');
            assert(items.every(item => item.tabIndex === 0 && !item.hasAttribute('tabindex')) && !document.querySelector('#menuContainer [tabindex]:not([tabindex="0"])'), name + '-default-tab-order-follows-dom-without-positive-tabindex');
            assert(items.every(item => getComputedStyle(item).order === '0') && !getComputedStyle(document.getElementById('menuContainer')).gridAutoFlow.includes('dense'), name + '-css-does-not-reorder-focus-or-reading-sequence');
            const focused = [];
            for (const item of items) { item.focus({ preventScroll: true }); assert(document.activeElement === item, name + '-card-focusable-' + code(item)); focused.push(code(document.activeElement)); }
            assert(same(focused, wanted), name + '-focusable-sequence-keeps-admin-last');
            const visual = [...items].sort((left, right) => {
                const a = left.getBoundingClientRect(), b = right.getBoundingClientRect();
                return Math.abs(a.top - b.top) > 1 ? a.top - b.top : a.left - b.left;
            }).map(code);
            assert(same(visual, wanted), name + '-visual-grid-reading-order-matches-dom');
            const container = document.getElementById('menuContainer'), bounds = container.getBoundingClientRect();
            assert(container.scrollWidth <= container.clientWidth + 1 && items.every(item => { const box = item.getBoundingClientRect(); return box.left >= bounds.left - 1 && box.right <= bounds.right + 1; }), name + '-cards-fit-container-without-horizontal-overflow');
            stages[name] = { api_order: codes.slice(), dom_order: actual, focus_order: focused, visual_order: visual, container: rectangle(container), cards: items.map(item => ({ code: code(item), href: new URL(item.href).pathname, tab_index: item.tabIndex, box: rectangle(item) })) };
        }

        try {
            await wait(() => cards().length === initial.length && !document.getElementById('dashboardWidget').classList.contains('hidden'), 'actual portal menus and dashboard');
            await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            assert(document.title.includes('메인 포털') && document.querySelector('.app-content-title')?.textContent.trim() === '메인 포털', 'actual-portal-document-and-content-heading');
            assert(document.querySelector('nav[aria-label="전역 네비게이션"]') && document.querySelector('.app-nav-role')?.textContent.trim() === '(admin)', 'actual-frame-renders-synthetic-admin-account');
            assert(!document.getElementById('parent-menu-link'), 'portal-root-has-no-parent-menu-link');
            assert(document.getElementById('dashboardWidget').textContent.includes('12대') && document.getElementById('dashboardWidget').textContent.includes('34대'), 'actual-dashboard-loader-uses-synthetic-numeric-stats');
            assert(document.documentElement.classList.contains('dark') === (theme === 'dark'), 'requested-theme-applies-to-real-frame');
            inspect('initial', initial);

            responseCodes = ['future_reports', 'public_equipment', 'admin_center', 'equipment_ai', 'my_equipment', 'my_approvals'];
            const readsBefore = requests.filter(item => item.path === '/api/portal/menus').length;
            await window.loadPortalMenus();
            assert(requests.filter(item => item.path === '/api/portal/menus').length === readsBefore + 1, 'reload-calls-actual-portal-menu-api-loader');
            inspect('reloaded', responseCodes);
            assert(same(JSON.parse(payloads.at(-1)).map(menu => menu.MenuCode), responseCodes), 'presentation-order-does-not-rewrite-api-payload');

            responseCodes = ['equipment_ai', 'future_reports', 'my_equipment'];
            await window.loadPortalMenus(); inspect('permission_reduced', responseCodes);
            assert(!rendered().includes('admin_center') && !document.querySelector('#menuContainer a[href="/admin_center"]'), 'permission-filtered-api-without-admin-never-gains-admin-card');

            responseCodes = initial.slice(); await window.loadPortalMenus(); inspect('restored', initial);
            const future = cards().find(item => code(item) === 'future_reports');
            assert(future.querySelector('.menu-card-description').title === records.future_reports.Description && !future.querySelector('img') && !window.__portalPwned, 'menu-description-remains-inert-text-with-full-tooltip');
            assert(requests.filter(item => item.path === '/api/portal/menus').length === 4 && requests.every(item => item.method === 'GET'), 'initial-plus-three-api-reloads-use-read-only-requests');
            assert(!requests.some(item => item.path.startsWith('/api/ai/')) && !document.getElementById('equipment-ai'), 'portal-alias-does-not-initialize-assistant-or-call-ai-services');
            const columns = getComputedStyle(document.getElementById('menuContainer')).gridTemplateColumns.split(/\s+/).filter(Boolean).length;
            assert(columns === (innerWidth < 640 ? 1 : 4), 'actual-portal-grid-has-responsive-column-count');
            assert(document.documentElement.scrollWidth <= innerWidth + 1 && document.body.scrollWidth <= innerWidth + 1, 'full-portal-frame-has-no-horizontal-page-overflow');

            // The child viewport expands to the actual document height so the mobile screenshot includes the final admin card.
            const measuredHeight = Math.ceil(document.documentElement.scrollHeight + 2);
            if (window.frameElement) window.frameElement.style.height = Math.max(1000, measuredHeight) + 'px';
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            window.scrollTo(0, 0); document.activeElement?.blur();
            assert(cards().at(-1).getBoundingClientRect().bottom <= innerHeight + 1 && document.documentElement.scrollHeight <= innerHeight + 1, 'full-document-capture-includes-final-admin-card');
            assert(innerHeight <= (innerWidth === 390 ? 1850 : 1050), 'complete-portal-fits-real-capture-window');
            publish({ status: 'pass', width: innerWidth, height: innerHeight, theme, checks, stages, menu_api_reads: payloads.length, tab_order_method: 'DOM order, default tabIndex and sequential programmatic focus; no synthesized native Tab claim' });
        } catch (error) { publish({ status: 'fail', width: innerWidth, height: innerHeight, theme, checks, stages, error: String(error.stack || error) }); }
    });
})();
