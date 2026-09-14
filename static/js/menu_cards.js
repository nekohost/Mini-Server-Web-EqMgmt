/* Shared portal/admin card renderer: text stays text, including the full hover title. */
(function (global) {
    'use strict';
    // Presentation-only order. Unknown future menus retain their API order after these groups.
    const adminOrder = ['users_management', 'permissions', 'master_management', 'lineup_management', 'approvals',
        'audit_logs', 'access_logs', 'maintenance_admin', 'backup_restore'];
    function orderAdmin(menus) {
        const rank = menu => { const index = adminOrder.indexOf(menu.MenuCode); return index < 0 ? adminOrder.length : index; };
        return menus.map((menu, index) => ({menu, index})).sort((a, b) => rank(a.menu) - rank(b.menu) || a.index - b.index).map(item => item.menu);
    }
    function menuLabel(value) {
        // Display-only menu annotations; never rewrite stored names or user/catalog data.
        let text = String(value ?? '');
        while (/\([^()]*\)/u.test(text)) text = text.replace(/\([^()]*\)/gu, '');
        return text.replace(/^[\s\p{Extended_Pictographic}\uFE0F\u200D]+/u, '').replace(/\s+/gu, ' ').trim();
    }
    function render(container, menus) {
        const fragment = document.createDocumentFragment();
        for (const menu of menus) {
            // Menu records use root-relative application paths, never executable/external URLs.
            if (typeof menu.Url !== 'string' || !/^\/(?![\/\\])/.test(menu.Url) || /[\\\x00-\x20]/.test(menu.Url)) continue;
            const card = document.createElement('a');
            card.href = menu.Url;
            card.className = 'menu-card group bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 hover:shadow-md hover:border-blue-400 dark:hover:border-blue-500 transition-all duration-200 transform hover:-translate-y-1';
            const heading = document.createElement('h2');
            heading.className = 'text-lg font-bold text-slate-800 dark:text-slate-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors';
            heading.textContent = menuLabel(menu.MenuName);
            const description = document.createElement('p');
            description.className = 'menu-card-description text-sm text-slate-500 dark:text-slate-400 mt-2';
            description.textContent = String(menu.Description ?? '');
            // Native tooltip exposes all lines without changing the card's geometry.
            description.title = description.textContent;
            card.title = description.textContent;
            const action = document.createElement('span');
            action.className = 'menu-card-action mt-4 text-right text-blue-600 dark:text-blue-400 font-medium text-sm group-hover:underline';
            action.textContent = '입장하기 →';
            card.append(heading, description, action);
            fragment.append(card);
        }
        container.replaceChildren(fragment);
    }
    global.MenuCards = {render, orderAdmin, menuLabel};
})(window);
