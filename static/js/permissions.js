/* Role-first permissions editor. Switching roles never submits or discards a draft. */
(function () {
    'use strict';
    const el = id => document.getElementById(id);
    const state = {rows: [], baseline: new Map(), role: null, busy: false};
    const key = row => JSON.stringify([row.Role, row.MenuCode]);
    const changed = row => Number(row.IsAllowed) !== state.baseline.get(key(row));
    const rowsFor = role => state.rows.filter(row => row.Role === role);
    function element(tag, text, classes = '') {
        const node = document.createElement(tag); node.textContent = text; node.className = classes; return node;
    }
    function message(text, error = false) {
        el('permission-message').textContent = text;
        el('permission-message').className = 'my-3 text-sm ' + (error ? 'text-red-600 dark:text-red-400' : 'text-slate-600 dark:text-slate-300');
    }
    function roles() {
        const query = el('permission-role-search').value.trim().toLocaleLowerCase();
        const list = el('permission-role-list'); list.replaceChildren();
        for (const role of [...new Set(state.rows.map(row => row.Role))].sort()) {
            if (!role.toLocaleLowerCase().includes(query)) continue;
            const rows = rowsFor(role), dirty = rows.filter(changed).length;
            const button = element('button', '', 'permission-role');
            button.type = 'button'; button.dataset.role = role;
            button.setAttribute('aria-pressed', String(state.role === role));
            button.setAttribute('aria-controls', 'permission-detail');
            button.append(element('strong', role), element('span', `허용 ${rows.filter(r => Number(r.IsAllowed) === 1).length}/${rows.length}` + (dirty ? ` · 미저장 ${dirty}` : ''), 'block text-xs mt-1'));
            button.addEventListener('click', () => {
                state.role = role; el('permission-menu-search').value = ''; message(''); render();
            });
            list.append(button);
        }
        if (!list.children.length) list.append(element('p', '표시할 역할이 없습니다.', 'text-sm text-slate-500'));
    }
    function descendantAllowed(code, rows, visited = new Set()) {
        if (visited.has(code)) return false;
        visited.add(code);
        return rows.filter(row => row.ParentMenuCode === code).some(row => Number(row.IsAllowed) === 1 || descendantAllowed(row.MenuCode, rows, visited));
    }
    function toggle(row) {
        if (state.busy) return;
        row.IsAllowed = Number(row.IsAllowed) === 1 ? 0 : 1;
        if (row.IsAllowed) {
            const byCode = new Map(rowsFor(row.Role).map(item => [item.MenuCode, item])), seen = new Set([row.MenuCode]);
            let parent = row.ParentMenuCode;
            while (parent && !seen.has(parent) && byCode.has(parent)) {
                seen.add(parent); const item = byCode.get(parent); item.IsAllowed = 1; parent = item.ParentMenuCode;
            }
        }
        render();
    }
    function render() {
        roles();
        el('permission-detail').hidden = state.role === null;
        el('permission-selected-title').textContent = state.role === null ? '역할을 선택해 주세요.' : `${state.role} 메뉴 권한`;
        const rows = rowsFor(state.role), body = el('permTableBody'); body.replaceChildren();
        const query = el('permission-menu-search').value.trim().toLocaleLowerCase(), seen = new Set();
        const visit = (row, depth) => {
            if (seen.has(row.MenuCode)) return;
            seen.add(row.MenuCode);
            const label = window.MenuCards.menuLabel(row.MenuName);
            if (!query || `${label} ${row.MenuCode}`.toLocaleLowerCase().includes(query)) {
                const tr = document.createElement('tr'); tr.dataset.menu = row.MenuCode;
                const name = element('td', (depth ? '— '.repeat(Math.min(depth, 8)) : '') + label, 'p-3 text-sm');
                const code = element('td', row.MenuCode, 'p-3 text-sm font-mono text-slate-500');
                const access = element('td', '', 'p-3 text-center');
                const box = document.createElement('input'); box.type = 'checkbox'; box.checked = Number(row.IsAllowed) === 1;
                box.disabled = state.busy || descendantAllowed(row.MenuCode, rows);
                box.setAttribute('aria-label', `${state.role} · ${label} 접근 허용`);
                box.title = box.disabled && !state.busy ? '허용된 하위 메뉴가 있어 상위 메뉴를 해제할 수 없습니다.' : label;
                box.className = 'h-5 w-5 disabled:opacity-50'; box.addEventListener('change', () => toggle(row));
                access.append(box); tr.append(name, code, access); body.append(tr);
            }
            rows.filter(child => child.ParentMenuCode === row.MenuCode).forEach(child => visit(child, depth + 1));
        };
        rows.filter(row => !row.ParentMenuCode).forEach(row => visit(row, 0));
        // Preserve orphan/cyclic metadata visibility without unbounded recursion.
        rows.forEach(row => visit(row, 0));
        if (state.role !== null && !body.children.length) {
            const td = element('td', '조건에 맞는 메뉴가 없습니다.', 'p-5 text-center text-sm'); td.colSpan = 3;
            const tr = document.createElement('tr'); tr.append(td); body.append(tr);
        }
        el('permission-save').disabled = state.busy || !rows.some(changed);
    }
    async function save() {
        if (state.busy || state.role === null || !rowsFor(state.role).some(changed)) return;
        const role = state.role;
        if (!confirm(`${role} 역할의 변경된 메뉴 권한을 저장하시겠습니까?`)) return;
        const payload = rowsFor(role).map(({Role, MenuCode, IsAllowed}) => ({Role, MenuCode, IsAllowed: Number(IsAllowed)}));
        state.busy = true; render();
        try {
            const response = await fetch('/api/permissions', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.getCSRFToken()}, body: JSON.stringify(payload)});
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.message || data.error || '권한 저장에 실패했습니다.');
            payload.forEach(row => state.baseline.set(key(row), row.IsAllowed));
            message(`${role} 역할의 권한을 저장했습니다.`);
        } catch (error) { message(error.message || '통신 오류입니다. 변경 내용은 유지됩니다.', true); }
        finally { state.busy = false; render(); }
    }
    el('permission-role-search').addEventListener('input', roles);
    el('permission-menu-search').addEventListener('input', render);
    el('permission-save').addEventListener('click', save);
    window.addEventListener('beforeunload', event => { if (state.rows.some(changed)) { event.preventDefault(); event.returnValue = ''; } });
    (async () => {
        message('역할과 메뉴를 불러오는 중입니다.');
        try {
            const response = await fetch('/api/permissions'), rows = await response.json();
            if (!response.ok || !Array.isArray(rows)) throw new Error('권한 정보를 불러오지 못했습니다.');
            state.rows = rows; rows.forEach(row => state.baseline.set(key(row), Number(row.IsAllowed)));
            message('역할을 선택해 주세요.'); render();
        } catch (error) { message(error.message, true); }
    })();
})();
