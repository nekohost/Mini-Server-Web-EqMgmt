/* Own-request history, with safe text rendering and no approval/write actions. */
(function () {
    'use strict';
    const el = id => document.getElementById(id);
    const state = {page: 1, pages: 1, generation: 0, busy: false};
    const types = {ADD_CATEGORY: '카테고리 추가', ADD_MANUFACTURER: '제조사 추가',
        Lineup_Node: '라인업 노드', ADD_LINEUP_NODE: '라인업 노드', Equipment_Option: '옵션 스펙', ADD_EQUIPMENT_OPTION: '옵션 스펙'};
    const statuses = {PENDING: '처리 중', APPROVED: '승인 완료', REJECTED: '반려'};
    function text(tag, value, classes = '') {
        const element = document.createElement(tag); element.textContent = String(value ?? '-'); element.className = classes; return element;
    }
    function requestData(item) {
        try { const data = JSON.parse(item.RequestDataJSON); return data && typeof data === 'object' && !Array.isArray(data) ? data : {}; }
        catch { return {}; }
    }
    function itemName(data) { return data.name || data.option_name || data.node_name || data.Name || '-'; }
    function openDetail(item) {
        const data = requestData(item);
        el('my-approval-detail-title').textContent = `상신 상세 · #${item.RequestId}`;
        el('my-approval-detail-summary').textContent = [types[item.RequestType] || item.RequestType, itemName(data),
            `상태: ${statuses[item.Status] || item.Status}`, `요청일시: ${item.CreatedAt || '-'}`,
            `처리일시: ${item.Status === 'PENDING' ? '-' : item.UpdatedAt || '-'}`,
            ...(item.RejectReason ? [`반려 사유: ${item.RejectReason}`] : [])].join('\n');
        el('my-approval-detail-data').textContent = JSON.stringify(data, null, 2);
        el('my-approval-detail').showModal();
    }
    function render(items) {
        const body = el('my-approvals-body'); body.replaceChildren();
        if (!items.length) {
            const tr = document.createElement('tr'), td = text('td', '조건에 맞는 상신 이력이 없습니다.', 'p-6 text-center text-sm text-slate-500');
            td.colSpan = 6; tr.append(td); body.append(tr); return;
        }
        for (const item of items) {
            const tr = document.createElement('tr'), documentCell = text('td', '', 'p-3 text-sm whitespace-nowrap');
            documentCell.append(text('strong', `#${item.RequestId}`), text('p', item.CreatedAt, 'text-xs text-slate-500'));
            const status = text('td', statuses[item.Status] || item.Status, 'p-3 text-sm whitespace-nowrap ' +
                (item.Status === 'REJECTED' ? 'text-red-600 dark:text-red-400' : item.Status === 'APPROVED' ? 'text-green-700 dark:text-green-400' : 'text-amber-700 dark:text-amber-300'));
            const result = text('td', item.Status === 'PENDING' ? '-' : item.UpdatedAt || '-', 'p-3 text-sm');
            if (item.RejectReason) result.append(text('p', item.RejectReason, 'mt-1 max-w-sm break-words text-red-600 dark:text-red-400'));
            const detail = text('td', '', 'p-3'), button = text('button', '상세 보기', 'rounded border px-3 py-2 text-sm whitespace-nowrap');
            button.type = 'button'; button.addEventListener('click', () => openDetail(item)); detail.append(button);
            tr.append(documentCell, text('td', types[item.RequestType] || item.RequestType, 'p-3 text-sm whitespace-nowrap'),
                text('td', itemName(requestData(item)), 'p-3 text-sm font-semibold break-words'), status, result, detail); body.append(tr);
        }
    }
    function buttons() {
        el('my-approvals-prev').disabled = state.busy || state.page <= 1;
        el('my-approvals-next').disabled = state.busy || state.page >= state.pages;
    }
    async function load() {
        const generation = ++state.generation; state.busy = true; buttons();
        el('my-approvals-message').textContent = '상신 이력을 불러오는 중입니다.';
        try {
            const parameters = new URLSearchParams({page: state.page, per_page: 25, status: el('my-approvals-status').value});
            const response = await fetch('/api/my_approvals?' + parameters), result = await response.json();
            if (generation !== state.generation) return;
            if (!response.ok || !result.success || !Array.isArray(result.data)) throw new Error(result.message || '상신 이력을 불러오지 못했습니다.');
            state.page = result.page; state.pages = result.pages; render(result.data);
            el('my-approvals-page').textContent = `${result.total}건 · ${result.page}/${result.pages} 페이지`;
            el('my-approvals-message').textContent = '본인이 상신한 요청만 표시합니다.';
        } catch (error) {
            if (generation !== state.generation) return;
            el('my-approvals-body').replaceChildren(); el('my-approvals-page').textContent = '';
            el('my-approvals-message').textContent = error.message || '통신 오류가 발생했습니다. 다시 조회해 주세요.';
        } finally { if (generation === state.generation) { state.busy = false; buttons(); } }
    }
    el('my-approvals-filter').addEventListener('submit', event => { event.preventDefault(); state.page = 1; load(); });
    el('my-approvals-prev').addEventListener('click', () => { if (!state.busy && state.page > 1) { state.page--; load(); } });
    el('my-approvals-next').addEventListener('click', () => { if (!state.busy && state.page < state.pages) { state.page++; load(); } });
    load();
})();
