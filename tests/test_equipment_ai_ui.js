/* [MINI-COMMENT: ASSISTANT.UI.LIFECYCLE.REGRESSION]
 * [EN rev.7]
 * [Role] Drives the real candidate DOM against a deterministic in-memory transport, including a second live app frame.
 * [Dependencies] assistant_ui_browser_fixture.py injection before equipment_ai.js; synthetic IDs, data and CSRF only.
 * [Impact] Preserves table/lifecycle/stream regressions while checking the compact composer, scoped error recovery, conditional model/support feedback, measured 136px model cap, browser-measured native reasoning widths, 760/761 boundary and state-preserving reflow without touching real services. An opt-in synthetic completion gate separates live-state assertions from terminal rendering. Focus checks here are programmatic; native keyboard and zoom probes remain separate.
 */
(function () {
    'use strict';
    const params = new URLSearchParams(location.search);
    const peer = params.get('peer') === '1';
    const theme = params.get('theme') || 'light';
    localStorage.theme = theme;
    document.documentElement.classList.toggle('dark', theme === 'dark');
    window.module = { exports: {} };
    const nativeFetch = window.fetch.bind(window);
    const cid = 'a'.repeat(32), oldCid = 'd'.repeat(32), trashCid = '9'.repeat(32), newCid = '7'.repeat(32), jid = 'b'.repeat(32), proposalId = 'c'.repeat(32), modelId = 'e'.repeat(32);
    const clone = value => JSON.parse(JSON.stringify(value));
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    const plainTable = '| 장비 | 수량 | 메모 |\n| :--- | ---: | :---: |\n| 노트북 \\| PC | 2 | **확인** |\n| 서버 | |\n| <img src=x onerror="window.__assistantPwned=1"> | 1 | [내 장비](/my_equipment) |';
    if (!peer) {
        const now = Date.now() / 1000;
        const conversations = new Map([
            [cid, { id: cid, title: '표와 휴지통 확인 <img src=x>', updated: 3, is_deleted: 0, deleted_at: null, purge_after: null, lifecycle_revision: 0, selection_id: modelId, selection_revision: 1, next_level: 'medium' }],
            [oldCid, { id: oldCid, title: '이전 페이지 대화', updated: 1, is_deleted: 0, deleted_at: null, purge_after: null, lifecycle_revision: 0, selection_id: modelId, selection_revision: 1, next_level: 'medium' }],
            [trashCid, { id: trashCid, title: '미리 보관한 대화', updated: 2, is_deleted: 1, deleted_at: now - 60, purge_after: now - 60 + 2592000, lifecycle_revision: 1, selection_id: modelId, selection_revision: 1, next_level: 'medium' }],
        ]);
        const receipts = new Map(), tombstones = new Map(), requests = [];
        const models = [
            { id: modelId, provider: '260Strata', label: 'Qwen3.8 Flash Next', available: true, tools: true, levels: ['off', 'low', 'medium', 'xhigh'], default_level: 'medium', level_reasons: { high: '모델 미지원', max: '모델 미지원' } },
            { id: 'f'.repeat(32), provider: '보조 연결', label: '대화 모델 <img src=x>', available: true, tools: false, levels: [] },
            { id: '8'.repeat(32), provider: '중지 연결', label: '보관 모델', available: false, tools: false, levels: [], reason: '관리자가 연결을 비활성화했습니다.' },
        ];
        const storage = { base_chars: 32000000, extension_chars: 32000000, total_chars: 64000000, used_chars: 32000001, reserved_chars: 0, above_base: true };
        const server = { conversations, receipts, requests, models, mode: '', failReads: 0, failModelReads: 0, sent: 0, polls: 0, mutations: 0, proposalState: 'pending', holdStreamCompletion: false, now,
            respond(result, status = 200) { return new Response(JSON.stringify(result), { status, headers: { 'Content-Type': 'application/json', 'X-Assistant-Account': 'synthetic-ui-account' } }); },
            async fetch(path, options = {}) {
                const url = new URL(path, location.origin), method = options.method || 'GET';
                const data = options.body && typeof options.body === 'string' ? JSON.parse(options.body) : null;
                requests.push({ path: url.pathname, search: url.search, method, data: clone(data), headers: clone(options.headers || {}) });
                if (method === 'GET' && this.failReads && /\/conversations(?:\/|$)/.test(url.pathname)) { this.failReads--; throw new TypeError('synthetic read disconnect'); }
                if (url.pathname === '/api/ai/capabilities') return this.respond({ success: true, storage, reasoning_version: 2, writes: true, file_tools: true, scopes: ['my', 'public'], tools: ['search_equipment', 'prepare_equipment_create', 'prepare_catalog_request'] });
                if (url.pathname === '/api/ai/models') {
                    if (this.holdModels) { const hold = this.holdModels; this.holdModels = null; await hold; }
                    if (this.failModelReads) { this.failModelReads--; return this.respond({ success: false, message: '시험용 모델 목록 오류: 현재 선택을 유지합니다.' }, 503); }
                    return this.respond({ success: true, models: this.omitSelectedModel ? models.filter(item => item.id !== modelId) : models, default_model: modelId });
                }
                if (url.pathname === '/api/ai/conversations' && method === 'POST') {
                    conversations.set(newCid, { id: newCid, title: '새로운 대화', updated: 4, is_deleted: 0, deleted_at: null, purge_after: null, lifecycle_revision: 0, selection_id: modelId, selection_revision: 1, next_level: 'medium', empty: true });
                    return this.respond({ success: true, id: newCid });
                }
                if (url.pathname === '/api/ai/conversations' && method === 'GET') {
                    const view = url.searchParams.get('view') || 'active', cursor = url.searchParams.get('cursor');
                    if (this.holdList) { const hold = this.holdList; this.holdList = null; await hold; }
                    if (cursor && this.holdCursor) { const hold = this.holdCursor; this.holdCursor = null; await hold; }
                    if (cursor && !new RegExp('^' + view + '-next(?:-\\d+)?$').test(cursor)) return this.respond({ success: false, message: '다른 보관함 커서입니다.' }, 422);
                    const items = [...conversations.values()].filter(item => Boolean(item.is_deleted) === (view === 'trash') && (!item.purge_after || item.purge_after > Date.now() / 1000)).sort((a,b) => b.updated - a.updated);
                    const offset = cursor ? Number(cursor.split('-')[2] || 1) : 0;
                    return this.respond({ success: true, conversations: items.slice(offset, offset + 1), next_cursor: items.length > offset + 1 ? view + '-next' + (offset ? '-' + (offset + 1) : '') : null });
                }
                const route = /^\/api\/ai\/conversations\/([a-f0-9]{32})\/(messages|selection|turns|trash|restore|purge)$/.exec(url.pathname);
                if (route) {
                    const id = route[1], action = route[2], item = conversations.get(id);
                    if (method === 'POST' && ['trash', 'restore', 'purge'].includes(action)) {
                        await sleep(35);
                        if (receipts.has(data.operation_id)) return this.respond({ ...clone(receipts.get(data.operation_id)), replayed: true, conversation: clone(conversations.get(id) || tombstones.get(id) || receipts.get(data.operation_id).conversation), purged: tombstones.has(id) });
                        if (!item) return this.respond({ success: false, message: '대화를 찾을 수 없습니다.' }, 404);
                        const mode = this.mode; this.mode = '';
                        if (mode === 'lost-before-apply') throw new TypeError('synthetic mutation disconnect');
                        if (mode === 'reject') return this.respond({ success: false, message: '요청 상태를 확인해 주세요.' }, 422);
                        if (mode === 'expire-on-restore') item.purge_after = Date.now() / 1000 - 1;
                        if (data.lifecycle_revision !== item.lifecycle_revision) return this.respond({ success: false, message: '다른 탭에서 대화 상태가 변경되었습니다.' }, 409);
                        if (action !== 'trash' && (!item.is_deleted || item.purge_after <= Date.now() / 1000)) return this.respond({ success: false, message: '보관 기간이 만료되었거나 상태가 바뀌었습니다.' }, 410);
                        item.lifecycle_revision++; this.mutations++;
                        let result;
                        if (action === 'purge') {
                            const metadata = { id, is_deleted: 1, lifecycle_revision: item.lifecycle_revision, deleted_at: item.deleted_at, purge_after: item.purge_after };
                            tombstones.set(id, metadata); conversations.delete(id); result = { success: true, purged: true, conversation: metadata };
                        }
                        else {
                            item.is_deleted = action === 'trash' ? 1 : 0;
                            item.deleted_at = item.is_deleted ? Date.now() / 1000 : null;
                            item.purge_after = item.is_deleted ? item.deleted_at + 2592000 : null;
                            this.proposalState = 'cancelled';
                            result = { success: true, conversation: clone(item) };
                        }
                        receipts.set(data.operation_id, clone(result));
                        if (mode === 'lost-after-apply') throw new TypeError('synthetic ACK lost');
                        if (mode === 'ack-refresh-failure') this.failReads = 2;
                        return this.respond(result);
                    }
                    if (!item) return this.respond({ success: false, message: '대화를 찾을 수 없습니다.' }, 404);
                    if (action === 'messages') {
                        const view = url.searchParams.get('view') || 'active';
                        if (Boolean(item.is_deleted) !== (view === 'trash') || item.purge_after && item.purge_after <= Date.now() / 1000) return this.respond({ success: false, message: '이 보관함에서 열 수 없는 대화입니다.' }, 404);
                        const before = url.searchParams.has('before');
                        const messages = item.empty ? [] : before ? [{ id: 1, role: 'user', content: '이전 질문', reasoning: '', job: null }] : id === cid ? this.sent ? [
                            { id: 101, role: 'user', content: '표로 정리해 줘', reasoning: '', job: jid },
                            { id: 102, role: 'assistant', content: '', reasoning: '', job: jid },
                        ] : [{ id: 101, role: 'user', content: '내 장비 표를 보여 줘', reasoning: '', job: null }, { id: 102, role: 'assistant', content: plainTable, reasoning: '조회 범위와 권한을 확인했습니다.', job: null }] : [{ id: 201, role: 'assistant', content: id === oldCid ? plainTable : '보관한 대화 내용입니다.', reasoning: '보관한 추론입니다.', job: null }];
                        const proposal = { id: proposalId, operation: 'equipment_create', payload: JSON.stringify({ name: '확인 장비' }), before_json: '{}', state: this.proposalState, result: '', expires: Date.now() / 1000 + 600 };
                        return this.respond({ success: true, storage, conversation: clone(item), messages, next_before: !before && id === cid ? 101 : null,
                            proposals: id === cid ? [proposal] : [], jobs: this.sent && id === cid ? [{ id: jid, state: this.polls >= 3 || item.is_deleted ? 'cancelled' : 'queued', steps: 0 }] : [] });
                    }
                    if (item.is_deleted) return this.respond({ success: false, message: '읽기 전용 대화입니다.' }, 409);
                    if (action === 'selection') {
                        if (this.rejectNextSelection) { this.rejectNextSelection = false; return this.respond({ success: false, message: '시험용 설정 저장 오류: 다시 선택해 주세요.' }, 422); }
                        item.selection_id = data.selection_id; item.next_level = data.level; item.selection_revision++; return this.respond({ success: true, revision: item.selection_revision });
                    }
                    if (action === 'turns') {
                        if (this.rejectNextTurn) { this.rejectNextTurn = false; return this.respond({ success: false, message: '시험용 입력 거부: 초안은 유지됩니다.' }, 422); }
                        this.sent++; this.polls = 0; return this.respond({ success: true, job_id: jid });
                    }
                }
                if (url.pathname.startsWith('/api/ai/jobs/')) {
                    const count = this.polls + 1;
                    // Shared-prefix suites complete immediately unless this driver explicitly installs a gate.
                    if (count >= 3 && this.holdStreamCompletion) await this.holdStreamCompletion;
                    this.polls = count;
                    const header = '| ' + Array.from({ length: 10 }, (_, index) => `긴 머리글 ${index}`).join(' | ') + ' |\n';
                    const separator = '| ' + Array(10).fill('---').join(' | ') + ' |\n';
                    const row = '| ' + Array(10).fill('장비 정보').join(' | ') + ' |\n';
                    const content = count === 2 ? header + separator + row + '| 장' : count === 3 ? '비 | 확인 |\n' : '';
                    return this.respond({ success: true, state: count >= 3 ? 'done' : 'running', message_id: 102, generation: 1, r: count >= 2 ? 20 : 10, c: count >= 3 ? 1000 : count === 2 ? 800 : 0, reasoning_length: count >= 2 ? 20 : 10, content_length: count >= 3 ? 1000 : count === 2 ? 800 : 0,
                        reasoning: count === 1 ? '조회 결과를 검토합니다.' : count === 2 ? '\n표를 작성합니다.' : '', content, answer_started: count >= 2, proposals: [], source: { provider_name: '260Strata', model_label: 'Qwen3.8 Flash Next', reasoning_effort: 'medium' } });
                }
                if (url.pathname.endsWith('/confirm')) return this.respond({ success: true, result: { message: '시험용 완료' } });
                if (url.pathname.endsWith('/csv/preview')) return this.respond({ success: true, count: 1, rows: [{ Name: 'CSV 시험', OptionId: 3, IsPublic: 0 }], errors: [], token: 'synthetic-csv-token' });
                if (url.pathname.endsWith('/csv/commit')) return this.respond({ success: true, count: 1 });
                if (/\/equipment\/\d+\/files$/.test(url.pathname)) return this.respond({ success: true });
                return this.respond({ success: false, message: '예상하지 않은 시험 요청입니다.' }, 422);
            },
        };
        window.__uiFixtureServer = server;
    }
    const server = peer ? window.parent.__uiFixtureServer : window.__uiFixtureServer;
    window.fetch = (path, options = {}) => new URL(path, location.origin).pathname.startsWith('/api/ai/') ? server.fetch(path, options) : nativeFetch(path, options);
    if (peer) return;

    document.addEventListener('DOMContentLoaded', async () => {
        const checks = [], layout = {}, report = document.createElement('pre'); report.id = 'browser-test-result'; report.hidden = true; document.body.append(report);
        const $ = id => document.getElementById(id);
        const wait = async (test, label = 'condition') => { for (let i = 0; i < 1200; i++) { if (test()) return; await sleep(10); } throw new Error(label + ' timed out'); };
        const assert = (value, label) => { if (!value) throw new Error(label); checks.push(label); };
        let releaseStreamCompletion = null;
        const releaseCompletion = () => {
            server.holdStreamCompletion = false;
            const release = releaseStreamCompletion; releaseStreamCompletion = null;
            release?.();
        };
        const posts = action => server.requests.filter(entry => entry.method === 'POST' && entry.path.endsWith('/' + action));
        const modelReads = () => server.requests.filter(entry => entry.path === '/api/ai/models').length;
        const round = value => Math.round(value * 1000) / 1000;
        const rect = element => {
            const box = element.getBoundingClientRect();
            return Object.fromEntries(['left', 'top', 'right', 'bottom', 'width', 'height'].map(key => [key, round(box[key])]));
        };
        const style = element => {
            const computed = getComputedStyle(element);
            return Object.fromEntries(['display', 'height', 'minHeight', 'width', 'fontSize', 'fontWeight', 'lineHeight', 'boxSizing', 'padding', 'borderWidth', 'whiteSpace', 'overflow', 'textOverflow'].map(key => [key, computed[key]]));
        };
        /** [Role] Records comparable real-DOM geometry before scenarios change reader/model state.
         * [Dependencies] The current viewport, loaded fonts and actual candidate controls; W0=136px was measured from the fixed original candidate.
         * [Impact] Returned metrics distinguish hidden header/status height from gains caused by a different conversation, viewport or selected model.
         */
        const measure = name => {
            const root = $('equipment-ai'), header = root.querySelector('.ai-header'), row = root.querySelector('.ai-composer-actions');
            return layout[name] = {
                viewport: { width: innerWidth, height: innerHeight, devicePixelRatio }, theme,
                title: $('ai-title').textContent, selectedModel: $('ai-model').value, selectedModelText: $('ai-model').selectedOptions[0]?.textContent || '', selectedLevel: $('ai-level').value,
                measuredModelCap: 136, cssModelCap: getComputedStyle(root).getPropertyValue('--ai-model-max-width').trim(),
                root: rect(root), header: rect(header), titleRect: rect($('ai-title')), modelRow: rect(row), scroll: rect($('ai-scroll')), composer: rect($('ai-form')), status: rect($('ai-model-status')),
                headerStyle: style(header), titleStyle: style($('ai-title')),
                controls: Object.fromEntries(['ai-model', 'ai-model-refresh', 'ai-level', 'ai-send'].map(id => [id, { rect: rect($(id)), style: style($(id)), disabled: $(id).disabled }])),
                pageScrollWidth: document.documentElement.scrollWidth,
            };
        };
        /** [Role] Checks compact-layout requirements against pixels and accessible DOM relationships.
         * [Dependencies] Stable control IDs, separate reasoning support and the shared <=760px header/sidebar breakpoint.
         * [Impact] Measures expanded model controls below reasoning; default-collapsed layout is checked separately and native keyboard coverage is not claimed.
         */
        const compact = name => {
            const metrics = measure(name), form = $('ai-form'), root = $('equipment-ai'), header = root.querySelector('.ai-header');
            const ids = ['ai-model', 'ai-model-refresh', 'ai-level', 'ai-send'];
            assert(ids.every(id => form.contains($(id))) && $('ai-model-settings').open && Boolean($('ai-level').compareDocumentPosition($('ai-model-settings')) & Node.DOCUMENT_POSITION_FOLLOWING) && Boolean($('ai-model-settings').compareDocumentPosition($('ai-reasoning-support')) & Node.DOCUMENT_POSITION_FOLLOWING), name + '-composer-reasoning-model-disclosure-support-order');
            assert(root.querySelector('label[for="ai-model"]').textContent.trim() === 'AI 모델' && $('ai-model-refresh').type === 'button', name + '-model-label-and-refresh-button-type');
            assert(!document.getElementById('ai-model-caption') && !header.querySelector('.ai-model-dot,.ai-header-note') && !header.textContent.includes('내 장비, 더 간편하게'), name + '-duplicate-header-content-removed');
            assert(!root.querySelector('.ai-workspace > .ai-model-control') && root.querySelector('.ai-bottom').contains($('ai-model-status')), name + '-no-upper-model-toolbar');
            assert(metrics.controls['ai-model'].rect.width <= 136.5 && metrics.controls['ai-model'].rect.width > 20, name + '-model-width-within-measured-136px-cap');
            const peers = ids.slice(0, 3).map(id => metrics.controls[id]);
            assert(peers.every(control => Math.abs(control.rect.height - peers[0].rect.height) < 0.5) && peers.every(control => control.style.fontSize === peers[0].style.fontSize && control.style.lineHeight === peers[0].style.lineHeight && control.style.fontWeight === peers[0].style.fontWeight && control.style.boxSizing === peers[0].style.boxSizing), name + '-shared-control-height-font-and-border-box');
            assert(peers[0].rect.height >= (innerWidth <= 760 ? 44 : 36) - 0.5 && peers[0].style.fontSize === '12px', name + '-readable-control-and-mobile-touch-size');
            assert($('ai-model-status').hidden && !$('ai-model-status').textContent.trim() && metrics.status.height === 0, name + '-normal-status-has-no-text-or-height');
            assert($('ai-model-status').getAttribute('role') === 'status' && ['ai-model', 'ai-level'].every(id => ($(id).getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean).every(reference => Boolean($(reference)))), name + '-status-and-help-idrefs-valid');
            if (innerWidth <= 760) {
                const titleStyle = metrics.titleStyle, button = rect($('ai-menu-toggle'));
                assert(metrics.header.height > 0 && button.width > 0 && $('ai-title').clientHeight <= parseFloat(titleStyle.fontSize) * 1.8, name + '-mobile-title-is-one-line');
                assert(titleStyle.whiteSpace === 'nowrap' && titleStyle.overflow === 'hidden' && titleStyle.textOverflow === 'ellipsis' && button.right <= metrics.titleRect.left + 1 && Math.abs((button.top + button.height / 2) - (metrics.titleRect.top + metrics.titleRect.height / 2)) <= 2, name + '-mobile-title-and-list-share-one-row');
                assert(getComputedStyle($('ai-sidebar')).display === 'none', name + '-mobile-sidebar-initially-collapsed');
            } else {
                assert(metrics.header.height === 0 && metrics.headerStyle.display === 'none' && getComputedStyle($('ai-sidebar')).display !== 'none', name + '-desktop-header-has-no-layout-height');
            }
            if (innerWidth >= 1440) assert(Math.abs(metrics.controls['ai-model'].rect.top-metrics.controls['ai-model-refresh'].rect.top)<=1 && metrics.controls['ai-model'].rect.top>metrics.controls['ai-level'].rect.bottom, name + '-desktop-model-row-is-below-reasoning');
            assert(metrics.root.right <= innerWidth + 1 && metrics.pageScrollWidth <= innerWidth + 1 && metrics.composer.right <= metrics.root.right + 1 && metrics.controls['ai-send'].rect.right <= metrics.composer.right + 1, name + '-compact-controls-do-not-overflow-page');
            return metrics;
        };
        const titleIsAccessible = expected => $('ai-title').textContent === expected && ($('ai-title').getAttribute('title') === expected || $('ai-title').getAttribute('aria-label') === expected);
        /** [Role] Measures the browser's own intrinsic select width for fixed labels using the candidate's computed typography and box chrome.
         * [Dependencies] The current Chromium native select, loaded fonts, computed appearance/padding/borders and exact option text; no assumed native-arrow allowance.
         * [Impact] A hidden reference outside the composer's flex constraints distinguishes platform sizing from label clipping or explanation-driven width inflation.
         */
        const nativeSelectReference = labels => {
            const reference = document.createElement('select'), computed = getComputedStyle($('ai-level'));
            reference.setAttribute('aria-hidden', 'true'); reference.tabIndex = -1; reference.disabled = $('ai-level').disabled;
            for (const key of ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'fontStretch', 'fontVariant', 'fontFeatureSettings', 'fontVariationSettings', 'letterSpacing', 'wordSpacing', 'textTransform', 'textIndent', 'lineHeight', 'writingMode', 'direction', 'boxSizing', 'appearance', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth', 'borderTopStyle', 'borderRightStyle', 'borderBottomStyle', 'borderLeftStyle']) reference.style[key] = computed[key];
            Object.assign(reference.style, { position: 'fixed', left: '-10000px', top: '0', visibility: 'hidden', display: 'inline-block', width: 'auto', minWidth: '0', maxWidth: 'none', height: computed.height, margin: '0', flex: 'none' });
            for (const text of labels) { const option = document.createElement('option'); option.textContent = text; reference.append(option); }
            document.body.append(reference);
            const measurement = { width: rect(reference).width, style: style(reference), labels };
            reference.remove(); return measurement;
        };
        /** [MINI-COMMENT: ASSISTANT.UI.REFLOW.EVIDENCE] [EN rev.1]
         * [Role] Crosses the actual media breakpoint and records each preserved field/node independently before asserting equality.
         * [Dependencies] The same-origin viewport iframe created by assistant_ui_browser_fixture.py and existing real message/control nodes.
         * [Impact] Unchanged transport cursors and before/after text distinguish unfinished display from unnecessary DOM replacement; original state/lock assertions remain unchanged and scrolling may clamp only to the resized table's available range.
         */
        const reflowAcrossBoundary = async (name, options = {}) => {
            const frame = window.frameElement, originalWidth = innerWidth, originalHeight = innerHeight;
            const targetWidth = options.width || (originalWidth <= 760 ? 761 : 760), targetHeight = options.height || originalHeight;
            const originalPageTop = scrollY, originalFlexShrink = frame?.style.flexShrink;
            const table = document.querySelector('.ai-answer table'), thought = document.querySelector('.ai-thought:not([hidden])'), region = document.querySelector('.ai-answer .ai-table-scroll');
            const before = { model: $('ai-model').value, level: $('ai-level').value, draft: $('ai-input').value, title: $('ai-title').textContent, thoughtOpen: thought?.open, left: region?.scrollLeft, models: modelReads(), turns: posts('turns').length, selections: posts('selection').length, inputDisabled: $('ai-input').disabled, modelDisabled: $('ai-model').disabled,
                sendDisabled: $('ai-send').disabled, tableConnected: table?.isConnected ?? null, thoughtConnected: thought?.isConnected ?? null, tableText: table?.textContent ?? null,
                answerText: table?.closest('.ai-answer')?.textContent ?? null, reasoningText: thought?.querySelector('.ai-thought-text')?.textContent ?? null, completedPolls: server.polls, completionHeld: Boolean(server.holdStreamCompletion), sampledAt: performance.now() };
            assert(Boolean(frame), name + '-uses-real-child-viewport');
            frame.style.flexShrink = '0';
            frame.style.width = targetWidth + 'px';
            frame.style.height = targetHeight + 'px';
            await wait(() => innerWidth === targetWidth && innerHeight === targetHeight, name + ' viewport transition');
            await sleep(20);
            const changed = measure(name);
            changed.emulation = options.height ? 'reduced-height-css-viewport' : options.width ? '200-percent-css-layout-equivalent' : '760-761-responsive-boundary';
            const afterTable = document.querySelector('.ai-answer table'), afterThought = document.querySelector('.ai-thought:not([hidden])'), afterRegion = document.querySelector('.ai-answer .ai-table-scroll');
            const after = { model: $('ai-model').value, level: $('ai-level').value, draft: $('ai-input').value, title: $('ai-title').textContent, thoughtOpen: afterThought?.open,
                inputDisabled: $('ai-input').disabled, modelDisabled: $('ai-model').disabled, sendDisabled: $('ai-send').disabled, tableConnected: afterTable?.isConnected ?? null, thoughtConnected: afterThought?.isConnected ?? null,
                tableText: afterTable?.textContent ?? null, answerText: afterTable?.closest('.ai-answer')?.textContent ?? null, reasoningText: afterThought?.querySelector('.ai-thought-text')?.textContent ?? null,
                completedPolls: server.polls, completionHeld: Boolean(server.holdStreamCompletion), sampledAt: performance.now() };
            const preserved = { model: after.model === before.model, level: after.level === before.level, draft: after.draft === before.draft,
                tableNode: afterTable === table, thoughtNode: afterThought === thought, thoughtOpen: thought?.open === before.thoughtOpen,
                inputDisabled: after.inputDisabled === before.inputDisabled, modelDisabled: after.modelDisabled === before.modelDisabled };
            changed.preservation = { before, after, identities: { table: afterTable === table, thought: afterThought === thought, tableRegion: afterRegion === region,
                capturedTableStillConnected: table?.isConnected ?? null, capturedThoughtStillConnected: thought?.isConnected ?? null },
                unchangedData: { completedPolls: after.completedPolls === before.completedPolls, answerText: after.answerText === before.answerText, reasoningText: after.reasoningText === before.reasoningText },
                preserved, failed: Object.entries(preserved).filter(([,same]) => !same).map(([name]) => name) };
            assert((targetWidth <= 760 ? changed.header.height > 0 : changed.header.height === 0) && titleIsAccessible(before.title), name + '-title-follows-current-responsive-width');
            assert($('ai-model').value === before.model && $('ai-level').value === before.level && $('ai-input').value === before.draft && document.querySelector('.ai-answer table') === table && document.querySelector('.ai-thought:not([hidden])') === thought && thought?.open === before.thoughtOpen && $('ai-input').disabled === before.inputDisabled && $('ai-model').disabled === before.modelDisabled, name + '-resize-preserves-nodes-selection-draft-and-locks');
            if (region) assert(Math.abs(region.scrollLeft - Math.min(before.left, Math.max(0, region.scrollWidth - region.clientWidth))) <= 1, name + '-resize-keeps-available-table-scroll');
            assert(modelReads() === before.models && posts('turns').length === before.turns && posts('selection').length === before.selections, name + '-resize-does-not-refetch-models-or-save-settings');
            if (options.height) {
                $('ai-input').scrollIntoView({ block: 'center' });
                const input = rect($('ai-input'));
                assert(input.top >= -1 && input.bottom <= innerHeight + 1, name + '-input-reachable-by-scroll-in-reduced-height');
                $('ai-send').scrollIntoView({ block: 'center' });
                const send = rect($('ai-send'));
                assert(send.top >= -1 && send.bottom <= innerHeight + 1 && document.documentElement.scrollWidth <= innerWidth + 1, name + '-send-reachable-without-horizontal-page-overflow');
            }
            frame.style.width = originalWidth + 'px';
            frame.style.height = originalHeight + 'px';
            frame.style.flexShrink = originalFlexShrink;
            await wait(() => innerWidth === originalWidth && innerHeight === originalHeight, name + ' viewport restore');
            window.scrollTo(0, originalPageTop);
        };
        const dismiss = async () => { $('ai-dialog-confirm').click(); await wait(() => !$('ai-lifecycle-dialog').open && $('equipment-ai').getAttribute('aria-busy') === 'false', 'dialog dismiss'); };
        const result = async title => { await wait(() => $('ai-lifecycle-dialog').open && $('ai-dialog-title').textContent.includes(title) && $('ai-lifecycle-dialog').getAttribute('aria-busy') === 'false', title); };
        const move = async (action, title = '완료') => { $(action === 'trash' ? 'ai-trash-current' : action === 'restore' ? 'ai-restore-current' : 'ai-purge-current').click(); if (action !== 'restore') { await result('확인'); $('ai-dialog-confirm').click(); } await result(title); };
        try {
            await wait(() => $('ai-title').textContent.includes('표와 휴지통') && !$('ai-model').disabled, 'initial chat');
            await document.fonts.ready;
            assert(!$('ai-model-settings').open && !$('ai-model-settings').hasAttribute('open'), 'model-settings-default-collapsed');
            $('ai-model-settings').querySelector('summary').click();
            assert($('ai-model-settings').open, 'model-settings-native-summary-expands-controls');
            compact('initialNormal');
            assert(titleIsAccessible(server.conversations.get(cid).title), 'current-title-retains-complete-accessible-name');
            assert([...$('ai-level').options].map(option => option.textContent).join('|') === 'off|low|medium|high|xhigh|max', 'six-reasoning-option-labels-stay-short-and-stable');
            assert($('ai-level').querySelector('[value=high]').disabled && $('ai-level').querySelector('[value=max]').disabled && !$('ai-reasoning-support').hidden && $('ai-reasoning-reasons').textContent.includes('high') && $('ai-reasoning-reasons').textContent.includes('max') && $('ai-reasoning-reasons').textContent.includes('모델 미지원'), 'unsupported-reasoning-options-disabled-with-separate-reasons');
            assert(($('ai-level').getAttribute('aria-describedby') || '').split(/\s+/).some(id => id === 'ai-reasoning-support' || id === 'ai-reasoning-reasons') && $('ai-reasoning-support').querySelector('summary') && $('ai-level-help').textContent.trim(), 'reasoning-help-is-associated-and-expandable');
            assert($('ai-model').options[0].textContent === '260Strata / Qwen3.8 Flash Next', 'short-model-option-name');
            assert([...$('ai-model').options].every(option => !/ · (?:장비 업무|대화 전용|사용 불가)/.test(option.textContent)), 'capability-absent-from-options');
            assert($('ai-model').options[2].disabled && $('ai-unavailable-model-reasons').textContent.includes('비활성화'), 'unavailable-reason-separate-and-disabled');
            assert($('ai-level').value === 'medium' && $('ai-level').querySelector('[value=high]').disabled, 'reasoning-choice-preserved');
            assert($('ai-storage-notice').textContent.includes('32,000,000'), 'storage-budget-preserved');
            assert(!$('equipment-ai').querySelector('img'), 'all-model-and-title-html-stays-text');
            const stored = document.querySelector('.ai-answer table');
            assert(stored && stored.querySelectorAll('thead th').length === 3 && stored.querySelectorAll('tbody tr').length === 3, 'past-response-renders-semantic-table');
            assert(stored.querySelector('th:nth-child(2)').className === 'ai-align-right' && stored.querySelector('th:nth-child(3)').className === 'ai-align-center', 'table-alignment');
            assert(stored.querySelector('td').textContent === '노트북 | PC' && stored.querySelector('tr:nth-child(2) td:last-child').textContent === '', 'escaped-pipe-empty-and-missing-cells');
            assert(!stored.querySelector('img') && stored.querySelector('a').getAttribute('href') === '/my_equipment', 'table-xss-and-local-link');

            const sandbox = document.createElement('div'); sandbox.className = 'ai-answer'; $('ai-messages').append(sandbox);
            const markdown = window.module.exports.markdown;
            markdown(sandbox, '| A | B |\n| --- | --', { streaming: true }); assert(!sandbox.querySelector('table') && sandbox.textContent.includes('| --- | --'), 'incomplete-delimiter-remains-text');
            markdown(sandbox, '| A | B |\n| --- | --'); assert(sandbox.querySelectorAll('thead th').length === 2, 'completed-short-gfm-delimiter-is-valid');
            markdown(sandbox, '| A | B |\n| --- | --- |\n| 1 | 2 |\n| 未完', { streaming: true });
            assert(sandbox.querySelectorAll('tbody tr').length === 1 && sandbox.lastElementChild.textContent.includes('未完'), 'stream-incomplete-row-preserved');
            markdown(sandbox, '| A | B |\n| --- | --- |\n| 1 | 2 |\n| 未完 | 完了 |', { streaming: false });
            assert(sandbox.querySelectorAll('tbody tr').length === 2, 'stream-final-row-commits');
            markdown(sandbox, '~~~md\n| A | B |\n| --- | --- |\n| x | y |\n~~~\n```\n<script>text</script>');
            assert(!sandbox.querySelector('table') && sandbox.querySelectorAll('pre').length === 2 && !sandbox.querySelector('script'), 'fences-and-unclosed-fence-stay-code');
            markdown(sandbox, '| A | B |\n| --- |\n| x | y |'); assert(!sandbox.querySelector('table'), 'header-separator-count-must-match');
            markdown(sandbox, '[bad](javascript:alert(1))\n[bad](/outside)\n<script>unsafe()</script>'); assert(!sandbox.querySelector('script,a'), 'link-allowlist-preserved');
            const large = '| A | B |\n| --- | --- |\n' + Array.from({ length: 230 }, (_, index) => `| ${index} | 行 ${index} |`).join('\n');
            markdown(sandbox, large); assert(sandbox.querySelectorAll('tbody tr').length === 200 && sandbox.querySelector('.ai-table-raw pre').textContent === large, 'long-table-bounded-with-complete-original');
            const wide = '| ' + Array(41).fill('列').join(' | ') + ' |\n| ' + Array(41).fill('---').join(' | ') + ' |';
            markdown(sandbox, wide); assert(!sandbox.querySelector('table') && sandbox.querySelector('.ai-table-raw pre').textContent === wide, 'excess-columns-use-explicit-raw-view');
            const scrollTable = '| ' + Array(12).fill('긴 머리글').join(' | ') + ' |\n| ' + Array(12).fill('---').join(' | ') + ' |\n| ' + Array(12).fill('긴 셀 내용').join(' | ') + ' |';
            markdown(sandbox, scrollTable); const region = sandbox.querySelector('.ai-table-scroll'); region.scrollLeft = 75; const horizontal = region.scrollLeft;
            markdown(sandbox, scrollTable + '\n| 새 행 |'); assert(sandbox.querySelector('.ai-table-scroll').scrollLeft === horizontal, 'horizontal-scroll-preserved');
            assert(region.tabIndex === 0 && region.getAttribute('role') === 'region', 'table-keyboard-region');
            const selection = document.getSelection(), range = document.createRange(), selectedCell = sandbox.querySelector('td');
            range.selectNodeContents(selectedCell); selection.removeAllRanges(); selection.addRange(range);
            const selectedText = selection.toString(); markdown(sandbox, scrollTable + '\n| 추가 행 |');
            assert(selection.toString() === selectedText && sandbox.contains(selectedCell), 'active-text-selection-defers-dom-replacement');
            selection.removeAllRanges(); document.dispatchEvent(new Event('selectionchange'));
            await wait(() => sandbox.textContent.includes('추가 행'), 'selection release render'); sandbox.remove();
            assert($('equipment-ai').getBoundingClientRect().right <= innerWidth + 1 && document.documentElement.scrollWidth <= innerWidth + 1, 'wide-table-does-not-overflow-page');
            assert(getComputedStyle($('equipment-ai')).getPropertyValue('--ai-bg').trim() === (theme === 'dark' ? '#141c28' : '#fff'), 'existing-theme-variables-preserved');

            await sleep(50);
            let releaseList; server.holdList = new Promise(resolve => { releaseList = resolve; });
            const listReadsBefore = server.requests.filter(entry => entry.path === '/api/ai/conversations').length;
            const earlyTurns = posts('turns').length;
            $('ai-input').value = '목록 갱신 중에도 유지할 초안';
            document.querySelector(`#ai-conversations .ai-conversation[data-conversation-id="${cid}"]`).click();
            await wait(() => server.requests.filter(entry => entry.path === '/api/ai/conversations').length > listReadsBefore, 'held sidebar refresh begins');
            await wait(() => !$('ai-send').disabled && $('equipment-ai').getAttribute('aria-busy') === 'false', 'hydrated composer ready before sidebar response');
            const hydratedAnswer = document.querySelector('.ai-answer table');
            assert($('ai-input').value === '목록 갱신 중에도 유지할 초안' && hydratedAnswer, 'hydration-preserves-draft-while-sidebar-is-pending');
            server.rejectNextTurn = true; $('ai-form').requestSubmit();
            await wait(() => posts('turns').length === earlyTurns + 1 && !$('ai-send').disabled, 'submit reaches server while sidebar is pending');
            assert(server.sent === 0 && $('ai-input').value === '목록 갱신 중에도 유지할 초안', 'ready-submit-not-swallowed-by-sidebar-refresh');
            window.dispatchEvent(new Event('focus')); await sleep(25);
            assert(document.querySelector('.ai-answer table') === hydratedAnswer && $('ai-input').value === '목록 갱신 중에도 유지할 초안' && !$('ai-send').disabled, 'unchanged-focus-check-keeps-composer-draft-and-message-nodes');
            releaseList(); await sleep(50);

            await sleep(50);
            let releaseCursor; server.holdCursor = new Promise(resolve => { releaseCursor = resolve; });
            const capabilityReads = server.requests.filter(entry => entry.path === '/api/ai/capabilities').length;
            $('ai-more-conversations').click(); await wait(() => server.requests.some(entry => entry.path === '/api/ai/conversations' && entry.search.includes('cursor=active-next')), 'explicit older-page request');
            window.dispatchEvent(new Event('focus'));
            await wait(() => server.requests.filter(entry => entry.path === '/api/ai/capabilities').length > capabilityReads, 'background identity recheck');
            await sleep(25); releaseCursor(); await wait(() => $('ai-conversations').textContent.includes('이전 페이지'));
            await sleep(50);
            assert($('ai-conversations').querySelectorAll('.ai-conversation').length === 2, 'older-active-pages-reachable');
            assert($('ai-conversations').textContent.includes('이전 페이지'), 'focus-refresh-cannot-discard-inflight-older-page');
            $('ai-trash-tab').click(); await wait(() => $('ai-conversations').textContent.includes('미리 보관한'));
            assert(server.requests.filter(entry => entry.path === '/api/ai/conversations' && entry.search.includes('view=trash')).every(entry => !entry.search.includes('active-next')), 'trash-has-independent-cursor');
            document.querySelector('#ai-conversations .ai-conversation').click(); await wait(() => $('ai-title').textContent.includes('미리 보관한') && $('equipment-ai').getAttribute('aria-busy') === 'false');
            assert($('ai-input').disabled && $('ai-model').disabled && $('ai-level').disabled && $('ai-file-controls').disabled, 'trash-input-model-reasoning-files-read-only');
            assert(titleIsAccessible(server.conversations.get(trashCid).title), 'trash-title-retains-current-accessible-name');
            await reflowAcrossBoundary('readOnlyReflow');
            assert($('ai-lifecycle-text').textContent.includes('30日') || $('ai-lifecycle-text').textContent.includes('30일'), 'trash-retention-and-expiry-visible');
            const turnsBefore = posts('turns').length; $('ai-input').value = '보내면 안 됨'; $('ai-form').dispatchEvent(new Event('submit', { cancelable: true }));
            assert(posts('turns').length === turnsBefore && !document.querySelector('.ai-confirm'), 'trash-cannot-submit-turn-or-proposal');
            $('ai-purge-current').click(); await result('확인');
            assert($('ai-dialog-message').textContent.includes('미리 보관한') && $('ai-dialog-detail').textContent.includes('복구할 수 없') && document.activeElement.id === 'ai-dialog-cancel', 'purge-modal-names-target-and-focuses-cancel');
            $('ai-lifecycle-dialog').dispatchEvent(new Event('close'));
            assert($('ai-lifecycle-dialog').open && posts('purge').length === 0, 'old-close-notification-cannot-resolve-current-dialog');
            $('ai-lifecycle-dialog').dispatchEvent(new Event('cancel', { cancelable: true })); await wait(() => !$('ai-lifecycle-dialog').open);
            assert(posts('purge').length === 0, 'escape-cancel-does-not-purge');
            await move('restore'); assert($('ai-dialog-detail').textContent.includes('다시 실행되지'), 'restore-explains-no-replay'); await dismiss();
            assert(document.activeElement.id === 'ai-trash-current' && !document.activeElement.disabled, 'result-dialog-restores-visible-enabled-focus');
            assert(!server.conversations.get(trashCid).is_deleted && posts('turns').length === turnsBefore, 'restore-does-not-replay-work');
            assert(titleIsAccessible(server.conversations.get(trashCid).title), 'restored-title-retains-current-accessible-name');

            $('ai-active-tab').click(); await wait(() => document.querySelector(`#ai-conversations .ai-conversation[data-conversation-id="${cid}"]`));
            document.querySelector(`#ai-conversations .ai-conversation[data-conversation-id="${cid}"]`).click(); await wait(() => $('ai-title').textContent.includes('표와 휴지통') && !$('ai-model').disabled);
            await move('trash'); const deletedAt = server.conversations.get(cid).deleted_at;
            assert(server.conversations.get(cid).purge_after - deletedAt === 2592000, 'server-thirty-day-timestamp-used'); await dismiss();
            assert($('ai-input').disabled && $('ai-trash-tab').getAttribute('aria-pressed') === 'true' && !document.querySelector('.ai-confirm'), 'selected-move-switches-to-read-only-trash');
            await move('restore'); await dismiss();
            assert(!$('ai-input').disabled && !document.querySelector('.ai-confirm') && posts('turns').length === turnsBefore, 'restored-cancelled-proposals-remain-cancelled');
            server.mode = 'ack-refresh-failure'; const writesBefore = posts('trash').length;
            await move('trash'); assert($('ai-dialog-title').textContent.includes('완료') && $('ai-dialog-detail').textContent.includes('새로고침'), 'ack-success-separated-from-get-failure'); await dismiss();
            assert(posts('trash').length === writesBefore + 1, 'ack-get-failure-never-resubmits-post');
            server.failReads = 0; await move('restore'); await dismiss();

            server.mode = 'lost-after-apply'; const unknownPosts = posts('trash').length;
            await move('trash', '확인 필요'); await dismiss();
            assert(!$('ai-lifecycle-reconcile').hidden && $('ai-input').disabled && posts('trash').length === unknownPosts + 1, 'lost-ack-blocks-and-never-autoretries');
            $('ai-lifecycle-reconcile').click(); await result('현재 상태'); await dismiss();
            assert(posts('trash').length === unknownPosts + 1 && $('ai-lifecycle-reconcile').hidden, 'lost-ack-reconciles-with-get-only');
            await move('restore'); await dismiss();
            server.mode = 'lost-before-apply'; const beforeUnknown = posts('trash').length;
            await move('trash', '확인 필요'); await dismiss();
            $('ai-lifecycle-reconcile').click(); await result('확인');
            assert(posts('trash').length === beforeUnknown + 1 && $('ai-dialog-detail').textContent.includes('아직 처리되지 않았다면'), 'unknown-unchanged-requires-explicit-resend');
            $('ai-dialog-confirm').click(); await result('완료'); await dismiss();
            const unknownRequests = posts('trash').slice(-2);
            assert(unknownRequests[0].data.operation_id === unknownRequests[1].data.operation_id && /^[a-f0-9]{32}$/.test(unknownRequests[1].data.operation_id), 'explicit-retry-reuses-operation-id');
            await move('restore'); await dismiss();

            server.mode = 'lost-before-apply'; await move('trash', '확인 필요'); await dismiss();
            const delayedOperation = clone(posts('trash').at(-1).data);
            $('ai-lifecycle-reconcile').click(); await result('확인');
            await server.fetch(`/api/ai/conversations/${cid}/trash`, { method: 'POST', headers: { 'X-CSRFToken': 'fixture-csrf' }, body: JSON.stringify(delayedOperation) });
            await server.fetch(`/api/ai/conversations/${cid}/restore`, { method: 'POST', headers: { 'X-CSRFToken': 'fixture-csrf' }, body: JSON.stringify({ lifecycle_revision: server.conversations.get(cid).lifecycle_revision, operation_id: crypto.randomUUID().replaceAll('-', '') }) });
            const currentRevision = server.conversations.get(cid).lifecycle_revision;
            $('ai-dialog-confirm').click(); await result('기처리 요청');
            assert($('ai-dialog-detail').textContent.includes('현재 정상 대화') && $('ai-dialog-message').textContent.includes('다시 바꾸지'), 'old-operation-receipt-explains-current-state'); await dismiss();
            assert(!server.conversations.get(cid).is_deleted && server.conversations.get(cid).lifecycle_revision === currentRevision && !$('ai-input').disabled && $('ai-active-tab').getAttribute('aria-pressed') === 'true', 'replayed-trash-never-retrashes-restored-chat');

            const staleControl = document.querySelector(`#ai-conversations [data-lifecycle-action="trash"][data-conversation-id="${cid}"]`);
            const frame = document.createElement('iframe'); frame.title = '독립 대화 탭'; frame.style.display = 'none'; frame.src = '/?peer=1&theme=' + theme; document.body.append(frame);
            await wait(() => frame.contentDocument?.getElementById('ai-title')?.textContent.includes('표와 휴지통') && !frame.contentDocument.getElementById('ai-model').disabled, 'second-tab-start');
            const peerDoc = frame.contentDocument;
            peerDoc.getElementById('ai-trash-current').click(); await wait(() => peerDoc.getElementById('ai-lifecycle-dialog').open); peerDoc.getElementById('ai-dialog-confirm').click();
            await wait(() => peerDoc.getElementById('ai-dialog-title').textContent.includes('완료'));
            peerDoc.getElementById('ai-dialog-confirm').click();
            await wait(() => $('ai-input').disabled && $('ai-lifecycle-text').textContent.includes('읽기 전용'), 'cross-tab-trash-revalidation');
            await wait(() => $('equipment-ai').getAttribute('aria-busy') === 'false', 'cross-tab-read-complete');
            assert($('ai-model').disabled && !document.querySelector('.ai-confirm'), 'second-tab-cannot-keep-stale-write-controls');
            await move('restore'); await dismiss();
            const revision = server.conversations.get(cid).lifecycle_revision;
            /* [MINI-COMMENT: ASSISTANT.UI.STALE.REVISION.PROBE] [EN rev.1]
             * [Role] Deliberately submits metadata retained by an obsolete client after a cross-tab trash/restore.
             * [Dependencies] open() disables old controls before list rerender detaches them; native click() ignores disabled buttons.
             * [Impact] Re-enabling this detached fixture-only node reaches the stale-revision server guard without changing live UI locks or weakening rejection checks.
             */
            layout.staleControl = { connected: staleControl.isConnected, disabledBeforeProbe: staleControl.disabled, currentRevision: revision };
            assert(!staleControl.isConnected, 'stale-revision-probe-uses-detached-fixture-control');
            const stalePosts = posts('trash').length;
            staleControl.disabled = false;
            staleControl.click(); await result('확인'); $('ai-dialog-confirm').click(); await result('처리하지 못'); await dismiss();
            assert(posts('trash').length === stalePosts + 1 && posts('trash').at(-1).data.lifecycle_revision < revision && $('ai-dialog-message').textContent.includes('다른 탭에서'), 'stale-revision-request-reaches-server-and-is-rejected');
            assert(!server.conversations.get(cid).is_deleted && server.conversations.get(cid).lifecycle_revision === revision, 'stale-tab-revision-cannot-retrash-restored-chat');
            frame.contentWindow.dispatchEvent(new Event('pagehide')); frame.remove();

            server.mode = 'reject'; await move('trash', '처리하지 못'); await dismiss(); assert(!server.conversations.get(cid).is_deleted, 'known-failure-does-not-claim-success');
            const duplicates = posts('trash').length; $('ai-trash-current').click(); await result('확인'); $('ai-dialog-confirm').click(); $('ai-dialog-confirm').click(); $('ai-trash-current').click();
            await result('완료'); await dismiss(); assert(posts('trash').length === duplicates + 1, 'duplicate-clicks-submit-once');
            await move('restore'); await dismiss();

            /* [MINI-COMMENT: ASSISTANT.UI.STREAM.COMPLETION.GATE] [EN rev.2]
             * [Role] Keeps this synthetic request running until its live feedback, draft, focus and resize checks finish.
             * [Dependencies] The opt-in third-response promise above and the second chunk's completed body row plus exact trailing incomplete row.
             * [Impact] Faster production polling cannot complete the fixture before live-state assertions; releasing the gate still exercises the original final delta, scroll retention and terminal controls.
             */
            server.holdStreamCompletion = new Promise(resolve => { releaseStreamCompletion = resolve; });
            $('ai-input').value = '안전한 표 스트리밍'; $('ai-form').requestSubmit();
            await wait(() => document.querySelector('.ai-thought:not([hidden])')?.open, 'live-thought-opens');
            const thought = document.querySelector('.ai-thought:not([hidden])');
            await wait(() => document.querySelector('.ai-answer table') && !thought.open, 'answer-auto-collapses');
            await wait(() => {
                const answer = document.querySelector('.ai-message[data-role="assistant"] .ai-answer');
                return answer?.querySelectorAll('tbody tr').length === 1 && answer.lastElementChild?.textContent === '| 장';
            }, 'running-chunk-visible-before-live-geometry-checks');
            thought.querySelector('summary').click(); const liveRegion = document.querySelector('.ai-answer .ai-table-scroll'); liveRegion.scrollLeft = 80; const liveLeft = liveRegion.scrollLeft;
            $('ai-input').value = '진행 중 보존할 다음 초안';
            assert(!$('ai-model-status').hidden && $('ai-model-status').textContent.includes('다음 요청') && $('ai-model-status').textContent.includes('기존 모델'), 'active-request-feedback-remains-visible-near-composer');
            await reflowAcrossBoundary('liveStreamReflow');
            if (innerWidth === 1440) await reflowAcrossBoundary('liveStream200PercentEquivalent', { width: 720 });
            await reflowAcrossBoundary('liveStreamReducedHeight', { width: innerWidth, height: 500 });
            window.dispatchEvent(new Event('focus')); await sleep(25);
            assert(document.querySelector('.ai-thought:not([hidden])') === thought && thought.open && $('ai-input').value === '진행 중 보존할 다음 초안' && $('ai-send').disabled, 'unchanged-focus-check-keeps-live-stream-job-and-draft');
            layout.streamCompletionGate = { heldAtPoll: server.polls, heldDuringLiveChecks: Boolean(server.holdStreamCompletion), feedback: $('ai-model-status').textContent, sendDisabledBeforeRelease: $('ai-send').disabled };
            assert(server.polls === 2 && Boolean(server.holdStreamCompletion), 'synthetic-completion-waits-for-explicit-live-check-release');
            releaseCompletion();
            await wait(() => server.polls >= 3 && !$('ai-send').disabled, 'stream-done');
            layout.streamCompletionGate.releasedAtPoll = server.polls;
            assert(thought.open && thought.textContent.includes('표를 작성'), 'stream-keeps-reopened-thoughts');
            assert(document.querySelector('.ai-answer .ai-table-scroll').scrollLeft === liveLeft && document.querySelectorAll('.ai-answer tbody tr').length === 2, 'stream-keeps-table-scroll-and-final-row');
            assert(document.querySelector('.ai-source').textContent.includes('260Strata'), 'accepted-answer-source-preserved');
            $('ai-model').value = 'f'.repeat(32); $('ai-model').dispatchEvent(new Event('change'));
            await wait(() => !$('ai-model').disabled && $('ai-model-status').textContent.includes('대화 전용'));
            assert($('ai-level').disabled && document.querySelector('.ai-source').textContent.includes('260Strata'), 'chat-only-status-and-frozen-source-preserved');

            assert(!document.querySelector('.ai-footnote') && !document.querySelector('.ai-bottom .ai-file-tools') && !$('ai-file-dialog').open, 'footer-space-released-until-user-requests-file-work');
            const fileRequest = document.createElement('p'); module.exports.markdown(fileRequest,'[CSV 가져오기 열기](/assistant?panel=csv-import)'); $('ai-messages').append(fileRequest); fileRequest.querySelector('a').click();
            assert($('ai-file-dialog').open && $('ai-file-title').textContent === 'CSV 가져오기', 'conversation-link-opens-existing-csv-flow-in-dialog');
            const data = new DataTransfer(); data.items.add(new File(['Name,OptionId\nCSV fixture,3'], 'fixture.csv', { type: 'text/csv' }));
            $('ai-csv-file').files = data.files; $('ai-csv-form').requestSubmit(); await wait(() => !$('ai-csv-preview').hidden);
            assert($('ai-csv-preview').textContent.includes('CSV 시험') && $('ai-csv-preview').textContent.includes('비공개'), 'existing-csv-preview-flow-preserved');
            $('ai-file-close').click();
            assert(!$('ai-file-dialog').open && document.activeElement === fileRequest.querySelector('a'), 'file-popup-close-restores-trigger-without-replay');
            const csrfWrites = server.requests.filter(entry => entry.method === 'POST');
            assert(csrfWrites.every(entry => entry.headers['X-CSRFToken'] === 'fixture-csrf'), 'all-mutations-retain-csrf');
            await move('trash'); await dismiss();
            server.mode = 'lost-after-apply'; const purgeCount = posts('purge').length; await move('purge', '확인 필요'); await dismiss();
            assert(!server.conversations.has(cid) && !$('ai-lifecycle-reconcile').hidden, 'purge-lost-ack-remains-unknown');
            $('ai-lifecycle-reconcile').click(); await result('확인'); $('ai-dialog-confirm').click(); await result('기처리 요청'); await dismiss();
            const purgeRequests = posts('purge').slice(-2);
            assert(posts('purge').length === purgeCount + 2 && purgeRequests[0].data.operation_id === purgeRequests[1].data.operation_id && $('ai-lifecycle-reconcile').hidden, 'purge-explicit-retry-confirms-idempotent-receipt');
            const expires = server.conversations.get(trashCid); expires.is_deleted = 1; expires.deleted_at = Date.now() / 1000; expires.purge_after = expires.deleted_at + 2592000; expires.lifecycle_revision++;
            $('ai-trash-tab').click(); await wait(() => document.querySelector(`#ai-conversations .ai-conversation[data-conversation-id="${trashCid}"]`));
            document.querySelector(`#ai-conversations .ai-conversation[data-conversation-id="${trashCid}"]`).click(); await wait(() => $('ai-title').textContent.includes('미리 보관한') && $('equipment-ai').getAttribute('aria-busy') === 'false');
            server.mode = 'expire-on-restore'; await move('restore', '처리하지 못'); await dismiss();
            assert(server.conversations.get(trashCid).is_deleted && !$('ai-title').textContent.includes('미리 보관한'), 'server-expiry-wins-over-stale-restore-ui');
            assert(!$('ai-dialog-confirm').contains(document.querySelector('img')) && !window.__assistantPwned, 'all-xss-fixtures-remain-inert');
            $('ai-active-tab').click(); await wait(() => document.querySelector(`#ai-conversations .ai-conversation[data-conversation-id="${oldCid}"]`));
            document.querySelector(`#ai-conversations .ai-conversation[data-conversation-id="${oldCid}"]`).click(); await wait(() => $('ai-title').textContent.includes('이전 페이지') && document.querySelector('.ai-answer table') && $('equipment-ai').getAttribute('aria-busy') === 'false');
            assert(document.querySelector('.ai-answer thead th') && !$('ai-input').disabled, 'final-screenshot-uses-real-stored-table-view');
            if (innerWidth <= 760) {
                $('ai-menu-toggle').focus(); $('ai-menu-toggle').click();
                assert($('ai-sidebar').classList.contains('is-open') && $('ai-menu-toggle').getAttribute('aria-expanded') === 'true' && document.activeElement === $('ai-menu-toggle'), 'mobile-sidebar-keyboard-button');
                assert(Math.abs(rect($('ai-sidebar')).top - rect(document.querySelector('.ai-header')).bottom) <= 1 && rect($('ai-new')).top >= rect(document.querySelector('.ai-header')).bottom, 'mobile-drawer-starts-after-current-header-height');
                $('ai-menu-toggle').click();
            }
            assert($('equipment-ai').getBoundingClientRect().right <= innerWidth + 1 && document.documentElement.scrollWidth <= innerWidth + 1, 'final-responsive-no-page-overflow');

            const currentOld = () => document.querySelector(`#ai-conversations .ai-conversation[data-conversation-id="${oldCid}"]`);
            const originalTitle = server.conversations.get(oldCid).title;
            const longTitle = '긴 세션 제목과 현재 대화 확인 '.repeat(12) + '<img src=x onerror="window.__assistantPwned=1">';
            server.conversations.get(oldCid).title = longTitle;
            currentOld().click(); await wait(() => titleIsAccessible(longTitle) && !$('ai-model').disabled, 'long current title');
            const longMetrics = measure('longTitle');
            assert(!document.querySelector('#ai-title img') && !window.__assistantPwned, 'long-title-remains-inert-complete-text');
            if (innerWidth <= 760) assert($('ai-title').scrollWidth > $('ai-title').clientWidth && longMetrics.titleStyle.textOverflow === 'ellipsis' && longMetrics.titleStyle.whiteSpace === 'nowrap', 'long-current-title-visibly-ellipsizes-on-mobile');
            else assert(longMetrics.header.height === 0, 'long-title-cannot-reintroduce-desktop-header-height');
            server.conversations.get(oldCid).title = originalTitle;
            currentOld().click(); await wait(() => titleIsAccessible(originalTitle) && !$('ai-model').disabled, 'current title restore');

            const normalLevelWidth = rect($('ai-level')).width, originalModelLabel = server.models[0].label, originalHighReason = server.models[0].level_reasons.high;
            const longModelLabel = 'Qwen3.8 Flash Next 긴 모델 이름 '.repeat(10);
            server.models[0].label = longModelLabel;
            server.models[0].level_reasons.high = '관리자가 허용하지 않은 추론 단계의 긴 설명 '.repeat(20);
            let readsBefore = modelReads(); $('ai-model-refresh').click();
            await wait(() => modelReads() > readsBefore && $('ai-model-refresh').getAttribute('aria-busy') === 'false' && $('ai-model').selectedOptions[0]?.textContent === '260Strata / ' + longModelLabel, 'long model inventory refresh');
            assert(rect($('ai-model')).width <= 136.5 && Math.abs(rect($('ai-level')).width - normalLevelWidth) < 0.5, 'long-model-option-keeps-full-name-without-expanding-either-select');
            measure('longModel');
            server.models[0].label = originalModelLabel;
            server.models[0].level_reasons.high = originalHighReason;
            readsBefore = modelReads(); $('ai-model-refresh').click();
            await wait(() => modelReads() > readsBefore && $('ai-model-refresh').getAttribute('aria-busy') === 'false' && $('ai-model').selectedOptions[0]?.textContent === '260Strata / ' + originalModelLabel, 'normal model label restore');

            const stableTable = document.querySelector('.ai-answer table'), refreshGeometry = measure('beforeRefresh'), refreshTurns = posts('turns').length;
            $('ai-input').value = '모델 목록과 오류 뒤에도 보존할 초안';
            let releaseModels; server.holdModels = new Promise(resolve => { releaseModels = resolve; });
            readsBefore = modelReads(); $('ai-model-refresh').click();
            await wait(() => modelReads() > readsBefore && $('ai-model-refresh').disabled && $('ai-model-refresh').getAttribute('aria-busy') === 'true', 'held model list refresh');
            const pendingGeometry = measure('loadingRefresh');
            assert($('ai-model-refresh').textContent.trim() === '목록 새로고침' && !$('ai-model-status').hidden && $('ai-model-status').textContent.includes('목록'), 'refresh-loading-has-stable-button-label-and-visible-status');
            assert(Math.abs(pendingGeometry.controls['ai-model-refresh'].rect.width - refreshGeometry.controls['ai-model-refresh'].rect.width) < 0.5 && Math.abs(pendingGeometry.controls['ai-model-refresh'].rect.height - refreshGeometry.controls['ai-model-refresh'].rect.height) < 0.5, 'refresh-loading-keeps-button-dimensions');
            $('ai-model-refresh').click(); await sleep(20);
            assert(modelReads() === readsBefore + 1 && posts('turns').length === refreshTurns, 'refresh-duplicate-click-is-one-read-and-no-form-submit');
            releaseModels(); await wait(() => !$('ai-model-refresh').disabled && $('ai-model-refresh').getAttribute('aria-busy') === 'false', 'model refresh released');
            assert($('ai-model-status').hidden && !$('ai-model-status').textContent.trim() && $('ai-input').value === '모델 목록과 오류 뒤에도 보존할 초안' && document.querySelector('.ai-answer table') === stableTable && $('ai-model').value === modelId && $('ai-level').value === 'medium', 'refresh-success-preserves-selection-draft-reader-and-empty-normal-status');

            server.failModelReads = 1; readsBefore = modelReads(); $('ai-model-refresh').click();
            await wait(() => modelReads() > readsBefore && !$('ai-model-refresh').disabled && $('ai-notice').textContent.includes('시험용 모델 목록 오류'), 'model refresh failure');
            assert(!$('ai-notice').hidden && $('ai-notice').getAttribute('role') === 'status' && !$('ai-model-status').hidden && $('ai-model-status').textContent.includes('시험용 모델 목록 오류: 현재 선택을 유지합니다.') && $('ai-model').value === modelId && !$('ai-model').disabled && !$('ai-send').disabled && $('ai-input').value === '모델 목록과 오류 뒤에도 보존할 초안' && document.querySelector('.ai-answer table') === stableTable && posts('turns').length === refreshTurns, 'refresh-error-is-visible-near-composer-and-retains-working-selection-draft-and-table');
            measure('failedRefresh');

            server.omitSelectedModel = true; readsBefore = modelReads(); $('ai-model-refresh').click();
            await wait(() => modelReads() > readsBefore && $('ai-model-refresh').getAttribute('aria-busy') === 'false' && $('ai-model').selectedOptions[0]?.disabled, 'selected model missing');
            assert($('ai-notice').hidden && !$('ai-notice').textContent.trim(), 'successful-model-retry-clears-only-its-recovered-inventory-global-notice');
            assert($('ai-model').value === modelId && $('ai-send').disabled && !$('ai-model-status').hidden && $('ai-model-status').textContent.includes('복원할 수 없'), 'missing-saved-model-remains-selected-disabled-and-explained');
            assert(rect($('ai-model')).width <= 136.5 && document.documentElement.scrollWidth <= innerWidth + 1, 'missing-model-feedback-keeps-compact-page-width');
            measure('missingModel');
            server.omitSelectedModel = false; readsBefore = modelReads(); $('ai-model-refresh').click();
            await wait(() => modelReads() > readsBefore && $('ai-model-refresh').getAttribute('aria-busy') === 'false' && !$('ai-send').disabled && $('ai-level').value === 'medium', 'saved model returns');
            assert($('ai-model-status').hidden && !$('ai-model-status').textContent.trim(), 'successful-inventory-recovery-clears-conditional-model-error-height');

            $('ai-model').value = 'f'.repeat(32); $('ai-model').dispatchEvent(new Event('change'));
            await wait(() => !$('ai-model').disabled && $('ai-level').value === 'default' && $('ai-model-status').textContent.includes('대화 전용'), 'default reasoning exception');
            const defaultStyle = getComputedStyle($('ai-level')), context = document.createElement('canvas').getContext('2d');
            context.font = `${defaultStyle.fontWeight} ${defaultStyle.fontSize} ${defaultStyle.fontFamily}`;
            measure('chatOnlyDefault');
            assert($('ai-level').selectedOptions[0].textContent === '모델 기본값' && $('ai-level').disabled && [...$('ai-level').options].filter(option => option.value !== 'default').map(option => option.textContent).join('|') === 'off|low|medium|high|xhigh|max' && [...$('ai-level').options].filter(option => option.value !== 'default').every(option => option.disabled), 'model-default-exception-preserves-six-standard-disabled-labels');
            const selectChrome = parseFloat(defaultStyle.paddingLeft) + parseFloat(defaultStyle.paddingRight) + parseFloat(defaultStyle.borderLeftWidth) + parseFloat(defaultStyle.borderRightWidth);
            const standardLabels = ['off', 'low', 'medium', 'high', 'xhigh', 'max'];
            const standardTextWidths = Object.fromEntries(standardLabels.map(text => [text, context.measureText(text).width]));
            const longestStandard = Math.max(...Object.values(standardTextWidths)), defaultTextWidth = context.measureText('모델 기본값').width;
            const normalReference = nativeSelectReference(standardLabels), defaultReference = nativeSelectReference(['모델 기본값', ...standardLabels]);
            layout.reasoningSizing = { normalWidth: normalLevelWidth, defaultWidth: rect($('ai-level')).width, standardTextWidths, defaultTextWidth, paddingAndBorders: selectChrome, computedFont: context.font, normalReference, defaultReference };
            assert(normalLevelWidth >= longestStandard + selectChrome - 1 && rect($('ai-level')).width >= Math.max(longestStandard, defaultTextWidth) + selectChrome - 1, 'reasoning-standard-and-default-labels-have-glyph-space');
            assert(Math.abs(normalLevelWidth - normalReference.width) <= 1 && Math.abs(rect($('ai-level')).width - defaultReference.width) <= 1, 'reasoning-width-matches-native-fixed-label-references');
            $('ai-model').value = modelId; $('ai-model').dispatchEvent(new Event('change'));
            await wait(() => !$('ai-model').disabled && $('ai-level').value === 'medium' && !$('ai-send').disabled, 'Qwen reasoning restored');

            server.rejectNextSelection = true; const selectionsBefore = posts('selection').length;
            $('ai-level').value = 'low'; $('ai-level').dispatchEvent(new Event('change'));
            await wait(() => posts('selection').length > selectionsBefore && !$('ai-model').disabled && $('ai-notice').textContent.includes('시험용 설정 저장 오류'), 'selection save failure');
            assert(!$('ai-notice').hidden && $('ai-send').disabled && $('ai-input').value === '모델 목록과 오류 뒤에도 보존할 초안' && document.querySelector('.ai-answer table') === stableTable, 'selection-error-keeps-cause-draft-reader-and-blocked-send');
            $('ai-level').value = 'medium'; $('ai-level').dispatchEvent(new Event('change'));
            await wait(() => !$('ai-model').disabled && !$('ai-send').disabled && server.conversations.get(oldCid).next_level === 'medium', 'selection recovery');
            assert(posts('turns').length === refreshTurns && [...$('ai-level').options].map(option => option.textContent).join('|') === 'off|low|medium|high|xhigh|max', 'settings-recovery-does-not-send-or-expand-reasoning-labels');
            assert($('ai-notice').hidden && !$('ai-notice').textContent.trim(), 'successful-selection-recovery-clears-matching-global-notice');

            let releaseConcurrentInventory; server.holdModels = new Promise(resolve => { releaseConcurrentInventory = resolve; });
            readsBefore = modelReads(); $('ai-model-refresh').click();
            await wait(() => modelReads() > readsBefore && $('ai-model-refresh').getAttribute('aria-busy') === 'true', 'inventory held during independent selection error');
            server.rejectNextSelection = true; const concurrentSelectionsBefore = posts('selection').length;
            $('ai-level').value = 'low'; $('ai-level').dispatchEvent(new Event('change'));
            await wait(() => posts('selection').length > concurrentSelectionsBefore && !$('ai-model').disabled && $('ai-notice').textContent.includes('시험용 설정 저장 오류'), 'independent selection error while inventory pending');
            const independentSelectionError = $('ai-notice').textContent;
            assert(!$('ai-notice').hidden && $('ai-model-refresh').getAttribute('aria-busy') === 'true' && $('ai-input').value === '모델 목록과 오류 뒤에도 보존할 초안', 'independent-selection-error-remains-visible-during-pending-inventory');
            releaseConcurrentInventory();
            await wait(() => !$('ai-model-refresh').disabled && $('ai-model-refresh').getAttribute('aria-busy') === 'false', 'independent inventory success');
            assert(!$('ai-notice').hidden && $('ai-notice').textContent === independentSelectionError, 'inventory-success-cannot-erase-unrecovered-selection-error');
            $('ai-level').value = 'medium'; $('ai-level').dispatchEvent(new Event('change'));
            await wait(() => !$('ai-model').disabled && !$('ai-send').disabled && server.conversations.get(oldCid).next_level === 'medium', 'independent selection recovery');
            assert($('ai-notice').hidden && !$('ai-notice').textContent.trim() && posts('turns').length === refreshTurns && document.querySelector('.ai-answer table') === stableTable, 'matching-selection-recovery-clears-overlapping-error-and-keeps-reader');

            await reflowAcrossBoundary('readyReflow');
            for (const id of ['ai-model', 'ai-model-refresh', 'ai-level', 'ai-send']) {
                $(id).focus(); assert(document.activeElement === $(id) && rect($(id)).width > 0 && rect($(id)).height > 0, id + '-enabled-control-programmatic-focus-reachable');
            }
            $('ai-new').click(); await wait(() => titleIsAccessible('새로운 대화') && !$('ai-model').disabled && document.querySelector(`#ai-conversations .ai-conversation[data-conversation-id="${newCid}"]`), 'new conversation current title');
            assert($('ai-model').value === modelId && $('ai-level').value === 'medium' && $('ai-welcome').hidden === false && !$('ai-model-status').textContent.trim(), 'new-conversation-title-and-default-selection-are-current');
            measure('newConversation');
            if (!currentOld()) { $('ai-more-conversations').click(); await wait(() => currentOld(), 'return to older conversation after new chat'); }
            currentOld().click(); await wait(() => titleIsAccessible(originalTitle) && document.querySelector('.ai-answer table') && !$('ai-model').disabled, 'final Qwen table view');
            assert($('ai-model').value === modelId && $('ai-level').value === 'medium' && $('ai-model').selectedOptions[0].textContent === '260Strata / Qwen3.8 Flash Next', 'final-measurement-uses-Qwen-medium-and-real-stored-table');
            assert(server.requests.filter(entry => entry.method === 'POST').every(entry => entry.headers['X-CSRFToken'] === 'fixture-csrf'), 'new-compact-scenarios-also-retain-csrf');
            compact('finalNormal');
            $('ai-model-settings').querySelector('summary').click();
            assert(!$('ai-model-settings').open, 'model-settings-return-to-collapsed-for-final-screen');
            measure('finalCollapsed');
            report.textContent = JSON.stringify({ status: 'pass', checks, width: innerWidth, theme, requests: server.requests.length, layout, focusMethod: 'programmatic-focus', viewportEmulation: 'CSS layout/reduced height only; native zoom, Tab traversal and phone keyboard are not exercised here', selectedModel: { id: $('ai-model').value, text: $('ai-model').selectedOptions[0].textContent, level: $('ai-level').value } });
        } catch (error) {
            report.textContent = JSON.stringify({ status: 'fail', checks, error: error.message, width: innerWidth, theme, layout, dialog: $('ai-dialog-title')?.textContent, notice: $('ai-notice')?.textContent, requests: server.requests.slice(-8) });
        } finally {
            releaseCompletion();
        }
        if (window.parent !== window) window.parent.postMessage({ fixtureResult: report.textContent }, location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
})();
