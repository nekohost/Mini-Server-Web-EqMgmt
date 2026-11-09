/* [Role] Exercises the responsive toolbars through the actual menu controls.
 * [Dependencies] The menu fixture supplies isolated GET transport and a same-origin resizable frame.
 * [Impact] Records visible geometry and read-only interactions without submitting administrative actions. */
async function checkMenuToolbars({view, ok, wait, frame, geometry, reads}) {
    const main = document.querySelector('main');
    const byId = id => document.getElementById(id);
    const box = element => element.getBoundingClientRect();
    const isVisible = element => box(element).width > 0 && box(element).height > 0;
    const isInsidePage = element => box(element).left >= -1 && box(element).right <= innerWidth + 1;
    const sizes = '.app-toolbar-control, .app-toolbar-buttons > button, .app-toolbar-pages > button, .app-toolbar .catalog-request-toolbar button';
    const controls = [...main.querySelectorAll(sizes)].filter(isVisible);
    const expectSizes = !['portal', 'admin_center', 'public'].includes(view);
    if (expectSizes) ok(controls.length > 0, 'visible scoped controls exist');
    geometry.controlCount = controls.length;
    geometry.smallHeights = controls.filter(el => box(el).height < 43.9).map(el => el.id || el.textContent.trim());
    geometry.wrongFonts = controls.filter(el => getComputedStyle(el).fontSize !== '13px').map(el => el.id || el.textContent.trim());
    ok(!geometry.smallHeights.length && !geometry.wrongFonts.length, '44px minimum height and 13px type on visible controls');
    const separatePages = {my_approvals: 'my-approvals-body', audit_logs: 'auditLogTbody', access_logs: 'logsTableBody'};
    if (view in separatePages) {
        const pages = main.querySelector('.app-toolbar-pages');
        const back = main.querySelector('.app-pagination-return');
        ok(isVisible(back) && back.hash === '#' + pages.id, 'long result list links to the live pager');
        back.scrollIntoView({block: 'center'});
        back.click();
        await frame();
        ok(document.activeElement === pages && box(pages).top >= box(document.querySelector('.app-nav-polish')).bottom - 1,
           'return link focuses the pager below the sticky header');
        ok(Boolean(pages.compareDocumentPosition(byId(separatePages[view])) & Node.DOCUMENT_POSITION_FOLLOWING),
           'pagination precedes its own result table');
        const next = view === 'my_approvals' ? byId('my-approvals-next') : pages.lastElementChild;
        next.click();
        await wait(() => reads.some(path => /[?&]page=2(?:&|$)/.test(path)), 'next page GET');
        await frame();
        ok(!pages.querySelector('button').disabled, 'previous page becomes available');
    }
    if (view === 'audit_logs') {
        const exact = main.querySelector('input[value="exact"]');
        exact.focus();
        ok(document.activeElement === exact, 'match controls accept keyboard focus');
        exact.click();
        await wait(() => reads.some(path => path.includes('exact')), 'exact search GET');
        const control = main.querySelector('button[onclick="toggleColumnMenu()"]');
        control.click();
        ok(isVisible(byId('columnMenu')) && isInsidePage(byId('columnMenu')), 'column menu fits when opened');
        control.click();
        byId('pageSizeSelect').value = 'custom';
        byId('pageSizeSelect').dispatchEvent(new Event('change'));
        ok(isVisible(byId('customPageSizeInput')) && isInsidePage(byId('customPageSizeInput')), 'custom page size fits and opens');
        byId('customPageSizeContainer').classList.add('hidden');
        byId('pageSizeSelect').value = '200';
        byId('keyword').focus();
        await frame();
    }
    if (view === 'access_logs') {
        const trigger = main.querySelector('button[onclick="toggleCleanupMenu()"]');
        trigger.click();
        ok(isVisible(byId('cleanupDropdown')) && isInsidePage(byId('cleanupDropdown')), 'opened cleanup menu fits viewport');
        trigger.click();
    }
    if (view === 'portal') {
        await wait(() => byId('menuContainer').querySelectorAll('a').length === 2, 'portal cards');
        ok(byId('menuContainer').lastElementChild.getAttribute('href') === '/admin_center', 'admin card is last');
    }
    if (view === 'backup_active') {
        ok(byId('backup-download').parentElement === byId('full-backup-download').parentElement, 'backup alternatives share their own group');
        ok(!main.querySelector('#restore-form').contains(byId('candidate-submit')) && !isVisible(byId('restore-submit')), 'verification and protected restore remain separate');
    }
    if (view === 'users_management') {
        const group = main.querySelector('.app-toolbar-buttons');
        const extra = document.createElement('button');
        extra.type = 'button';
        extra.textContent = '추가된 목록 작업';
        group.append(extra);
        await frame();
        ok(box(extra).height >= 43.9 && isInsidePage(extra) && document.documentElement.scrollWidth <= innerWidth + 1,
           'additional actions inherit the control size and wrap without new layout rules');
        extra.remove();
    }
    if (view === 'my_approvals' && innerWidth === 1440) {
        const root = document.documentElement;
        const previous = root.style.fontSize;
        root.style.fontSize = '125%';
        await frame();
        ok(box(byId('my-approvals-status')).height >= 54.9 && root.scrollWidth <= innerWidth + 1,
           '125% root text scales the controls and preserves page fit');
        root.style.fontSize = previous;
        await frame();
    }
    const rowSelectors = {
        my_approvals: '[data-catalog-kind], #my-approvals-status, #my-approvals-filter button, #my-approvals-prev, #my-approvals-page, #my-approvals-next',
        lineup_management: '#categoryFilter, #manufacturerFilter, #addRootButton',
        users_management: '.app-toolbar button', master_management: '.app-toolbar button',
        dashboard: '#combinedSearchForm select, #combinedSearchForm button',
        access_logs: '.app-toolbar-results button, #perPageSelect, #paginationNav [aria-current]',
        audit_logs: '.app-toolbar-results > .app-toolbar-group > .relative > button, #pageSizeSelect, #paginationNav button'
    };
    if (rowSelectors[view]) {
        const elements = [...main.querySelectorAll(rowSelectors[view])].filter(isVisible);
        const widths = innerWidth === 1440 ? [1440, 1024, 820, 640, 412, 384, 320, 1440] : [innerWidth];
        const target = view === 'my_approvals' ? byId('my-approvals-status') : main.querySelector('.app-toolbar select');
        const originalValue = target?.value;
        const initialFocus = document.activeElement;
        const readsBeforeResize = reads.length;
        geometry.rows = [];
        for (const width of widths) {
            if (width !== innerWidth) {
                frameElement.style.width = width + 'px';
                await wait(() => innerWidth === width, 'viewport resize');
            }
            await frame();
            const rects = elements.map(box);
            const rows = [...new Set(rects.map(r => Math.round(r.bottom)))].length;
            geometry.rows.push({width, rows});
            ok(!rects.some(r => r.left < -1 || r.right > width + 1) && document.documentElement.scrollWidth <= width + 1,
               'toolbar and document fit at ' + width);
            if (width === 1440) ok(rows === 1, 'related controls share one desktop row');
        }
        ok(target?.value === originalValue && document.activeElement === initialFocus && reads.length === readsBeforeResize,
           'resizing preserves focus and selection without loading data');
    }
}
