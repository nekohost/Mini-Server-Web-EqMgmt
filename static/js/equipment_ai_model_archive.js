/* [MINI-COMMENT: ASSISTANT.PROVIDERS.ARCHIVE.CLIENT]
 * [EN rev.1]
 * [Role] Lists stored model records absent from the latest inventory and lets an administrator unpublish one.
 * [Dependencies] Read-only /api/admin/ai/models/archive, the existing revision-checked model-settings API, CSRF and
 * the global loading overlay; all text is inserted as text nodes.
 * [Impact] No deletion and no route change; unpublishing only keeps a record from returning to users automatically.
 */
(function () {
    'use strict';
    const root = document.getElementById('ai-providers-admin');
    if (!root || !root.classList.contains('provider-archive')) return;
    const $ = id => document.getElementById(id), dialog = $('provider-dialog');
    const params = new URLSearchParams(location.search);
    let busy = false;

    /** [Role] Same-origin JSON call; POST carries the per-session CSRF token. */
    async function api(path, data) {
        const response = await fetch(path, { method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
            headers: data === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRFToken': root.dataset.csrf },
            body: data === undefined ? undefined : JSON.stringify(data) });
        const value = await response.json().catch(() => ({}));
        if (!response.ok || value.success !== true) throw Error(value.message || '요청을 완료하지 못했습니다.');
        return value;
    }

    /** [Role] Text-only confirm/result dialog. */
    function ask(title, message, confirm) {
        return new Promise(resolve => {
            $('provider-dialog-title').textContent = title; $('provider-dialog-message').textContent = message;
            $('provider-dialog-cancel').hidden = !confirm; dialog.returnValue = '';
            dialog.addEventListener('close', () => resolve(dialog.returnValue === 'accept'), { once: true });
            dialog.showModal();
        });
    }

    function cell(row, text, header) {
        const node = document.createElement(header ? 'th' : 'td'); if (header) node.scope = 'row';
        if (text instanceof Node) node.append(text); else node.textContent = text; row.append(node); return node;
    }

    function chip(text, tone) { const node = document.createElement('span'); node.className = 'provider-badge provider-badge-' + tone; node.textContent = text; return node; }

    /** [Role] Renders the filter and the record table from one safe projection. */
    function render(value) {
        const select = $('archive-provider'), chosen = params.get('provider') || '';
        select.replaceChildren(new Option('전체 연결', ''));
        for (const provider of value.providers) select.append(new Option(provider.name + ' (' + provider.archived + ')', provider.id));
        select.value = chosen;
        const body = $('archive-table').tBodies[0]; body.replaceChildren();
        for (const model of value.models) {
            const row = document.createElement('tr');
            cell(row, model.provider_name + (model.provider_retired ? ' · 폐기' : ''), true);
            cell(row, model.label);
            const id = document.createElement('code'); id.textContent = model.upstream; cell(row, id);
            cell(row, model.checked ? new Date(model.checked * 1000).toLocaleString() : '기록 없음');
            cell(row, model.published ? chip('사용자에게 자동 재공개', 'warn') : chip('비공개로 복귀', 'muted'));
            const actions = document.createElement('span');
            if (model.published && !model.provider_retired) {
                const button = document.createElement('button'); button.type = 'button'; button.textContent = '공개 해제';
                button.addEventListener('click', () => unpublish(model)); actions.append(button);
            } else actions.textContent = '—';
            cell(row, actions); body.append(row);
        }
        $('archive-caption').textContent = '기록 ' + value.models.length + '건' + (chosen ? ' · 선택한 연결' : ' · 전체 연결');
        $('archive-empty').hidden = Boolean(value.models.length);
        $('archive-table').hidden = !value.models.length;
    }

    async function load() {
        const provider = params.get('provider');
        render(await api('/api/admin/ai/models/archive' + (provider ? '?provider=' + encodeURIComponent(provider) : '')));
    }

    /** [Role] Unpublishes one stored record through the existing revision-checked model-settings API. */
    async function unpublish(model) {
        if (busy || !await ask('공개 해제', '“' + model.label + '”을 비공개로 바꿀까요? 연결이 이 모델을 다시 제공해도 사용자에게 자동으로 공개되지 않습니다. 기록과 시험 결과는 삭제되지 않습니다.', true)) return;
        busy = true; window.showGlobalLoading?.('공개 해제 중입니다...');
        try {
            await api('/api/admin/ai/providers/' + model.provider + '/models', { id: model.id, label: model.label, published: false, sort_order: model.sort_order,
                context_tokens: model.context_tokens, revision: model.provider_revision, profile_revision: model.profile_revision });
            await load(); $('archive-notice').textContent = '“' + model.label + '”을 비공개로 바꿨습니다.';
        } catch (error) { await ask('공개 해제 실패', error.message + ' 목록을 새로고침한 뒤 다시 확인해 주세요.', false); }
        finally { busy = false; window.hideGlobalLoading?.(); }
    }

    $('archive-provider').addEventListener('change', event => {
        if (event.target.value) params.set('provider', event.target.value); else params.delete('provider');
        history.replaceState(null, '', location.pathname + (params.toString() ? '?' + params : ''));
        load().catch(error => { $('archive-notice').textContent = error.message; });
    });
    $('archive-reload').addEventListener('click', () => load().then(() => { $('archive-notice').textContent = '현재 기록을 불러왔습니다.'; }, error => { $('archive-notice').textContent = error.message; }));
    load().catch(error => { $('archive-notice').textContent = error.message; });
})();
