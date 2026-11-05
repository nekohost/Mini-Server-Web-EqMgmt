/* [MINI-COMMENT: ASSISTANT.POLISH.LIFECYCLE.UI.TESTS]
 * [EN rev.1]
 * [Role] Drives real title/loaded-selection/bulk controls through a deterministic in-memory transport.
 * [Dependencies] Linux loopback Chromium harness, candidate DOM/CSS/client, synthetic identity and per-item receipts.
 * [Impact] Checks cancellation, concurrent edits, exact-ID recovery, partial results, selected-chat transitions and the fifty-request pacing boundary without production services.
 */
(function () {
    'use strict';
    const theme = new URLSearchParams(location.search).get('theme') || 'light';
    localStorage.theme = theme; document.documentElement.classList.toggle('dark', theme === 'dark');
    window.module = { exports: {} };
    const originalFetch = window.fetch.bind(window), clone = value => JSON.parse(JSON.stringify(value));
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    const active = 'a'.repeat(32), model = 'e'.repeat(32), id = number => number.toString(16).padStart(32, '0');
    const now = Date.now() / 1000;
    const entry = (cid, title, trash = false, order = 1) => ({ id: cid, title, created: now - 1000, updated: order, selection_id: model,
        next_level: 'medium', selection_revision: 1, lifecycle_revision: trash ? 1 : 0, is_deleted: Number(trash),
        deleted_at: trash ? now - order : null, purge_after: trash ? now - order + 2592000 : null, read_only: trash });
    const conversations = new Map([[active, entry(active, '이름을 바꿀 대화', false, 100)]]);
    for (let number = 1; number <= 4; number++) conversations.set(id(number), entry(id(number), '보관 대화 ' + number, true, number));
    const receipts = new Map(), tombstones = new Map(), requests = [];
    const storage = { base_chars: 32000000, total_chars: 64000000, used_chars: 100, reserved_chars: 0, above_base: false };
    const server = { conversations, receipts, requests, modes: new Map(), inFlight: 0, maxInFlight: 0,
        respond(result, status = 200) { return new Response(JSON.stringify(result), { status, headers: { 'Content-Type': 'application/json', 'X-Assistant-Account': 'synthetic-polish-account' } }); },
        async fetch(path, options = {}) {
            const url = new URL(path, location.origin), method = options.method || 'GET';
            const data = typeof options.body === 'string' ? JSON.parse(options.body) : null;
            requests.push({ path: url.pathname, search: url.search, method, data: clone(data) });
            if (url.pathname === '/api/ai/capabilities') return this.respond({ success: true, reasoning_version: 2, storage, writes: true, file_tools: true, scopes: ['my'], tools: ['search_equipment'] });
            if (url.pathname === '/api/ai/status') return this.respond({ success: true, state: 'ready', scope: 'selection', checked_at: Date.now() / 1000, expires_at: Date.now() / 1000 + 60, message: '최근 연결 상태가 정상입니다.' });
            if (url.pathname === '/api/ai/models') return this.respond({ success: true, default_model: model, models: [{ id: model, provider: '합성 연결', label: '합성 모델', available: true, tools: true, levels: ['off', 'medium'], default_level: 'medium', level_reasons: {} }] });
            if (url.pathname === '/api/ai/conversations' && method === 'GET') {
                const view = url.searchParams.get('view') || 'active', offset = Number(url.searchParams.get('cursor') || 0);
                const items = [...conversations.values()].filter(item => Boolean(item.is_deleted) === (view === 'trash') && (!item.purge_after || item.purge_after > Date.now() / 1000)).sort((left, right) => left.id.localeCompare(right.id));
                return this.respond({ success: true, conversations: clone(items.slice(offset, offset + 2)), next_cursor: offset + 2 < items.length ? String(offset + 2) : null, view, server_time: Date.now() / 1000 });
            }
            const route = /^\/api\/ai\/conversations\/([a-f0-9]{32})\/(messages|rename|restore|purge|trash|selection)$/.exec(url.pathname);
            if (!route) return this.respond({ success: false, message: '예상하지 않은 합성 요청입니다.' }, 422);
            const cid = route[1], action = route[2], item = conversations.get(cid);
            if (action === 'messages') {
                const view = url.searchParams.get('view') || 'active';
                if (!item || Boolean(item.is_deleted) !== (view === 'trash')) return this.respond({ success: false, message: '대화를 찾을 수 없습니다.' }, 404);
                if (item.is_deleted && item.purge_after <= Date.now() / 1000) return this.respond({ success: false, message: '보관 기간이 끝난 대화입니다.' }, 410);
                return this.respond({ success: true, conversation: clone(item), messages: [{ id: 1000 + parseInt(cid.slice(-4), 16), role: 'assistant', content: '기존 메시지와 **안전한 텍스트**를 유지합니다.', reasoning: '기존 추론 내용', job: null }], jobs: [], proposals: [], next_before: null, storage });
            }
            if (method !== 'POST') return this.respond({ success: false, message: '요청 형식을 확인해 주세요.' }, 400);
            if (action === 'selection') return this.respond({ success: true, revision: 2, selection_id: model, level: data.level });
            this.inFlight++; this.maxInFlight = Math.max(this.maxInFlight, this.inFlight);
            try {
                await sleep(5);
                const previous = receipts.get(data.operation_id);
                if (previous) {
                    if (previous.path !== url.pathname || JSON.stringify(previous.data) !== JSON.stringify(data)) return this.respond({ success: false, message: '조작 식별자 충돌입니다.' }, 409);
                    const current = clone(conversations.get(cid) || tombstones.get(cid));
                    const expired = action === 'rename' && current.is_deleted && current.purge_after <= Date.now() / 1000;
                    if (expired) delete current.title;
                    return this.respond({ success: true, action, operation_id: data.operation_id, replayed: true, conversation: current, purged: tombstones.has(cid), expired: Boolean(expired) });
                }
                if (!item) return this.respond({ success: false, message: '대화를 찾을 수 없습니다.' }, 404);
                const mode = this.modes.get(cid + '/' + action); this.modes.delete(cid + '/' + action);
                if (mode === 'lost-before') throw new TypeError('synthetic disconnect before apply');
                if (mode === 'reject') return this.respond({ success: false, message: '합성 항목별 실패: 이 항목은 유지됩니다.' }, 422);
                if (mode === 'conflict' || data.lifecycle_revision !== item.lifecycle_revision || action === 'rename' && (item.is_deleted || data.expected_title !== item.title)) return this.respond({ success: false, message: '다른 화면에서 대화 이름이나 상태가 변경되었습니다.' }, 409);
                if (action === 'rename') item.title = data.title.trim();
                else if (action === 'purge') { conversations.delete(cid); tombstones.set(cid, { id: cid, is_deleted: 1, lifecycle_revision: item.lifecycle_revision + 1 }); }
                else { item.is_deleted = Number(action === 'trash'); item.deleted_at = item.is_deleted ? Date.now() / 1000 : null; item.purge_after = item.is_deleted ? item.deleted_at + 2592000 : null; item.read_only = Boolean(item.is_deleted); }
                item.lifecycle_revision++;
                receipts.set(data.operation_id, { path: url.pathname, data: clone(data) });
                if (mode === 'lost-after') throw new TypeError('synthetic ACK loss');
                return this.respond({ success: true, action, operation_id: data.operation_id, conversation: clone(conversations.get(cid) || tombstones.get(cid)), purged: tombstones.has(cid), storage });
            } finally { this.inFlight--; }
        }
    };
    window.__polishLifecycleServer = server;
    window.fetch = (path, options) => new URL(path, location.origin).pathname.startsWith('/api/ai/') ? server.fetch(path, options) : originalFetch(path, options);

    document.addEventListener('DOMContentLoaded', async () => {
        const checks = [], report = document.createElement('pre'); report.id = 'browser-test-result'; report.hidden = true; document.body.append(report);
        const $ = name => document.getElementById(name), posts = action => requests.filter(item => item.method === 'POST' && item.path.endsWith('/' + action));
        const wait = async (test, label = 'condition') => { for (let count = 0; count < 1600; count++) { if (test()) return; await sleep(10); } throw new Error(label + ' timed out'); };
        const assert = (value, name) => { if (!value) throw new Error(name); checks.push(name); };
        const dialog = async name => wait(() => $('ai-lifecycle-dialog').open && $('ai-dialog-title').textContent.includes(name) && $('ai-lifecycle-dialog').getAttribute('aria-busy') === 'false', name);
        const dismiss = async () => { $('ai-dialog-confirm').click(); await wait(() => !$('ai-lifecycle-dialog').open && $('equipment-ai').getAttribute('aria-busy') === 'false'); };
        const checkbox = cid => document.querySelector(`.ai-trash-select[data-conversation-id="${cid}"]`);
        const loaded = () => document.querySelectorAll('.ai-trash-select').length;
        const refresh = async () => { const before = requests.filter(item => item.path === '/api/ai/conversations').length; window.dispatchEvent(new Event('focus')); await wait(() => requests.filter(item => item.path === '/api/ai/conversations').length > before); await sleep(20); };
        const loadAll = async () => { for (let limit = 0; limit < 40 && !$('ai-more-conversations').hidden; limit++) { const count = loaded(); $('ai-more-conversations').click(); await wait(() => loaded() > count || $('ai-more-conversations').hidden); } };
        const rename = async title => { $('ai-rename-current').click(); await wait(() => $('ai-rename-dialog').open); $('ai-rename-input').value = title; $('ai-rename-form').requestSubmit(); };
        const publish = result => { report.textContent = JSON.stringify(result); if (window.parent !== window) window.parent.postMessage({ fixtureResult: report.textContent }, location.origin); };
        try {
            await wait(() => $('ai-title').textContent === '이름을 바꿀 대화' && !$('ai-rename-current').disabled);
            assert($('ai-rename-current').title === '대화 세션의 이름 변경' && $('ai-rename-current').nextElementSibling === $('ai-trash-current'), 'rename-left-of-trash-with-exact-tooltip');
            const draft = '보존해야 할 작성 중 초안', message = document.querySelector('.ai-message'), modelBefore = $('ai-model').value;
            $('ai-input').value = draft;
            $('ai-rename-current').click(); $('ai-rename-input').value = '   '; $('ai-rename-form').requestSubmit();
            await wait(() => $('ai-rename-error').textContent.includes('1~100'));
            assert(posts('rename').length === 0, 'invalid-title-blocked-before-network');
            const literal = '<img src=x onerror="window.__titlePwned=1"> 새 이름 😀';
            $('ai-rename-input').value = literal; $('ai-rename-form').requestSubmit(); $('ai-rename-form').requestSubmit();
            await wait(() => !$('ai-rename-dialog').open && !$('ai-rename-current').disabled && $('ai-title').textContent === literal);
            assert(posts('rename').length === 1 && $('ai-input').value === draft && document.querySelector('.ai-message') === message && $('ai-model').value === modelBefore, 'rename-once-preserves-draft-message-and-model');
            assert(!$('ai-title').querySelector('img') && !window.__titlePwned && $('ai-title').getAttribute('aria-label') === literal, 'renamed-title-is-inert-and-fully-accessible');
            assert(document.activeElement === $('ai-rename-current'), 'rename-success-restores-trigger-focus');
            $('ai-rename-current').click(); $('ai-rename-input').value = '취소할 이름'; $('ai-rename-cancel').click();
            assert(posts('rename').length === 1 && $('ai-title').textContent === literal && $('ai-input').value === draft, 'rename-cancel-preserves-everything');

            $('ai-rename-current').click(); $('ai-rename-input').value = '충돌 후 직접 저장한 이름';
            conversations.get(active).title = '다른 탭의 현재 이름'; conversations.get(active).lifecycle_revision++;
            $('ai-rename-form').requestSubmit();
            await wait(() => $('ai-rename-error').textContent.includes('현재 이름을 확인') && !$('ai-rename-save').disabled);
            assert($('ai-rename-current-title').textContent.includes('다른 탭의 현재 이름') && $('ai-rename-input').value === '충돌 후 직접 저장한 이름', 'rename-conflict-keeps-draft-and-shows-current-title');
            const conflictPosts = posts('rename').length;
            $('ai-rename-form').requestSubmit(); await wait(() => !$('ai-rename-dialog').open && !$('ai-rename-current').disabled);
            assert(posts('rename').length === conflictPosts + 1 && posts('rename').at(-1).data.expected_title === '다른 탭의 현재 이름', 'conflict-requires-explicit-new-save-with-current-cas');

            server.modes.set(active + '/rename', 'lost-before'); await rename('미확인 이름'); await dialog('확인 필요'); await dismiss();
            const lostBefore = posts('rename').at(-1);
            assert(!$('ai-lifecycle-reconcile').hidden && $('ai-input').disabled, 'ambiguous-rename-blocks-fresh-writes');
            $('ai-lifecycle-reconcile').click(); await dialog('이름 변경 요청 확인'); $('ai-dialog-cancel').click(); await sleep(20);
            assert(posts('rename').at(-1) === lostBefore, 'ambiguous-rename-retry-cancel-does-not-post');
            $('ai-lifecycle-reconcile').click(); await dialog('이름 변경 요청 확인'); $('ai-dialog-confirm').click();
            await wait(() => $('ai-lifecycle-reconcile').hidden && !$('ai-rename-current').disabled);
            assert(posts('rename').at(-1).data.operation_id === lostBefore.data.operation_id && posts('rename').at(-1).data.expected_title === lostBefore.data.expected_title, 'ambiguous-rename-retries-only-exact-original-identity-and-payload');
            server.modes.set(active + '/rename', 'lost-after'); await rename('응답 유실 후 확인한 이름'); await dialog('확인 필요'); await dismiss();
            const afterApplyPosts = posts('rename').length;
            $('ai-lifecycle-reconcile').click(); await dialog('현재 상태'); await dismiss();
            assert(posts('rename').length === afterApplyPosts && $('ai-title').textContent === '응답 유실 후 확인한 이름' && document.querySelector('.ai-message') === message, 'applied-rename-reconciles-with-get-and-preserves-message-node');

            server.modes.set(active + '/rename', 'lost-after'); await rename('만료되면 다시 노출하지 않을 이름'); await dialog('확인 필요'); await dismiss();
            const expiredRow = conversations.get(active); expiredRow.is_deleted = 1; expiredRow.deleted_at = Date.now() / 1000 - 31 * 86400; expiredRow.purge_after = expiredRow.deleted_at + 2592000; expiredRow.lifecycle_revision++;
            $('ai-lifecycle-reconcile').click(); await dialog('이름 변경 요청 확인'); $('ai-dialog-confirm').click();
            await wait(() => $('ai-lifecycle-reconcile').hidden && !$('ai-rename-dialog').open && $('ai-notice').textContent.includes('보관 기간이 만료'));
            assert(!$('ai-title').textContent.includes('만료되면') && !$('ai-messages').textContent && $('ai-notice').textContent.includes('더 이상 표시하지 않습니다'), 'expired-rename-receipt-clears-stale-chat-without-refetching-title');

            $('ai-trash-tab').click(); await wait(() => loaded() === 2);
            assert($('ai-trash-bulk-restore').disabled && $('ai-trash-selected-count').textContent === '선택 0개', 'trash-starts-unselected-and-bulk-disabled');
            const selectedTitle = $('ai-title').textContent;
            checkbox(id(1)).click();
            assert($('ai-trash-select-all').indeterminate && $('ai-title').textContent === selectedTitle, 'row-checkbox-does-not-open-conversation-and-sets-indeterminate');
            $('ai-trash-select-all').click();
            assert($('ai-trash-select-all').checked && $('ai-trash-selected-count').textContent === '선택 2개', 'select-all-covers-only-loaded-two');
            $('ai-more-conversations').click(); await wait(() => loaded() === 4);
            assert(!checkbox(id(3)).checked && !checkbox(id(4)).checked && $('ai-trash-select-all').indeterminate && $('ai-trash-select-all-label').textContent.includes('4개'), 'more-appends-unselected-rows-and-updates-loaded-range');
            await refresh();
            assert(checkbox(id(1)).checked && checkbox(id(2)).checked && !checkbox(id(3)).checked, 'background-refresh-preserves-valid-selection-ids');
            $('ai-active-tab').click(); await wait(() => $('ai-active-tab').getAttribute('aria-pressed') === 'true');
            $('ai-trash-tab').click(); await wait(() => loaded() === 4);
            assert($('ai-trash-selected-count').textContent === '선택 0개', 'changing-history-tab-clears-selection');

            document.querySelector(`.ai-conversation[data-conversation-id="${id(1)}"]`).click();
            await wait(() => $('ai-title').textContent === '보관 대화 1' && !$('ai-restore-current').disabled);
            checkbox(id(1)).click(); checkbox(id(2)).click(); server.modes.set(id(2) + '/restore', 'reject');
            $('ai-trash-bulk-restore').click(); await dialog('2개 복구 확인');
            assert($('ai-dialog-detail').textContent.includes('보관 대화 1') && $('ai-dialog-detail').textContent.includes('보관 대화 2'), 'bulk-restore-confirmation-lists-selected-targets');
            $('ai-dialog-confirm').click(); await dialog('복구 결과');
            assert($('ai-dialog-message').textContent.includes('성공 1개 · 실패 1개 · 확인 중 0개') && !conversations.get(id(1)).is_deleted && conversations.get(id(2)).is_deleted, 'bulk-restore-reports-independent-partial-success');
            await dismiss();
            assert(checkbox(id(2)).checked && !checkbox(id(1)) && !$('ai-input').disabled && $('ai-input').value === draft, 'restored-current-chat-unlocks-with-draft-and-failed-selection-retained');

            server.modes.set(id(2) + '/restore', 'lost-after'); $('ai-trash-bulk-restore').click(); await dialog('1개 복구 확인'); $('ai-dialog-confirm').click(); await dialog('복구 결과');
            assert($('ai-dialog-message').textContent.includes('확인 중 1개'), 'bulk-unknown-is-not-counted-as-failure-or-success'); await dismiss();
            const restorePosts = posts('restore').length;
            $('ai-lifecycle-reconcile').click(); await dialog('현재 상태'); await dismiss();
            assert(posts('restore').length === restorePosts && $('ai-lifecycle-reconcile').hidden, 'bulk-unknown-restoration-reconciles-without-reposting');

            checkbox(id(3)).click(); checkbox(id(4)).click(); const purgeBeforeCancel = posts('purge').length;
            $('ai-trash-bulk-purge').click(); await dialog('2개 영구삭제 확인');
            assert($('ai-dialog-detail').textContent.includes('앱에서 복구할 수 없') && document.activeElement === $('ai-dialog-cancel'), 'bulk-purge-final-confirmation-is-explicit-and-cancel-focused');
            $('ai-dialog-cancel').click(); await sleep(20);
            assert(posts('purge').length === purgeBeforeCancel && conversations.has(id(3)) && conversations.has(id(4)), 'bulk-purge-cancel-is-nonmutating');
            server.modes.set(id(4) + '/purge', 'conflict'); $('ai-trash-bulk-purge').click(); await dialog('2개 영구삭제 확인'); $('ai-dialog-confirm').click(); await dialog('영구삭제 결과');
            assert($('ai-dialog-message').textContent.includes('성공 1개 · 실패 1개') && !conversations.has(id(3)) && conversations.has(id(4)), 'bulk-purge-partial-failure-keeps-unmodified-target'); await dismiss();
            server.modes.set(id(4) + '/purge', 'lost-after'); $('ai-trash-bulk-purge').click(); await dialog('1개 영구삭제 확인'); $('ai-dialog-confirm').click(); await dialog('영구삭제 결과'); await dismiss();
            const lostPurge = posts('purge').at(-1);
            $('ai-lifecycle-reconcile').click(); await dialog('영구삭제 확인'); $('ai-dialog-confirm').click(); await dialog('기처리 요청'); await dismiss();
            assert(posts('purge').at(-1).data.operation_id === lostPurge.data.operation_id && $('ai-lifecycle-reconcile').hidden, 'lost-bulk-purge-requires-confirmed-same-id-receipt-replay');

            for (let number = 100; number < 152; number++) conversations.set(id(number), entry(id(number), '속도 경계 대화 ' + number, true, number));
            await refresh(); await loadAll();
            assert(loaded() === 52, 'loaded-scope-reaches-more-than-fifty-without-unseen-selection');
            $('ai-trash-select-all').click(); $('ai-trash-bulk-restore').click(); await dialog('52개 복구 확인'); const priorCount = posts('restore').length; $('ai-dialog-confirm').click();
            await wait(() => $('ai-dialog-message').textContent.includes('다음 묶음까지'), 'fifty item pacing window');
            assert(posts('restore').length === priorCount + 50 && $('ai-active-tab').disabled && !$('ai-bulk-stop').hidden, 'bulk-pauses-after-fifty-and-exposes-stop-with-explicit-lock');
            $('ai-bulk-stop').click(); await dialog('복구 결과');
            assert($('ai-dialog-message').textContent.includes('성공 50개') && $('ai-dialog-message').textContent.includes('미처리 2개') && posts('restore').length === priorCount + 50, 'bulk-stop-leaves-unsent-items-unchanged'); await dismiss();
            assert(loaded() === 2 && $('ai-trash-selected-count').textContent === '선택 2개' && server.maxInFlight === 1, 'remaining-selection-retained-and-all-mutations-strictly-sequential');
            assert(posts('turns').length === 0 && posts('cancel').length === 0, 'naming-and-bulk-never-replay-model-work');
            if (innerWidth <= 760 && !$('ai-sidebar').classList.contains('is-open')) $('ai-menu-toggle').click();
            assert(document.documentElement.scrollWidth <= innerWidth + 1 && $('equipment-ai').getBoundingClientRect().right <= innerWidth + 1, 'lifecycle-controls-fit-viewport-in-both-themes');
            assert(!$('ai-title').querySelector('img') && !$('ai-dialog-detail').querySelector('img') && !window.__titlePwned, 'all-user-controlled-titles-remain-text-only');
            publish({ status: 'pass', width: innerWidth, theme, checks, requests: requests.length, max_mutations_in_flight: server.maxInFlight });
        } catch (error) { publish({ status: 'fail', width: innerWidth, theme, checks, error: String(error.stack || error) }); }
    });
})();
