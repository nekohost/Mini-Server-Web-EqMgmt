/* [MINI-COMMENT: ASSISTANT.CLIENT]
 * [EN rev.13]
 * [Role] Renders owner chat and requested file/CSV workspaces with measured viewport fitting and preserved conversation lifecycle actions.
 * [Dependencies] Vanilla DOM/fetch and /api/ai; existing file/CSV APIs retain their own authorization.
 * [Impact] Actual frame geometry controls height only when minimum content space fits; resizing preserves reader/model/request state. Fixed file links, stale-preview isolation, explicit writes and independent lifecycle/notice recovery remain intact.
 */
(function () {
    'use strict';
    const reasoningLevels = ['off', 'low', 'medium', 'high', 'xhigh', 'max'];
    const reasoningHelp = { off: '추론을 끄고 답합니다.', low: '적은 추론으로 답합니다.', medium: '중간 수준으로 검토합니다.', high: '높은 수준으로 검토합니다.', xhigh: '더 깊게 검토하며 시간이 길어질 수 있습니다.', max: '모델이 지원하는 최대 추론 수준입니다.', default: '추론 수준을 지정하지 않고 모델 기본 동작을 사용합니다.' };

    /** [Role] Uses the server model default only when initializing a new choice, never to replace a saved unavailable effort. */
    const initialLevel = model => model && model.default_level || (model && model.levels && model.levels.includes('medium') ? 'medium' : model && model.levels && model.levels[0] || 'default');

    /** [Role] Merges cumulative thoughts and closes them once per turn, across model generations.
     * [Dependencies] Server generation/code-point cursors and a sticky answer_started flag.
     * [Impact] A later tool step cannot erase thoughts or close a manually reopened section.
     */
    function mergeStream(previous, delta) {
        const reset = previous.generation !== delta.generation;
        const answer = (reset ? '' : previous.content) + delta.content;
        const started = previous.answerStarted;
        const hasAnswer = Boolean(delta.content) || Boolean(delta.answer_started);
        return { reasoning: previous.reasoning + delta.reasoning, content: answer,
            generation: delta.generation, r: delta.r, c: delta.c,
            answerStarted: started || hasAnswer, closeThought: !started && hasAnswer };
    }

    const pendingMarkdown = new WeakMap();
    const tableLimit = { columns: 40, rows: 200 };

    /** [MINI-COMMENT: ASSISTANT.CLIENT.FILE.LINK]
     * [EN rev.1]
     * [Role] Maps only exact app-owned file links to a fixed dialog panel.
     * [Dependencies] Two literal workspace paths and the existing my/public CSV export URL.
     * [Impact] Query additions, remote origins, fragments and model HTML cannot choose an endpoint, owner or executable.
     */
    function fileWorkspaceTarget(href) {
        if (href === '/assistant?panel=csv-import') return { panel: 'csv-import' };
        if (href === '/assistant?panel=attachment') return { panel: 'attachment' };
        for (const scope of ['my','public']) if (href === '/api/ai/csv/export?scope=' + scope) return { panel: 'csv-export', scope };
        return null;
    }

    /** [Role] Marks a safely rendered local anchor as a dialog trigger without parsing model attributes. */
    function workspaceLink(anchor, href) {
        const target = fileWorkspaceTarget(href);
        if (target) {
            anchor.dataset.aiWorkspace = target.panel;
            if (target.scope) anchor.dataset.aiScope = target.scope;
            anchor.setAttribute('aria-haspopup', 'dialog');
            anchor.setAttribute('aria-controls', 'ai-file-dialog');
        }
        return anchor;
    }

    /** [Role] Splits unescaped table pipes, retaining escapes until safe inline rendering. */
    function tableCells(line) {
        const source = line.trim();
        const cells = []; let start = 0, pipes = 0;
        for (let i = 0; i < source.length; i++) {
            if (source[i] === '\\') { i++; continue; }
            if (source[i] === '|') { cells.push(source.slice(start, i).trim()); start = i + 1; pipes++; }
        }
        cells.push(source.slice(start).trim());
        if (!pipes) return null;
        if (source.startsWith('|')) cells.shift();
        if (start === source.length) cells.pop();
        return cells;
    }

    /** [Role] Adds text, inline code, emphasis and existing allowlisted local links only. */
    function markdownInline(block, source) {
        const doc = block.ownerDocument;
        const unescape = text => text.replace(/\\([\\|`*])/g, '$1');
        for (const part of source.split(/(`[^`\n]*`|\*\*[^*\n]+\*\*|\[[^\]\n]{1,200}\]\(\/[^\s)\n]{1,200}\))/g)) {
            const link = /^\[([^\]]+)\]\((\/[^)]+)\)$/.exec(part);
            if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
                const code = doc.createElement('code'); code.textContent = unescape(part.slice(1, -1)); block.append(code);
            } else if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
                const strong = doc.createElement('strong'); strong.textContent = unescape(part.slice(2, -2)); block.append(strong);
            } else if (link && (fileWorkspaceTarget(link[2]) || /^(?:\/api\/ai\/equipment\/[1-9]\d*\/files\/[1-9]\d*\/download|\/(?:my_equipment|public_equipment|my_approvals|mypage))$/.test(link[2]))) {
                const anchor = doc.createElement('a'); anchor.href = link[2]; anchor.textContent = unescape(link[1]); block.append(workspaceLink(anchor, link[2]));
            } else block.append(doc.createTextNode(unescape(part || '')));
        }
    }

    /** [MINI-COMMENT: ASSISTANT.CLIENT.MARKDOWN]
     * [EN rev.1]
     * [Role] Renders a bounded DOM-only Markdown subset with pipe tables, alignment, escaped pipes and fenced code.
     * [Dependencies] Safe inline allowlist, completed streaming lines and the existing stable message/details nodes.
     * [Impact] No model HTML is parsed; selected text defers replacement, table scroll survives updates and oversized tables retain an explicit raw-text view.
     */
    function markdown(target, value, { streaming = false } = {}) {
        const doc = target.ownerDocument;
        value = String(value ?? '').replace(/\r\n?/g, '\n');
        const selected = doc.getSelection?.();
        if (selected && !selected.isCollapsed && (target.contains(selected.anchorNode) || target.contains(selected.focusNode))) {
            const pending = pendingMarkdown.get(target);
            if (pending) { pending.value = value; pending.streaming = streaming; }
            else {
                const state = { value, streaming };
                const resume = () => {
                    const selection = doc.getSelection?.();
                    if (target.isConnected && selection && !selection.isCollapsed && (target.contains(selection.anchorNode) || target.contains(selection.focusNode))) return;
                    doc.removeEventListener('selectionchange', resume); pendingMarkdown.delete(target);
                    if (target.isConnected) markdown(target, state.value, { streaming: state.streaming });
                };
                pendingMarkdown.set(target, state); doc.addEventListener('selectionchange', resume);
            }
            return;
        }
        const positions = [...target.querySelectorAll('.ai-table-scroll')].map(node => ({ left: node.scrollLeft, top: node.scrollTop, focused: node === doc.activeElement }));
        const rawPositions = [...target.querySelectorAll('.ai-table-raw')].map(node => ({ open: node.open, top: node.querySelector('pre')?.scrollTop || 0, left: node.querySelector('pre')?.scrollLeft || 0 }));
        const fragment = doc.createDocumentFragment();
        const lines = value.split('\n');
        const complete = index => !streaming || index < lines.length - 1;
        let code = null, fence = null;
        for (let index = 0; index < lines.length; index++) {
            const line = lines[index];
            const marker = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line);
            if (code) {
                if (marker && marker[1][0] === fence[0] && marker[1].length >= fence.length && !marker[2].trim()) {
                    fragment.append(code); code = null; fence = null;
                } else code.append(doc.createTextNode(line + (index < lines.length - 1 ? '\n' : '')));
                continue;
            }
            if (marker) { code = doc.createElement('pre'); fence = marker[1]; continue; }
            const header = complete(index) && tableCells(line);
            const separator = index + 1 < lines.length && complete(index + 1) && tableCells(lines[index + 1]);
            if (header && separator && header.length && header.length === separator.length && separator.every(cell => /^:?-+:?$/.test(cell))) {
                const start = index; index += 2;
                const rows = [];
                while (index < lines.length && complete(index) && lines[index].trim() && tableCells(lines[index])) { rows.push(tableCells(lines[index])); index++; }
                const source = lines.slice(start, index).join('\n'); index--;
                const clipped = header.length > tableLimit.columns || rows.length > tableLimit.rows || rows.some(row => row.length > header.length);
                if (header.length <= tableLimit.columns) {
                    const wrapper = doc.createElement('div'); wrapper.className = 'ai-table-scroll'; wrapper.tabIndex = 0;
                    wrapper.setAttribute('role', 'region'); wrapper.setAttribute('aria-label', '응답 표 · 가로로 스크롤할 수 있습니다');
                    const table = doc.createElement('table'), head = doc.createElement('thead'), body = doc.createElement('tbody');
                    const appendRow = (parent, cells, heading) => {
                        const row = doc.createElement('tr');
                        header.forEach((_, column) => {
                            const cell = doc.createElement(heading ? 'th' : 'td');
                            if (heading) cell.setAttribute('scope', 'col');
                            const align = separator[column];
                            cell.className = align.startsWith(':') && align.endsWith(':') ? 'ai-align-center' : align.endsWith(':') ? 'ai-align-right' : 'ai-align-left';
                            markdownInline(cell, cells[column] || ''); row.append(cell);
                        });
                        parent.append(row);
                    };
                    appendRow(head, header, true); rows.slice(0, tableLimit.rows).forEach(row => appendRow(body, row, false));
                    table.append(head, body); wrapper.append(table); fragment.append(wrapper);
                }
                if (clipped) {
                    const raw = doc.createElement('details'); raw.className = 'ai-table-raw';
                    const summary = doc.createElement('summary'); summary.textContent = header.length > tableLimit.columns ? '열이 많은 표입니다. 전체 원문 보기' : `표는 최대 ${tableLimit.rows}행과 머리글 열까지 표시합니다. 전체 원문 보기`;
                    const original = doc.createElement('pre'); original.textContent = source; raw.append(summary, original); fragment.append(raw);
                }
                continue;
            }
            const heading = /^(#{1,4})\s+(.+)$/.exec(line);
            const bullet = /^\s*(?:[-*]|\d+\.)\s+(.+)$/.exec(line);
            const block = doc.createElement(heading ? 'h3' : bullet ? 'li' : 'p');
            const source = heading ? heading[2] : bullet ? bullet[1] : line;
            markdownInline(block, source);
            fragment.append(block);
        }
        if (code) fragment.append(code);
        target.replaceChildren(fragment);
        target.querySelectorAll('.ai-table-scroll').forEach((node, index) => {
            if (!positions[index]) return;
            node.scrollLeft = positions[index].left; node.scrollTop = positions[index].top;
            if (positions[index].focused) node.focus({ preventScroll: true });
        });
        target.querySelectorAll('.ai-table-raw').forEach((node, index) => {
            if (!rawPositions[index]) return;
            node.open = rawPositions[index].open; const original = node.querySelector('pre');
            original.scrollTop = rawPositions[index].top; original.scrollLeft = rawPositions[index].left;
        });
    }

    /** [MINI-COMMENT: ASSISTANT.CLIENT.VIEWPORT]
     * [EN rev.1]
     * [Role] Fits the assistant to measured document/visual viewport space without hiding short-screen content.
     * [Dependencies] Existing CSS minimums, actual frame padding/nav, ResizeObserver and batched animation frames.
     * [Impact] Only style/diagnostic attributes change; no scroll position, selected conversation, draft or network operation is reset. Minimum/zoom fallback retains page scrolling and teardown removes every observer/listener.
     */
    function fitViewport(root) {
        const pane = root.querySelector('#ai-scroll'), viewport = window.visualViewport;
        let frame = null, stopped = false;
        const pixels = value => Number.parseFloat(value) || 0;
        const setStyle = (name, value) => { if (root.style.getPropertyValue(name) !== value) root.style.setProperty(name,value); };
        const setData = (name, value) => { if (root.dataset[name] !== String(value)) root.dataset[name] = String(value); };
        const measure = () => {
            frame = null; if (stopped || !root.isConnected || !pane) return;
            const style = getComputedStyle(root), box = root.getBoundingClientRect();
            let bottom = pixels(style.marginBottom);
            for (let ancestor = root.parentElement; ancestor; ancestor = ancestor.parentElement) {
                const parentStyle = getComputedStyle(ancestor);
                bottom += pixels(parentStyle.paddingBottom) + pixels(parentStyle.borderBottomWidth) + pixels(parentStyle.marginBottom);
                if (ancestor === document.body) break;
            }
            const height = viewport?.height || window.innerHeight;
            const available = Math.floor(height - Math.max(0, box.top + window.scrollY) - bottom - 1);
            const fixed = Math.max(0,root.clientHeight - pane.clientHeight);
            const minimum = Math.ceil(Math.max(pixels(style.getPropertyValue('--ai-min-height')),fixed + 120));
            const maximum = Number.parseFloat(style.maxHeight);
            setStyle('--ai-measured-min-height',minimum + 'px');
            const fits = (!viewport || Math.abs(viewport.scale - 1) < .01) && available >= minimum;
            if (fits) setStyle('--ai-fitted-height',Math.max(minimum,Math.min(available,Number.isFinite(maximum) ? maximum : available)) + 'px');
            else if (root.style.getPropertyValue('--ai-fitted-height')) root.style.removeProperty('--ai-fitted-height');
            setData('viewportFit',fits ? 'fit' : 'minimum'); setData('viewportAvailable',available); setData('viewportMinimum',minimum);
        };
        const queue = () => { if (!stopped && frame === null) frame = requestAnimationFrame(measure); };
        const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(queue) : null;
        for (const element of [root,root.parentElement,pane,document.querySelector('nav[aria-label="전역 네비게이션"]')]) if (element) observer?.observe(element);
        window.addEventListener('resize',queue); window.addEventListener('orientationchange',queue);
        viewport?.addEventListener('resize',queue); viewport?.addEventListener('scroll',queue);
        document.fonts?.addEventListener('loadingdone',queue); document.fonts?.ready.then(queue);
        queue();
        return () => {
            stopped = true; if (frame !== null) cancelAnimationFrame(frame); observer?.disconnect();
            window.removeEventListener('resize',queue); window.removeEventListener('orientationchange',queue);
            viewport?.removeEventListener('resize',queue); viewport?.removeEventListener('scroll',queue); document.fonts?.removeEventListener('loadingdone',queue);
        };
    }

    if (typeof module !== 'undefined' && module.exports) module.exports = { mergeStream, markdown, fileWorkspaceTarget };
    if (typeof document === 'undefined') return;

    /** [Role] Initializes this standalone screen, preserving drafts/details/scroll across incremental polling. */
    async function initialize() {
        const root = document.getElementById('equipment-ai');
        if (!root) return;
        const $ = id => document.getElementById(id);
        const csrf = root.dataset.csrf;
        const disposeViewport = fitViewport(root);
        const nodes = new Map(), streams = new Map(), cards = new Map();
        const history = { active: { items: new Map(), cursor: null, depth: 1, request: 0, pending: null }, trash: { items: new Map(), cursor: null, depth: 1, request: 0, pending: null } };
        const uncertainLifecycle = new Map();
        const terminal = new Set(['done', 'failed', 'cancelled', 'waiting_confirmation']);
        let conversation = null, activeJob = null, timer = null, disposed = false, polling = false;
        let selection = 0, requestKey = null, csvToken = null, retryDelay = 1500, accountContext = null, identityTimer = null, checkingIdentity = false;
        let historyView = 'active', conversationView = 'active', conversationMeta = null, nextBefore = null, loadingHistory = false;
        let lifecycleBusy = false, lifecycleIntent = false, syncingLifecycle = false, dialogResolve = null, dialogFocus = null, lifecycleChannel = null, invalidationPending = false, creatingConversation = false;
        let modelChoices = [], modelId = null, defaultModel = null, modelRevision = 0, modelUnavailable = false, changingModel = false, openingConversation = false, unattributedSelection = false, capabilities = null;
        let loadingModels = false, modelsPromise = null, inventoryError = '', currentNoticeSource = null;
        let fileEpoch = 0, fileBusy = false, filePanel = null, fileFocus = null, csvFileVersion = 0;
        const controller = new AbortController();
        const labels = { equipment_create: '내 장비 등록', equipment_update: '내 장비 정보 수정', equipment_status: '내 장비 상태 변경',
            catalog_request: '카탈로그 등록 신청', option_request: '옵션 등록 신청', preferences: '내 설정 변경', csv_export: 'CSV 내보내기' };
        const fields = { equipment_id: '장비 번호', name: '장비 이름', option_id: '옵션 번호', serial_number: '시리얼 번호', purchase_date: '구입일',
            warranty_end_date: '보증 종료일', replacement_due_date: '교체 예정일', memo: '메모', is_public: '공개 여부', is_draft: '임시저장',
            status: '상태', reason: '변경 사유', kind: '신청 종류', category_id: '카테고리 번호', manufacturer_id: '제조사 번호', parent_id: '상위 노드 번호',
            lineup_node_id: '모델 노드 번호', option_name: '옵션 이름', specs: '사양', theme: '테마', layout_skin: '화면 구성', deadline_email_opt_in: '기한 알림 수신', scope: '조회 범위' };

        /** [Role] Shows safe text feedback; source-specific recovery clears only its own current notice, while a generic reset retains its existing unconditional behavior. */
        function notice(message = '', source = 'general') {
            if (!message && source !== 'general' && currentNoticeSource !== source) return;
            currentNoticeSource = message ? source : null;
            $('ai-notice').textContent = message; $('ai-notice').hidden = !message;
        }

        /** [Role] Keeps the complete current title available when the compact mobile heading is visually truncated. */
        function setConversationTitle(title) {
            const heading = $('ai-title'), fullTitle = String(title ?? '');
            heading.textContent = fullTitle; heading.title = fullTitle; heading.setAttribute('aria-label', fullTitle);
        }
        setConversationTitle($('ai-title').textContent);

        /** [Role] Locks all conversation-dependent writes while trash or a mutation result is unresolved. */
        function readOnly() { return conversationView === 'trash' || Boolean(conversationMeta?.is_deleted) || uncertainLifecycle.has(conversation); }

        /** [Role] Formats only server UTC epoch values in the reader's local timezone. */
        function lifecycleDate(epoch) {
            return typeof epoch === 'number' && Number.isFinite(epoch) ? new Date(epoch * 1000).toLocaleString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' }) : '서버 확인 필요';
        }

        /** [Role] Updates the selected-conversation lock and exposes only actions valid for its current view. */
        function lifecycleControls() {
            const locked = readOnly() || lifecycleBusy || creatingConversation;
            $('ai-input').disabled = locked;
            $('ai-form').hidden = readOnly();
            if (readOnly() && (filePanel || $('ai-file-dialog').open)) resetFileWorkspace();
            $('ai-file-controls').disabled = locked || fileBusy;
            root.querySelectorAll('[data-prompt]').forEach(button => { button.disabled = locked; });
            root.querySelectorAll('.ai-confirm').forEach(button => { button.disabled = locked || Number(button.dataset.expires) * 1000 < Date.now(); });
            $('ai-conversation-actions').hidden = !conversation || !conversationMeta;
            $('ai-trash-current').hidden = conversationView !== 'active';
            $('ai-restore-current').hidden = $('ai-purge-current').hidden = conversationView !== 'trash';
            for (const id of ['ai-trash-current', 'ai-restore-current', 'ai-purge-current']) $(id).disabled = lifecycleBusy || openingConversation || changingModel || uncertainLifecycle.has(conversation);
            for (const id of ['ai-active-tab', 'ai-trash-tab']) $(id).disabled = lifecycleBusy || openingConversation;
            $('ai-new').disabled = lifecycleBusy || openingConversation || changingModel || creatingConversation;
            root.querySelectorAll('[data-lifecycle-action]').forEach(button => {
                button.disabled = lifecycleBusy || openingConversation || changingModel || uncertainLifecycle.has(button.dataset.conversationId);
            });
            $('ai-cancel').disabled = locked;
            $('ai-lifecycle-reconcile').hidden = !uncertainLifecycle.size;
            $('ai-lifecycle-reconcile').disabled = lifecycleBusy || syncingLifecycle;
            const trashText = conversationView === 'trash' && conversationMeta ? `휴지통의 대화입니다. 읽기 전용이며 ${lifecycleDate(conversationMeta.purge_after)}에 보관이 만료됩니다. 이동한 시각부터 30일 동안 보관하며, 만료 시점부터 열람과 복구가 제한됩니다. 취소된 요청과 작업은 복구해도 다시 실행되지 않습니다.` : '';
            $('ai-lifecycle-text').textContent = uncertainLifecycle.size ? '대화 조작의 처리 결과를 확인하지 못했습니다. 자동으로 다시 보내지 않습니다. 처리 결과를 확인해 주세요.' : trashText;
            $('ai-lifecycle-notice').hidden = !uncertainLifecycle.size && !trashText;
            root.setAttribute('aria-busy', String(lifecycleBusy || openingConversation));
        }

        /** [Role] Presents one native dialog and returns explicit confirmation, with cancel as the destructive-action focus. */
        function lifecycleDialog({ title, message, detail = '', confirm = '확인', cancel = false, danger = false, busy = false }) {
            const dialog = $('ai-lifecycle-dialog');
            $('ai-dialog-title').textContent = title; $('ai-dialog-message').textContent = message; $('ai-dialog-detail').textContent = detail;
            $('ai-dialog-cancel').hidden = !cancel || busy; $('ai-dialog-confirm').hidden = busy;
            $('ai-dialog-confirm').textContent = confirm; $('ai-dialog-confirm').classList.toggle('ai-danger', danger);
            dialog.setAttribute('aria-busy', String(busy));
            if (!dialog.open) { dialogFocus = document.activeElement; dialog.showModal(); }
            (busy ? $('ai-dialog-title') : cancel ? $('ai-dialog-cancel') : $('ai-dialog-confirm')).focus({ preventScroll: true });
            if (busy) return;
            return new Promise(resolve => { dialogResolve = resolve; });
        }

        /** [Role] Finds a visible enabled focus target after a lifecycle refresh replaced or hid the original control. */
        function restoreDialogFocus() {
            const candidates = [dialogFocus, conversationView === 'trash' ? $('ai-restore-current') : $('ai-trash-current'), $('ai-menu-toggle'), conversationView === 'trash' ? $('ai-trash-tab') : $('ai-active-tab'), $('ai-new')];
            const target = candidates.find(node => node?.isConnected && node.matches('button,a[href],input,select,textarea,[tabindex]') && !node.disabled && !node.hidden && node.getClientRects().length);
            target?.focus({ preventScroll: true });
        }

        /** [Role] Resolves dialog input; the mutation finalizer restores focus again after releasing its control lock. */
        function finishDialog(confirmed) {
            const dialog = $('ai-lifecycle-dialog');
            if (dialog.getAttribute('aria-busy') === 'true') return;
            const resolve = dialogResolve; dialogResolve = null; dialog.close();
            restoreDialogFocus();
            if (resolve) resolve(confirmed);
        }

        /** [MINI-COMMENT: ASSISTANT.CLIENT.FILE.WORKSPACE]
         * [EN rev.2]
         * [Role] Opens one user-requested native dialog while retaining the existing file/CSV API boundary.
         * [Dependencies] Current capabilities, owner conversation lifecycle, native dialog focus and a separate operation epoch.
         * [Impact] Closing never resends work; boundaries discard selected files/tokens and reject late previews. A completed write may report its outcome to the same account after a conversation switch, without populating that conversation's file panel.
         */
        function openFileWorkspace(panel, scope, trigger) {
            if (disposed || readOnly() || lifecycleBusy || lifecycleIntent || openingConversation || creatingConversation || dialogResolve) {
                notice('현재 대화 상태에서는 파일 작업을 열 수 없습니다. 정상 대화에서 다시 요청해 주세요.'); return;
            }
            const exported = panel === 'csv-export' && ['my','public'].includes(scope);
            if (exported ? !(capabilities?.scopes || []).includes(scope) : !['csv-import','attachment'].includes(panel) || !capabilities?.file_tools) {
                notice('이 파일 작업을 사용할 권한이 없거나 현재 비활성 상태입니다.'); return;
            }
            if (fileBusy && filePanel !== panel) { notice('진행 중인 파일 작업의 결과를 확인한 뒤 다른 작업을 열어 주세요.'); return; }
            notice('', 'file');
            if (filePanel !== panel) fileNotice('');
            filePanel = panel;
            $('ai-upload-form').hidden = panel !== 'attachment'; $('ai-csv-form').hidden = panel !== 'csv-import'; $('ai-csv-export').hidden = !exported;
            const descriptions = {
                'csv-import': ['CSV 가져오기', '파일을 선택해 등록 전 내용을 확인하세요. 확인 버튼을 눌러야 본인 장비에 등록됩니다.'],
                attachment: ['내 장비에 파일 첨부', '본인 장비 번호와 첨부할 파일을 선택하세요. 파일은 모델에 보내지 않고 장비관리 서버에 업로드합니다.'],
                'csv-export': ['CSV 내보내기', '선택한 범위를 확인한 뒤 파일을 내려받으세요. 다운로드 시 현재 계정의 권한을 다시 확인합니다.']
            };
            [$('ai-file-title').textContent, $('ai-file-description').textContent] = descriptions[panel];
            if (exported) {
                $('ai-csv-export-scope').textContent = scope === 'my' ? '내보낼 범위: 내 장비' : '내보낼 범위: 공개 장비';
                $('ai-csv-download').href = '/api/ai/csv/export?scope=' + scope;
            }
            const dialog = $('ai-file-dialog');
            if (!dialog.open) { fileFocus = trigger || document.activeElement; dialog.showModal(); }
            $('ai-file-title').focus({ preventScroll: true });
            lifecycleControls();
        }

        /** [Role] Restores a still-visible trigger or the composer after an Escape/close, without changing pending requests. */
        function closeFileWorkspace() {
            if (!$('ai-file-dialog').open) return;
            $('ai-file-dialog').close();
            const target = [fileFocus, $('ai-input'), $('ai-menu-toggle')].find(node => node?.isConnected && !node.disabled && node.getClientRects().length);
            target?.focus({ preventScroll: true });
        }

        /** [Role] Clears all transient file data at an owner/conversation boundary and invalidates late HTTP callbacks. */
        function resetFileWorkspace() {
            ++fileEpoch; ++csvFileVersion; csvToken = null; fileBusy = false; filePanel = null; fileFocus = null;
            const dialog = $('ai-file-dialog');
            if (dialog?.open) dialog.close();
            $('ai-upload-form')?.reset(); $('ai-csv-form')?.reset();
            if ($('ai-csv-preview')) { $('ai-csv-preview').hidden = true; $('ai-csv-preview').textContent = ''; }
            if ($('ai-csv-confirm')) $('ai-csv-confirm').hidden = true;
            if ($('ai-csv-download')) $('ai-csv-download').removeAttribute('href');
            if ($('ai-file-notice')) { $('ai-file-notice').hidden = true; $('ai-file-notice').textContent = ''; }
            dialog?.setAttribute('aria-busy', 'false');
        }

        /** [Role] Keeps result/error feedback inside the popup, announcing completed work outside it if the user closed it. */
        function fileNotice(message) {
            if (disposed) return;
            $('ai-file-notice').textContent = message; $('ai-file-notice').hidden = !message;
            if (message && !$('ai-file-dialog').open) notice(message, 'file');
        }

        /** [Role] Admits one explicit file operation and ignores results whose conversation/account epoch was invalidated. */
        async function fileOperation(message, action, { write = false } = {}) {
            if (fileBusy || disposed || readOnly() || lifecycleBusy || !capabilities?.file_tools || !$('ai-file-dialog').open) return;
            const epoch = fileEpoch, account = accountContext, cid = conversation;
            const current = () => !disposed && epoch === fileEpoch && account === accountContext && cid === conversation && !readOnly();
            fileBusy = true; fileNotice(message); $('ai-file-dialog').setAttribute('aria-busy','true'); lifecycleControls();
            try {
                const outcome = await action(current);
                if (typeof outcome === 'string') {
                    if (current()) fileNotice(outcome);
                    else if (write && !disposed && account === accountContext) notice('이전 대화에서 요청한 파일 작업: ' + outcome, 'file');
                }
            }
            catch (error) {
                if (current()) fileNotice(error.message);
                else if (write && !disposed && account === accountContext) notice('이전 대화에서 요청한 파일 작업: ' + error.message, 'file');
            }
            finally {
                if (current()) { fileBusy = false; $('ai-file-dialog').setAttribute('aria-busy','false'); lifecycleControls(); }
            }
        }

        /** [Role] Renders only published opaque choices and restores conversation-specific supported reasoning.
         * [Dependencies] Safe server projections; no provider URL/key/raw metadata reaches this screen.
         * [Impact] A saved unavailable model/effort remains selected and disabled until it returns; only an available model without reasoning uses the default fallback, and short labels expose disabled reasons separately without reserving a normal-status row.
         */
        function modelControls(restoredLevel) {
            if (disposed) return;
            restoredLevel ??= $('ai-level').value;
            const fragment = document.createDocumentFragment();
            for (const model of modelChoices) {
                const option = document.createElement('option'); option.value = model.id;
                option.textContent = `${model.provider} / ${model.label}`;
                option.disabled = !model.available; fragment.append(option);
            }
            const model = modelChoices.find(item => item.id === modelId);
            if (modelId && !model) {
                const missing = document.createElement('option'); missing.value = modelId; missing.textContent = '이 대화의 이전 모델'; missing.disabled = true; fragment.append(missing);
            }
            $('ai-model').replaceChildren(fragment); $('ai-model').value = modelId || '';
            $('ai-model').title = model ? `${model.provider} / ${model.label}` : modelId ? '이 대화의 이전 모델' : '사용 가능한 모델 없음';
            const levels = model && model.available ? model.levels || [] : [];
            const options = document.createDocumentFragment();
            const unsupported = document.createDocumentFragment();
            if (!levels.length || restoredLevel === 'default') {
                const option = document.createElement('option'); option.value = 'default'; option.textContent = '모델 기본값';
                option.disabled = !model || !model.available || Boolean(levels.length); options.append(option);
                if (model && model.available && !levels.length) restoredLevel = 'default';
            }
            for (const level of reasoningLevels) {
                const option = document.createElement('option'); option.value = level;
                option.disabled = !levels.includes(level);
                option.textContent = level; options.append(option);
                if (option.disabled) {
                    const reason = document.createElement('li');
                    reason.textContent = `${level}: ${model && model.level_reasons && model.level_reasons[level] || '사용 불가'}`; unsupported.append(reason);
                }
            }
            $('ai-reasoning-support').hidden = !unsupported.childElementCount;
            $('ai-reasoning-reasons').replaceChildren(unsupported);
            $('ai-level').replaceChildren(options); $('ai-level').value = restoredLevel;
            modelUnavailable = !model || !model.available || (levels.length ? !levels.includes($('ai-level').value) : $('ai-level').value !== 'default');
            $('ai-level').disabled = !levels.length || changingModel || openingConversation || readOnly() || lifecycleBusy || creatingConversation;
            $('ai-level-help').textContent = reasoningHelp[$('ai-level').value] || '지원하며 허용된 추론 수준을 선택해 주세요.';
            $('ai-model').disabled = changingModel || openingConversation || readOnly() || lifecycleBusy || creatingConversation;
            $('ai-model-refresh').disabled = loadingModels || changingModel || openingConversation || lifecycleBusy;
            $('ai-model-refresh').setAttribute('aria-busy', String(loadingModels));
            const status = [];
            if (loadingModels) status.push('모델 목록을 확인하고 있습니다.');
            if (inventoryError) status.push(`모델 목록 새로고침 실패: ${inventoryError}`);
            if (modelUnavailable) {
                if (!loadingModels || modelId) status.push(model && model.reason || '이 대화의 모델/추론 설정을 복원할 수 없습니다. 모델과 지원 추론을 다시 선택해 주세요.');
            } else if (!model.tools) status.push('대화 전용 · 장비 업무는 지원 모델 또는 수동 화면을 이용해 주세요.');
            if (activeJob) status.push('변경은 다음 요청부터 적용됩니다. 접수된 요청은 기존 모델을 사용합니다.');
            if (unattributedSelection) status.push('이전 모델 기록이 없습니다. 표시한 기본 모델은 다음 요청에 적용됩니다.');
            $('ai-model-status').textContent = status.join(' · ');
            $('ai-model-status').hidden = !status.length;
            const unavailable = document.createDocumentFragment();
            for (const item of modelChoices.filter(choice => !choice.available)) {
                const reason = document.createElement('li'); reason.textContent = `${item.provider} / ${item.label}: ${item.reason || '현재 사용할 수 없습니다.'}`; unavailable.append(reason);
            }
            $('ai-unavailable-model-reasons').replaceChildren(unavailable);
            $('ai-unavailable-models').hidden = !modelChoices.some(choice => !choice.available);
            if (capabilities) root.querySelectorAll('[data-tool]').forEach(button => {
                button.hidden = !model || !model.tools || !(capabilities.tools || []).includes(button.dataset.tool) || button.dataset.write && !capabilities.writes || button.dataset.own === 'true' && !(capabilities.scopes || []).includes('my');
            });
            $('ai-send').disabled = modelUnavailable || changingModel || openingConversation || Boolean(activeJob) || readOnly() || lifecycleBusy || creatingConversation;
            lifecycleControls();
        }

        /** [Role] Shares one pending backend inventory read while keeping an existing saved choice intact.
         * [Dependencies] Sanitized same-origin models API and current conversation selection.
         * [Impact] Inventory changes never silently replace a saved unavailable model; repeated refreshes cannot race inventories, loading preserves button text/size and failures release the control with near-composer feedback without discarding the last inventory. Success clears only an inventory-owned global notice.
         */
        async function loadModels() {
            if (modelsPromise) return modelsPromise;
            if (disposed) return;
            loadingModels = true; inventoryError = ''; modelControls();
            modelsPromise = (async () => {
                try {
                    const result = await api('/api/ai/models');
                    if (disposed) return;
                    modelChoices = result.models; defaultModel = result.default_model;
                    if (!modelId) { modelId = result.default_model; const model = modelChoices.find(item => item.id === modelId); modelControls(initialLevel(model)); }
                    else modelControls();
                    notice('', 'inventory');
                } catch (error) {
                    inventoryError = error.message;
                    throw error;
                } finally {
                    loadingModels = false; modelsPromise = null;
                    if (!disposed) modelControls();
                }
            })();
            return modelsPromise;
        }

        /** [Role] Persists next-turn selection with optimistic concurrency and clears only its own recovered notice; an in-flight request is unaffected. */
        async function saveSelection() {
            if (readOnly() || lifecycleBusy) return;
            requestKey = null;
            if (!conversation) { modelControls(); return; }
            changingModel = true; $('ai-model').disabled = true; $('ai-send').disabled = true;
            try {
                const result = await api(`/api/ai/conversations/${conversation}/selection`, { method: 'POST', data: { selection_id: modelId, level: $('ai-level').value, revision: modelRevision, reasoning_version: 2 } });
                modelRevision = result.revision;
                unattributedSelection = false;
                notice('', 'selection');
            } finally { changingModel = false; if (!disposed) { $('ai-model').disabled = false; modelControls(); } }
        }

        /** [Role] Labels each answer from its immutable accepted route.
         * [Dependencies] Server provenance projection and an existing owner message node.
         * [Impact] Provider renames and next-turn choices cannot relabel older answers.
         */
        function sourceLabel(messageId, source) {
            if (!source || !nodes.has(messageId)) return;
            const node = nodes.get(messageId);
            let label = node.article.querySelector('.ai-source');
            if (!label) { label = document.createElement('p'); label.className = 'ai-source'; node.article.append(label); }
            label.textContent = `${source.provider_name} / ${source.model_label} · ${source.reasoning_effort === 'none' ? 'off' : source.reasoning_effort || '모델 기본값'}`;
        }

        /** [Role] Explains the baseline and extra storage separately from errors.
         * [Dependencies] Authenticated server-side message accounting, including reserved future output.
         * [Impact] Existing results remain readable when new requests are blocked for space.
         */
        function storageNotice(storage) {
            if (!storage) return;
            const target = $('ai-storage-notice');
            target.hidden = !storage.above_base;
            target.textContent = `대화 보관량이 기준 ${storage.base_chars.toLocaleString()}자를 넘었습니다. 추가 예산을 포함한 ${storage.total_chars.toLocaleString()}자 중 ${storage.used_chars.toLocaleString()}자를 보관하고 있습니다. 생성 결과를 보존하며, 완료에 필요한 공간이 부족하면 새 요청이 제한됩니다.`;
        }

        /** [Role] Adds browser credentials/CSRF only to fixed application paths; reads are passive activity. */
        async function api(path, { method = 'GET', data, form } = {}) {
            const headers = { 'X-Assistant-Poll': method === 'GET' ? '1' : '0' };
            if (method !== 'GET') headers['X-CSRFToken'] = csrf;
            if (data !== undefined) headers['Content-Type'] = 'application/json';
            let response;
            try {
                response = await fetch(path, { method, headers, body: form || (data === undefined ? undefined : JSON.stringify(data)),
                    credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal });
            } catch (_) {
                throw Object.assign(new Error(method === 'GET' ? '연결 상태를 확인해 주세요.' : '서버의 처리 결과를 확인하지 못했습니다.'), { outcomeUnknown: method !== 'GET', status: 0 });
            }
            const context = response.headers.get('X-Assistant-Account');
            if (response.status === 401 || response.status === 403 && method === 'GET' && !context || context && accountContext && context !== accountContext) {
                resetFileWorkspace(); disposed = true; clearTimeout(timer); nodes.clear(); streams.clear(); cards.clear(); root.replaceChildren();
                window.location.assign(response.status === 401 ? '/login' : response.status === 403 ? '/portal' : '/assistant');
                throw new Error('로그인 상태가 변경되었습니다.');
            }
            if (context) accountContext = context;
            let result;
            try { result = await response.json(); } catch (_) { throw Object.assign(new Error('응답을 읽을 수 없습니다. 연결 상태를 확인해 주세요.'), { outcomeUnknown: method !== 'GET', status: response.status }); }
            if (!result || typeof result !== 'object' || Array.isArray(result)) throw Object.assign(new Error('올바른 서버 응답을 확인하지 못했습니다.'), { outcomeUnknown: method !== 'GET', status: response.status });
            if (!response.ok || result.success === false || result.error && result.success !== true) throw Object.assign(new Error(typeof result.message === 'string' ? result.message : typeof result.error === 'string' ? result.error : '요청을 처리하지 못했습니다.'), { status: response.status, code: result.code || result.error_code, outcomeUnknown: method !== 'GET' && response.status >= 500 });
            return result;
        }

        /** [Role] Follows new output only when the reader is already near the bottom. */
        function follow(action) {
            const pane = $('ai-scroll');
            const near = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 100;
            const position = pane.scrollTop;
            action();
            if (near) pane.scrollTop = pane.scrollHeight;
            else pane.scrollTop = position;
        }

        /** [Role] Creates stable message nodes so a poll cannot reset an expanded native details element. */
        function messageNode(message) {
            if (nodes.has(message.id)) return nodes.get(message.id);
            const article = document.createElement('article'); article.className = 'ai-message'; article.dataset.role = message.role;
            const speaker = document.createElement('div'); speaker.className = 'ai-speaker'; speaker.textContent = message.role === 'user' ? '나' : 'AI 도우미';
            const details = document.createElement('details'); details.className = 'ai-thought'; details.hidden = true;
            const summary = document.createElement('summary'); summary.textContent = '추론 과정';
            const thought = document.createElement('div'); thought.className = 'ai-thought-text'; details.append(summary, thought);
            const answer = document.createElement('div'); answer.className = 'ai-answer';
            article.append(speaker); if (message.role !== 'user') article.append(details); article.append(answer);
            $('ai-messages').append(article);
            const node = { article, details, summary, thought, answer, content: null };
            nodes.set(message.id, node);
            return node;
        }

        /** [Role] Hydrates stored user/assistant text safely and keeps raw reasoning out of the answer block. */
        function hydrate(message) {
            const node = messageNode(message);
            if (message.role === 'user') node.answer.textContent = message.content;
            else {
                node.thought.textContent = message.reasoning;
                node.details.hidden = !message.reasoning;
                let visible = message.content;
                if (message.job === null && /^장비관리 서버 확인 완료 \[[a-f0-9]{32}\]: /.test(visible)) {
                    try { visible = '장비관리 서버 확인 완료\n' + resultText(JSON.parse(visible.slice(visible.indexOf(']: ') + 3))); }
                    catch (_) { visible = '처리 결과를 불러오지 못했습니다. 확인 카드를 다시 열어 주세요.'; }
                }
                markdown(node.answer, visible);
                if (message.job) streams.set(message.job, { messageId: message.id, reasoning: message.reasoning, content: message.content,
                    r: Array.from(message.reasoning).length, c: Array.from(message.content).length, generation: null,
                    answerStarted: Boolean(message.content) });
            }
        }

        /** [Role] Formats only frozen data fields for a review card, never privileged instructions. */
        function display(value, key = '') {
            const choices = { status: { ACTIVE: '정상', LOANED: '대여', REPAIR: '수리', PENDING: '승인 대기' },
                scope: { my: '내 장비', public: '공개 장비', draft: '임시저장 장비' }, kind: { category: '카테고리', manufacturer: '제조사', node: '라인업' },
                theme: { light: '밝은 화면', dark: '어두운 화면', system: '기기 설정에 맞춤' } };
            if (choices[key] && Object.hasOwn(choices[key], value)) return choices[key][value];
            if (Array.isArray(value)) return value.map(item => display(item)).join(', ');
            if (typeof value === 'object' && value !== null) return Object.entries(value).map(([name, item]) => `${fields[name] || name}: ${display(item, name)}`).join('\n');
            return value === true ? '예' : value === false ? '아니요' : value === null || value === '' ? '미설정' : String(value);
        }

        /** [Role] Projects confirmed business results into readable text without internal receipt identifiers. */
        function resultText(result) {
            const output = [result.message || '처리가 완료되었습니다.'];
            const names = { equipment_id: '장비 번호', request_id: '신청 번호', status: '처리 상태' };
            for (const [key, label] of Object.entries(names)) if (Object.hasOwn(result, key)) output.push(`${label}: ${display(result[key], key)}`);
            return output.join('\n');
        }

        /** [Role] Summarizes only validated CSV business columns and row errors in ordinary user language. */
        function csvPreviewText(result) {
            const errors = result.errors || [];
            if (errors.length) return '등록 전에 아래 내용을 수정해 주세요.\n' + errors.map(item => `${item.row}행: ${item.message}`).join('\n');
            const names = { Name: '장비 이름', OptionId: '옵션 번호', SerialNumber: '시리얼 번호', PurchaseDate: '구입일',
                WarrantyEndDate: '보증 종료일', ReplacementDueDate: '교체 예정일', IsPublic: '공개 여부', Memo: '메모' };
            const rows = (result.rows || []).slice(0, 10).map((row, index) => `${index + 1}. ` + Object.entries(names).filter(([key]) => row[key] !== '' && row[key] != null)
                .map(([key, label]) => `${label}: ${key === 'IsPublic' ? Number(row[key]) === 1 ? '공개' : '비공개' : display(row[key])}`).join(' · '));
            return `등록할 장비 ${result.count}개\n` + rows.join('\n') + (result.count > 10 ? '\n미리보기는 처음 10행입니다. 선택한 원본 전체가 등록됩니다.' : '');
        }

        /** [MINI-COMMENT: ASSISTANT.UI.PROPOSAL.CARD]
         * [EN rev.2]
         * [Role] Renders server proposals with operation-specific field labels; confirms only an opaque ID.
         * [Dependencies] Frozen payload kind and the server-owned operation, never model HTML.
         * [Impact] Catalog names retain their meaning; trash/unknown lifecycle views cannot execute pending cards and restoration never replays cancelled work.
         */
        function proposalCard(proposal) {
            const previous = cards.get(proposal.id);
            const version = proposal.state + (proposal.result || '') + String(readOnly());
            if (previous && previous.version === version) return;
            const card = previous?.element || document.createElement('section'); card.className = 'ai-proposal';
            const title = document.createElement('h3'); title.textContent = labels[proposal.operation] || '작업 내용 확인';
            const note = document.createElement('p');
            const applied = proposal.state === 'applied';
            note.textContent = applied ? '장비관리 서버에서 처리한 실제 결과입니다.' : readOnly() ? '읽기 전용 대화입니다. 이 작업을 실행할 수 없습니다. 취소된 작업은 복구해도 다시 실행되지 않습니다.' : proposal.state === 'pending' ? '아직 적용되지 않았습니다. 내용을 확인한 뒤 실행해 주세요.' : proposal.state === 'superseded' ? '수정한 새 확인 카드로 대체되었습니다. 이 항목은 실행할 수 없습니다.' : '확인 기한이 만료되었거나 취소된 항목입니다. 새로 요청해 주세요.';
            const list = document.createElement('dl');
            let payload = {}, before = {};
            try { payload = JSON.parse(proposal.payload); before = JSON.parse(proposal.before_json); } catch (_) { note.textContent = '확인 내용을 읽지 못했습니다.'; }
            for (const [key, value] of Object.entries(payload)) {
                if (!(key in fields)) continue;
                const term = document.createElement('dt');
                term.textContent = key === 'name' && proposal.operation === 'catalog_request'
                    ? ({ category: '카테고리 이름', manufacturer: '제조사 이름', node: '라인업 이름' }[payload.kind] || '신청 이름')
                    : fields[key];
                const description = document.createElement('dd');
                description.textContent = (Object.hasOwn(before, key) && display(before[key], key) !== display(value, key) ? display(before[key], key) + ' → ' : '') + display(value, key);
                list.append(term, description);
            }
            card.replaceChildren(title, note, list);
            if (before._selected_option) {
                const option = before._selected_option;
                const selected = document.createElement('p'); selected.textContent = `선택 옵션: ${option.official_model_name || option.model} / ${option.option_name} (번호 ${option.id})`;
                card.append(selected);
            }
            if (applied) {
                const result = JSON.parse(proposal.result || '{}');
                const text = document.createElement('p'); text.textContent = resultText(result); text.style.whiteSpace = 'pre-line'; card.append(text);
                if (fileWorkspaceTarget(result.download_url)?.panel === 'csv-export') {
                    const link = document.createElement('a'); link.href = result.download_url; link.className = 'ai-button'; link.textContent = 'CSV 다운로드'; card.append(workspaceLink(link, result.download_url));
                }
            } else if (proposal.state === 'pending' && !readOnly()) {
                const execute = document.createElement('button'); execute.type = 'button'; execute.className = 'ai-confirm'; execute.textContent = '이 내용으로 실행';
                execute.disabled = proposal.expires * 1000 < Date.now();
                execute.dataset.expires = String(proposal.expires);
                execute.addEventListener('click', async () => {
                    if (readOnly() || lifecycleBusy || execute.disabled) return;
                    const selected = selection;
                    execute.disabled = true; notice();
                    try {
                        const result = await api(`/api/ai/proposals/${proposal.id}/confirm`, { method: 'POST', data: {} });
                        if (selected === selection) proposalCard({ ...proposal, state: 'applied', result: JSON.stringify(result.result) });
                    } catch (error) { if (selected === selection) notice(error.message); execute.disabled = readOnly() || lifecycleBusy; }
                });
                card.append(execute);
            }
            if (!previous) $('ai-proposals').append(card);
            cards.set(proposal.id, { element: card, version });
        }

        /** [Role] Displays only app-local queue position and observable own-request progress. */
        function progress(job) {
            const states = { queued: `장비관리 요청 대기 · 내부 순서 ${job.position || '확인 중'}`, running: '응답을 기다리거나 생성하고 있습니다.',
                draining: '작업 중단됨 · 이 요청의 응답 종료를 확인하고 있습니다.', recovery_required: '작업 중단됨 · 이 요청의 종료 확인이 필요합니다. 관리자에게 문의해 주세요.',
                waiting_confirmation: '변경할 내용을 확인해 주세요.', failed: '작업 중단됨 · 응답을 완료하지 못했습니다.', cancelled: '작업을 중단했습니다. 이미 적용된 결과는 유지됩니다.', done: '' };
            const explanation = ['failed','cancelled','draining','recovery_required'].includes(job.state) && job.error ? ' ' + job.error : '';
            $('ai-progress').hidden = !states[job.state]; $('ai-progress-text').textContent = (job.worker_stale && job.state === 'running' ? '처리 작업자의 연결 상태를 확인하고 있습니다.' : states[job.state] || '') + explanation;
            const busy = !terminal.has(job.state);
            $('ai-cancel').hidden = !['queued','running'].includes(job.state);
            $('ai-send').disabled = busy || modelUnavailable || changingModel || openingConversation || readOnly() || lifecycleBusy;
            $('ai-input').disabled = readOnly() || lifecycleBusy;
            $('ai-progress').querySelector('.ai-pulse').hidden = !['queued','running'].includes(job.state);
        }

        /** [Role] Renders separate owner list views and names every lifecycle action for keyboard/screen-reader use. */
        function renderConversations() {
            const fragment = document.createDocumentFragment();
            const items = [...history[historyView].items.values()].sort((a,b) => (historyView === 'trash' ? (b.deleted_at || 0) - (a.deleted_at || 0) : (b.updated || 0) - (a.updated || 0)) || b.id.localeCompare(a.id));
            for (const item of items) {
                const row = document.createElement('div'); row.className = 'ai-conversation-row';
                const button = document.createElement('button'); button.type = 'button'; button.className = 'ai-conversation';
                button.textContent = item.title; button.title = item.title; button.setAttribute('aria-current', String(item.id === conversation));
                button.dataset.conversationId = item.id;
                const view = historyView;
                button.addEventListener('click', () => { if (!lifecycleBusy && !changingModel) open(item.id, view).catch(error => notice(error.message)); }); row.append(button);
                if (historyView === 'trash') {
                    const dates = document.createElement('p'); dates.className = 'ai-conversation-dates';
                    const remaining = typeof item.purge_after === 'number' ? Math.max(0, Math.ceil((item.purge_after * 1000 - Date.now()) / 86400000)) : null;
                    dates.textContent = `이동 ${lifecycleDate(item.deleted_at)}\n만료 ${lifecycleDate(item.purge_after)}${remaining === null ? '' : remaining ? ` · 약 ${remaining}일 남음` : ' · 보관 만료'}`; row.append(dates);
                }
                const actions = document.createElement('div'); actions.className = 'ai-conversation-row-actions';
                for (const action of historyView === 'trash' ? ['restore', 'purge'] : ['trash']) {
                    const control = document.createElement('button'); control.type = 'button'; control.className = 'ai-conversation-action' + (action === 'purge' ? ' ai-danger' : '');
                    control.textContent = { trash: '휴지통', restore: '복구', purge: '영구삭제' }[action];
                    control.setAttribute('aria-label', `${item.title} · ${{ trash: '휴지통으로 이동', restore: '복구', purge: '영구삭제' }[action]}`);
                    control.dataset.conversationId = item.id; control.dataset.lifecycleAction = action;
                    control.addEventListener('click', () => mutateLifecycle(action, item).catch(error => notice(error.message))); actions.append(control);
                }
                row.append(actions); fragment.append(row);
            }
            $('ai-conversations').replaceChildren(fragment);
            $('ai-active-tab').setAttribute('aria-pressed', String(historyView === 'active'));
            $('ai-trash-tab').setAttribute('aria-pressed', String(historyView === 'trash'));
            $('ai-history-title').textContent = historyView === 'trash' ? '휴지통' : '최근 대화';
            $('ai-conversations').setAttribute('aria-label', historyView === 'trash' ? '휴지통 대화 목록' : '대화 목록');
            $('ai-trash-help').hidden = historyView !== 'trash';
            $('ai-list-empty').hidden = Boolean(items.length); $('ai-list-empty').textContent = historyView === 'trash' ? '휴지통이 비어 있습니다.' : '저장된 대화가 없습니다.';
            $('ai-more-conversations').hidden = !history[historyView].cursor;
            lifecycleControls();
        }

        /** [MINI-COMMENT: ASSISTANT.CLIENT.HISTORY]
         * [EN rev.3]
         * [Role] Serializes each active/trash cursor chain and replaces stale entries on refresh.
         * [Dependencies] Owner/account-scoped list API, per-view request queues and retained loaded-ID boundaries.
         * [Impact] A background refresh cannot discard an in-flight explicit older-page load; deletion/restore refreshes still remove stale entries, failed refreshes retain the last known list, and a missing selected title clears through the accessible-heading path.
         */
        function conversations(more = false) {
            const view = historyView, state = history[view];
            const next = (state.pending || Promise.resolve()).catch(() => {}).then(() => loadConversationPages(view, more));
            state.pending = next;
            return next.finally(() => { if (state.pending === next) state.pending = null; });
        }

        /** [Role] Reads one serialized view request using the latest completed cursor/depth, never an older in-flight snapshot. */
        async function loadConversationPages(view, more) {
            if (disposed) return [];
            const state = history[view], request = ++state.request;
            let cursor = more ? state.cursor : null;
            if (more && !cursor) return [];
            const entries = more ? new Map(state.items) : new Map();
            let first = [], pages = 0;
            const depth = more ? 1 : state.depth;
            const retained = new Set(more ? [] : state.items.keys()), seenCursors = new Set();
            for (let index = 0; index < depth || retained.size; index++) {
                if (cursor && seenCursors.has(cursor)) throw new Error('대화 목록을 갱신하지 못했습니다. 잠시 뒤 다시 확인해 주세요.');
                if (cursor) seenCursors.add(cursor);
                const result = await api(`/api/ai/conversations?view=${view}${cursor ? '&cursor=' + encodeURIComponent(cursor) : ''}`);
                if (request !== state.request || disposed) return [];
                if (!index) first = result.conversations;
                for (const item of result.conversations) { entries.set(item.id, item); retained.delete(item.id); }
                cursor = result.next_cursor || null; pages++;
                if (!cursor) break;
            }
            const changed = JSON.stringify([...state.items]) !== JSON.stringify([...entries]) || state.cursor !== cursor;
            state.items = entries; state.cursor = cursor; state.depth = more ? state.depth + pages : pages;
            if (view === historyView && (changed || !$('ai-conversations').childElementCount)) renderConversations();
            return first;
        }

        /** [Role] Changes only the sidebar view; a selected trash conversation stays read-only until explicitly restored. */
        async function changeHistoryView(view) {
            if (lifecycleBusy || openingConversation) return;
            historyView = view; renderConversations();
            try { await conversations(); } catch (error) { notice(error.message); }
        }

        /** [Role] Reads both permitted views without treating a missing target as proof of permanent deletion. */
        async function readLifecycle(cid, preferred = conversationView) {
            for (const view of [preferred, preferred === 'trash' ? 'active' : 'trash']) {
                try { return { view, result: await api(`/api/ai/conversations/${cid}/messages?view=${view}`) }; }
                catch (error) { if (![404, 409, 410].includes(error.status)) throw error; }
            }
            return null;
        }

        /** [Role] Clears an unavailable selected chat without creating a new conversation or replaying any cancelled work. */
        function clearConversation() {
            resetFileWorkspace();
            ++selection; clearTimeout(timer); conversation = null; conversationMeta = null; conversationView = 'active'; activeJob = null; nextBefore = null;
            nodes.clear(); streams.clear(); cards.clear(); requestKey = null;
            $('ai-messages').replaceChildren(); $('ai-proposals').replaceChildren(); setConversationTitle('대화를 선택해 주세요.');
            $('ai-welcome').hidden = false; $('ai-progress').hidden = true; $('ai-more-messages').hidden = true;
            modelControls();
        }

        /** [Role] Revalidates server lifecycle metadata on return/reconnect and replaces only a changed selected chat. */
        async function refreshLifecycle() {
            if (disposed || syncingLifecycle || lifecycleBusy || openingConversation) return;
            syncingLifecycle = true; lifecycleControls();
            const cid = conversation, selected = selection;
            try {
                if (cid) {
                    const current = await readLifecycle(cid);
                    if (selected !== selection || disposed) return;
                    if (!current) { clearConversation(); notice('이 대화는 현재 열 수 없습니다. 목록을 갱신했습니다.'); }
                    else if (current.view !== conversationView || current.result.conversation.lifecycle_revision !== conversationMeta?.lifecycle_revision) {
                        await open(cid, current.view, { preserveReader: true, result: current.result, refreshList: false });
                        notice(current.view === 'trash' ? '다른 화면에서 휴지통으로 이동한 대화입니다. 읽기 전용으로 표시합니다.' : '서버에서 변경된 대화 상태를 반영했습니다. 취소된 작업은 다시 실행하지 않습니다.');
                    }
                }
                await conversations();
            } finally { syncingLifecycle = false; if (!disposed) lifecycleControls(); }
        }

        /** [Role] Broadcasts only an invalidation hint; every receiving tab rereads its own authenticated server state. */
        function announceLifecycle(cid) {
            const hint = { account: accountContext, conversation: cid, nonce: crypto.randomUUID() };
            if (lifecycleChannel) { try { lifecycleChannel.postMessage(hint); } catch (_) { /* Return/focus polling also invalidates stale views. */ } }
            else { try { localStorage.setItem('eqmgmt.ai.lifecycle', JSON.stringify(hint)); } catch (_) { /* Focus/visibility revalidation remains available. */ } }
        }

        /** [MINI-COMMENT: ASSISTANT.CLIENT.LIFECYCLE]
         * [EN rev.2]
         * [Role] Submits one explicitly intended trash/restore/purge operation with a server revision and stable operation ID.
         * [Dependencies] Existing same-origin CSRF/account boundary, native dialogs and server-owned lifecycle timestamps.
         * [Impact] Duplicate clicks lock; replay receipts retain the current server state, ACK/GET failure and ambiguous writes remain distinct, and restoration never replays turns/proposals.
         */
        async function mutateLifecycle(action, item, retry = null) {
            if (lifecycleBusy || lifecycleIntent || openingConversation || changingModel || dialogResolve || disposed) return;
            if (item && uncertainLifecycle.has(item.id) && !retry) { notice('이 대화의 이전 처리 결과를 먼저 확인해 주세요.'); return; }
            if (!item || !Number.isSafeInteger(item.lifecycle_revision) || item.lifecycle_revision < 0) { notice('대화 상태를 먼저 새로 확인해 주세요.'); await refreshLifecycle(); return; }
            const title = String(item.title || '제목 없는 대화');
            const names = { trash: '휴지통으로 이동', restore: '복구', purge: '영구삭제' };
            if (action !== 'restore' || retry) {
                lifecycleIntent = true;
                const confirmed = await lifecycleDialog({ title: `${names[action]} 확인`, message: `“${title}” 대화를 ${action === 'trash' ? '휴지통으로 옮길까요?' : action === 'restore' ? '복구할까요?' : '영구삭제할까요?'}`,
                    detail: retry ? '같은 조작 식별자로 다시 보냅니다. 아직 처리되지 않았다면 지금 적용됩니다. 영구삭제한 대화는 앱에서 복구할 수 없습니다.' : action === 'trash' ? '이동 시점부터 30일간 보관됩니다. 대기 요청과 미확정 작업은 취소되며, 이미 적용한 장비 업무는 유지됩니다.' : `만료 예정: ${lifecycleDate(item.purge_after)}. 앱의 대화 저장소에서 복구할 수 없게 제거합니다. 별도 감사 기록과 운영 백업은 기존 정책에 따라 남을 수 있습니다.`,
                    confirm: retry ? '같은 요청 다시 보내기' : names[action], cancel: true, danger: action === 'purge' });
                lifecycleIntent = false;
                if (!confirmed || disposed) return;
            }
            lifecycleBusy = true; modelControls();
            lifecycleDialog({ title: `${names[action]} 중`, message: `“${title}” 대화를 처리하고 있습니다.`, busy: true });
            const operation = retry || { action, id: item.id, title, lifecycle_revision: item.lifecycle_revision, operation_id: crypto.randomUUID().replaceAll('-', '') };
            let acknowledged = false, refreshError = null;
            try {
                const result = await api(`/api/ai/conversations/${item.id}/${action}`, { method: 'POST', data: { lifecycle_revision: operation.lifecycle_revision, operation_id: operation.operation_id } });
                if (action === 'purge' ? result.purged !== true : result.purged !== true && (!result.conversation || !Number.isSafeInteger(result.conversation.lifecycle_revision) || ![0,1,false,true].includes(result.conversation.is_deleted))) throw Object.assign(new Error('서버의 처리 확인 정보를 읽지 못했습니다.'), { outcomeUnknown: true });
                acknowledged = true; uncertainLifecycle.delete(item.id); announceLifecycle(item.id);
                storageNotice(result.storage);
                let currentMeta = result.purged ? null : result.conversation;
                let currentView = currentMeta?.is_deleted ? 'trash' : 'active';
                let snapshot = null;
                if (!result.purged) {
                    try {
                        const current = await readLifecycle(item.id, currentView);
                        currentMeta = current?.result.conversation || null;
                        currentView = current?.view || currentView; snapshot = current?.result || null;
                    } catch (error) { refreshError = error; }
                }
                history.active.items.delete(item.id); history.trash.items.delete(item.id);
                if (currentMeta) history[currentView].items.set(item.id, currentMeta);
                if (conversation === item.id) {
                    if (!currentMeta) clearConversation();
                    else {
                        conversationMeta = currentMeta; conversationView = currentView; historyView = currentView;
                        clearTimeout(timer); activeJob = null; ++selection; requestKey = null; cards.clear(); $('ai-proposals').replaceChildren();
                        if (snapshot) {
                            try { await open(item.id, currentView, { preserveReader: true, result: snapshot, refreshList: false }); } catch (error) { refreshError = error; }
                        }
                    }
                }
                try { await conversations(); } catch (error) { refreshError = error; }
                renderConversations();
                const stateText = result.purged ? '현재 앱의 대화 저장소에서 영구삭제된 상태이며 휴지통에서도 복구할 수 없습니다.' : !currentMeta ? '현재 이 대화를 열 수 없습니다. 목록에서 최신 상태를 확인해 주세요.' : currentView === 'trash' ? `현재 휴지통에 있습니다. 자동 삭제 예정: ${lifecycleDate(currentMeta.purge_after)}. 30일 안에 복구할 수 있습니다.` : '현재 정상 대화 목록에 있습니다. 취소된 요청과 작업은 다시 실행되지 않습니다. 새 질문은 직접 보낼 수 있습니다.';
                await lifecycleDialog({ title: result.replayed ? '기처리 요청 확인' : `${names[action]} 완료`, message: result.replayed ? `“${title}” 대화의 같은 요청은 이미 처리되었습니다. 이 요청으로 현재 상태를 다시 바꾸지 않았습니다.` : `“${title}” 대화의 ${names[action]} 처리가 완료되었습니다.`,
                    detail: stateText + (refreshError ? ' 요청 처리는 확인했으나 화면 새로고침을 완료하지 못했습니다. 목록을 다시 확인해 주세요.' : '') });
            } catch (error) {
                if (disposed) return;
                if (!acknowledged && error.outcomeUnknown) uncertainLifecycle.set(item.id, operation);
                if (!acknowledged && !error.outcomeUnknown && [404,409,410].includes(error.status)) {
                    try {
                        const current = await readLifecycle(item.id);
                        if (conversation === item.id) { if (current) await open(item.id, current.view, { preserveReader: true, result: current.result, refreshList: false }); else clearConversation(); }
                        await conversations();
                    } catch (_) { /* The error dialog retains the unresolved refresh instead of claiming a state. */ }
                }
                await lifecycleDialog({ title: error.outcomeUnknown ? '처리 결과 확인 필요' : '처리하지 못했습니다.', message: `“${title}” · ${error.message}`,
                    detail: error.outcomeUnknown ? '요청을 자동으로 다시 보내지 않습니다. 처리 결과 확인에서 서버 상태를 읽거나, 같은 요청을 직접 다시 보낼 수 있습니다.' : error.status === 409 ? '다른 탭에서 상태가 바뀌었습니다. 갱신된 상태를 확인한 뒤 다시 선택해 주세요.' : '입력과 기존 대화는 유지됩니다. 서버 상태를 확인한 뒤 다시 시도해 주세요.' });
            } finally {
                lifecycleBusy = false;
                if (!disposed) { modelControls(); renderConversations(); restoreDialogFocus(); if (invalidationPending) { invalidationPending = false; refreshLifecycle().catch(error => notice(error.message)); } }
            }
        }

        /** [Role] Reconciles ambiguous writes using GET first; only a second explicit confirmation can resend the same operation. */
        async function reconcileLifecycle() {
            if (lifecycleBusy || lifecycleIntent || syncingLifecycle || dialogResolve || !uncertainLifecycle.size) return;
            const operation = uncertainLifecycle.values().next().value;
            syncingLifecycle = true; lifecycleControls();
            let current;
            try { current = await readLifecycle(operation.id, operation.action === 'trash' ? 'trash' : 'active'); }
            catch (error) { notice(error.message); return; }
            finally { syncingLifecycle = false; lifecycleControls(); }
            const changed = current && current.result.conversation.lifecycle_revision > operation.lifecycle_revision;
            if (changed) {
                uncertainLifecycle.delete(operation.id);
                if (conversation === operation.id) await open(operation.id, current.view, { preserveReader: true, result: current.result });
                else await conversations();
                modelControls();
                await lifecycleDialog({ title: '현재 상태 확인', message: `“${operation.title}” 대화는 현재 ${current.view === 'trash' ? '휴지통에 있습니다.' : '정상 대화 목록에 있습니다.'}`, detail: '서버에서 현재 상태를 확인했습니다. 이전 요청이나 취소된 작업을 자동으로 다시 실행하지 않았습니다.' });
                return;
            }
            await mutateLifecycle(operation.action, { id: operation.id, title: operation.title, lifecycle_revision: operation.lifecycle_revision }, operation);
        }

        /** [Role] Prepends an older page without replacing live nodes or moving the reader.
         * [Dependencies] Owner-scoped before IDs and a conversation selection guard.
         * [Impact] Every retained message is reachable; stale responses cannot enter another conversation.
         */
        async function olderMessages() {
            if (!nextBefore || loadingHistory) return;
            const selected = selection, cid = conversation;
            loadingHistory = true; $('ai-more-messages').disabled = true;
            try {
                const result = await api(`/api/ai/conversations/${cid}/messages?view=${conversationView}&before=${nextBefore}`);
                if (selected !== selection || disposed) return;
                const pane = $('ai-scroll'), height = pane.scrollHeight, position = pane.scrollTop;
                const anchor = $('ai-messages').firstChild;
                for (const message of result.messages) if (!nodes.has(message.id)) {
                    hydrate(message); $('ai-messages').insertBefore(nodes.get(message.id).article, anchor);
                }
                for (const item of result.proposals) proposalCard(item);
                nextBefore = result.next_before; $('ai-more-messages').hidden = !nextBefore;
                pane.scrollTop = position + pane.scrollHeight - height;
            } finally { loadingHistory = false; $('ai-more-messages').disabled = false; }
        }

        /** [MINI-COMMENT: ASSISTANT.CLIENT.OPEN]
         * [EN rev.2]
         * [Role] Hydrates a selected conversation before enabling its composer; the sidebar refresh runs independently.
         * [Dependencies] Owner snapshot, selection generation and the serialized history queue.
         * [Impact] A delayed/background list read cannot swallow a ready user's submit; unchanged lifecycle checks preserve drafts, streams, active jobs and message nodes, while the compact heading exposes the complete selected title.
         */
        async function open(cid, view = historyView, { preserveReader = false, result: loaded = null, refreshList = true } = {}) {
            if (conversation !== cid || conversationView !== view) resetFileWorkspace();
            const pane = $('ai-scroll');
            const reader = preserveReader && conversation === cid ? { top: pane.scrollTop, thoughts: new Map([...nodes].map(([id,node]) => [id, { open: node.details.open, top: node.thought.scrollTop }])), tables: [...pane.querySelectorAll('.ai-table-scroll')].map(node => node.scrollLeft) } : null;
            const selected = ++selection; clearTimeout(timer); activeJob = null; nextBefore = null;
            openingConversation = true; root.setAttribute('aria-busy', 'true'); modelControls();
            try {
            $('ai-more-messages').hidden = true;
            const result = loaded || await api(`/api/ai/conversations/${cid}/messages?view=${view}`);
            if (selected !== selection || disposed) return;
            conversationMeta = result.conversation; conversationView = result.conversation.is_deleted ? 'trash' : view;
            conversation = cid; nodes.clear(); streams.clear(); cards.clear(); requestKey = null;
            unattributedSelection = !result.conversation.selection_id;
            modelId = result.conversation.selection_id || defaultModel;
            modelRevision = result.conversation.selection_revision || 0;
            modelControls(result.conversation.next_level || 'medium');
            nextBefore = result.next_before; $('ai-more-messages').hidden = !nextBefore; storageNotice(result.storage);
            $('ai-messages').replaceChildren(); $('ai-proposals').replaceChildren(); setConversationTitle(result.conversation.title);
            $('ai-welcome').hidden = Boolean(result.messages.length) || readOnly(); $('ai-progress').hidden = true;
            for (const message of result.messages) hydrate(message);
            for (const item of result.proposals) proposalCard(item);
            const job = !readOnly() && result.jobs.find(item => !terminal.has(item.state));
            for (const item of result.jobs) {
                const stream = streams.get(item.id);
                if (stream) stream.generation = item.steps + (['running','draining','recovery_required'].includes(item.state) ? 1 : 0);
                if (stream) stream.answerStarted ||= Boolean(item.answer_started);
                if (stream) sourceLabel(stream.messageId, item.source);
                if (stream && stream.reasoning && !stream.answerStarted && ['running','draining'].includes(item.state)) nodes.get(stream.messageId).details.open = true;
            }
            if (job) { activeJob = job.id; progress(job); schedule(100); }
            else if (!readOnly() && result.jobs[0]) progress(result.jobs[0]);
            modelControls(result.conversation.next_level || 'medium');
            if (reader) {
                for (const [id, state] of reader.thoughts) if (nodes.has(id)) { nodes.get(id).details.open = state.open; nodes.get(id).thought.scrollTop = state.top; }
                pane.querySelectorAll('.ai-table-scroll').forEach((node,index) => { node.scrollLeft = reader.tables[index] || 0; });
                pane.scrollTop = reader.top;
            } else pane.scrollTop = pane.scrollHeight;
            $('ai-sidebar').classList.remove('is-open'); $('ai-menu-toggle').setAttribute('aria-expanded', 'false');
            if (refreshList) {
                renderConversations();
                conversations().catch(error => { if (!disposed && selected === selection) notice(error.message); });
            }
            } finally {
                if (selected === selection) { openingConversation = false; modelControls(); }
            }
        }

        /** [Role] Schedules at most one poll; hidden tabs back off and terminal jobs stop polling. */
        function schedule(delay = 1500) { clearTimeout(timer); if (!disposed && activeJob && !readOnly()) timer = setTimeout(poll, document.hidden ? Math.max(5000, delay) : delay); }

        /** [MINI-COMMENT: ASSISTANT.CLIENT.STREAM]
         * [EN rev.5]
         * [Role] Applies separate deltas while preserving user-opened thoughts and scroll.
         * [Dependencies] Server generation/code-point cursors.
         * [Impact] Automatic close occurs once per turn; selected text, table scroll and manual reopening survive updates, remotely trashed chats stop polling, and a completed explicit new-chat action releases every composer/model lock. Model-setting/inventory errors own their notices so unrelated successful work cannot erase them.
         */
        async function poll() {
            if (polling || !activeJob || disposed || readOnly()) { schedule(); return; }
            polling = true;
            const jid = activeJob, selected = selection;
            try {
                const previous = streams.get(jid) || { messageId: null, reasoning: '', content: '', r: 0, c: 0, generation: 0, answerStarted: false };
                const result = await api(`/api/ai/jobs/${jid}?r=${previous.r}&c=${previous.c}&v=${previous.generation}`);
                if (selected !== selection || jid !== activeJob || disposed) return;
                const next = { ...mergeStream(previous, result), messageId: result.message_id };
                storageNotice(result.storage);
                streams.set(jid, next);
                follow(() => {
                    const node = messageNode({ id: result.message_id, role: 'assistant' });
                    const firstThought = !previous.reasoning && Boolean(next.reasoning);
                    node.thought.textContent = next.reasoning; node.details.hidden = !next.reasoning;
                    if (firstThought && !next.answerStarted) node.details.open = true;
                    if (next.closeThought) node.details.open = false;
                    node.summary.textContent = result.state === 'running' && !next.answerStarted ? '추론 중 · 접기/펼치기' : '추론 과정 · 다시 보기';
                    const streaming = !terminal.has(result.state);
                    if (next.content !== node.content || node.streaming !== streaming) { markdown(node.answer, next.content, { streaming }); node.content = next.content; node.streaming = streaming; }
                    sourceLabel(result.message_id, result.source);
                    for (const item of result.proposals) proposalCard(item);
                });
                progress(result); retryDelay = 1500;
                if (terminal.has(result.state) && next.r >= result.reasoning_length && next.c >= result.content_length) { activeJob = null; modelControls(); }
                else schedule(next.r < result.reasoning_length || next.c < result.content_length ? 100 : 1500);
            } catch (error) {
                if (!disposed && selected === selection) {
                    notice(error.message);
                    if ([404,409,410].includes(error.status)) { await refreshLifecycle(); if (selected !== selection || readOnly()) return; }
                    retryDelay = Math.min(retryDelay * 2, 15000); schedule(retryDelay);
                }
            } finally { polling = false; }
        }

        /** [Role] Creates a new account-local conversation only on explicit user intent. */
        async function newConversation() {
            if (lifecycleBusy || lifecycleIntent || openingConversation || changingModel || creatingConversation) return;
            creatingConversation = true;
            $('ai-new').disabled = true;
            try { const result = await api('/api/ai/conversations', { method: 'POST', data: {} }); historyView = 'active'; await open(result.id, 'active'); $('ai-input').focus(); }
            finally { creatingConversation = false; if (!disposed) modelControls(); }
        }

        /** [Role] Revalidates idle/returning screens too, so a different login cannot retain a prior account's DOM. */
        async function checkIdentity() {
            if (disposed || checkingIdentity || document.hidden) return;
            checkingIdentity = true;
            try { const result = await api('/api/ai/capabilities'); storageNotice(result.storage); await refreshLifecycle(); }
            catch (error) { if (!disposed) notice(error.message); }
            finally { checkingIdentity = false; }
        }

        $('ai-dialog-confirm').addEventListener('click', () => finishDialog(true));
        $('ai-dialog-cancel').addEventListener('click', () => finishDialog(false));
        $('ai-lifecycle-dialog').addEventListener('cancel', event => { event.preventDefault(); finishDialog(false); });
        $('ai-active-tab').addEventListener('click', () => changeHistoryView('active'));
        $('ai-trash-tab').addEventListener('click', () => changeHistoryView('trash'));
        $('ai-trash-current').addEventListener('click', () => mutateLifecycle('trash', conversationMeta).catch(error => notice(error.message)));
        $('ai-restore-current').addEventListener('click', () => mutateLifecycle('restore', conversationMeta).catch(error => notice(error.message)));
        $('ai-purge-current').addEventListener('click', () => mutateLifecycle('purge', conversationMeta).catch(error => notice(error.message)));
        $('ai-lifecycle-reconcile').addEventListener('click', () => reconcileLifecycle().catch(error => notice(error.message)));
        $('ai-new').addEventListener('click', () => newConversation().catch(error => notice(error.message)));
        $('ai-more-conversations').addEventListener('click', async () => {
            $('ai-more-conversations').disabled = true;
            try { await conversations(true); } catch (error) { notice(error.message); }
            finally { $('ai-more-conversations').disabled = false; }
        });
        $('ai-more-messages').addEventListener('click', () => olderMessages().catch(error => notice(error.message)));
        $('ai-menu-toggle').addEventListener('click', () => { const show = $('ai-sidebar').classList.toggle('is-open'); $('ai-menu-toggle').setAttribute('aria-expanded', String(show)); });
        $('ai-input').addEventListener('input', () => { requestKey = null; $('ai-input').style.height = 'auto'; $('ai-input').style.height = Math.min($('ai-input').scrollHeight, 160) + 'px'; });
        $('ai-level').addEventListener('change', () => { if (readOnly() || lifecycleBusy || openingConversation || changingModel) return; requestKey = null; $('ai-level-help').textContent = reasoningHelp[$('ai-level').value] || ''; saveSelection().catch(error => { modelUnavailable = true; $('ai-send').disabled = true; notice(error.message, 'selection'); }); });
        $('ai-model').addEventListener('change', () => { if (openingConversation || changingModel || readOnly() || lifecycleBusy) return; modelId = $('ai-model').value; const model = modelChoices.find(item => item.id === modelId); modelControls(initialLevel(model)); saveSelection().catch(error => { modelUnavailable = true; $('ai-send').disabled = true; notice(error.message, 'selection'); }); });
        $('ai-model-refresh').addEventListener('click', () => loadModels().catch(error => notice(error.message, 'inventory')));
        $('ai-input').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!$('ai-send').disabled) $('ai-form').requestSubmit(); } });
        root.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => { if (readOnly() || lifecycleBusy) return; $('ai-input').value = button.dataset.prompt; requestKey = null; $('ai-input').focus(); }));
        $('ai-form').addEventListener('submit', async event => {
            event.preventDefault(); if ($('ai-send').disabled || readOnly() || lifecycleBusy || lifecycleIntent || openingConversation) return;
            const content = $('ai-input').value.trim(); if (!content) return;
            $('ai-send').disabled = true; notice();
            try {
                if (!conversation) { const result = await api('/api/ai/conversations', { method: 'POST', data: {} }); conversation = result.id; modelRevision = result.selection_revision || 1; await saveSelection(); }
                requestKey ||= crypto.randomUUID().replaceAll('-', '');
                await api(`/api/ai/conversations/${conversation}/turns`, { method: 'POST', data: { content, level: $('ai-level').value, client_key: requestKey, selection_id: modelId, reasoning_version: 2 } });
                $('ai-input').value = ''; requestKey = null; await open(conversation, 'active');
            } catch (error) { notice(error.message); modelControls(); if ([404,409,410].includes(error.status)) await refreshLifecycle(); }
        });
        $('ai-cancel').addEventListener('click', async () => { if (!activeJob || readOnly() || lifecycleBusy) return; try { await api(`/api/ai/jobs/${activeJob}/cancel`, { method: 'POST', data: {} }); schedule(50); } catch (error) { notice(error.message); } });

        root.addEventListener('click', event => {
            const anchor = event.target.closest('a[data-ai-workspace]');
            if (!anchor || !root.contains(anchor)) return;
            event.preventDefault(); openFileWorkspace(anchor.dataset.aiWorkspace, anchor.dataset.aiScope, anchor);
        });
        $('ai-file-close').addEventListener('click', closeFileWorkspace);
        $('ai-file-dialog').addEventListener('cancel', event => { event.preventDefault(); closeFileWorkspace(); });
        $('ai-csv-download').addEventListener('click', event => {
            const target = fileWorkspaceTarget($('ai-csv-download').getAttribute('href'));
            if (readOnly() || lifecycleBusy || disposed || !target || !(capabilities?.scopes || []).includes(target.scope)) { event.preventDefault(); fileNotice('현재 권한과 대화 상태를 확인한 뒤 다시 요청해 주세요.'); }
        });

        /** [Role] Sends only a user-selected file from the requested popup to the existing own-equipment endpoint. */
        $('ai-upload-form').addEventListener('submit', async event => {
            event.preventDefault(); if (filePanel !== 'attachment') return;
            const id = Number($('ai-upload-equipment').value), file = $('ai-upload-file').files[0];
            if (!Number.isSafeInteger(id) || id < 1 || !file || file.size > 10 * 1024 * 1024) { fileNotice('장비 번호와 10MiB 이하 파일을 선택해 주세요.'); return; }
            const form = new FormData(); form.append('file', file);
            await fileOperation('파일을 업로드하고 있습니다.', async current => {
                await api(`/api/ai/equipment/${id}/files`, { method: 'POST', form });
                if (current()) $('ai-upload-file').value = '';
                return '선택한 파일이 첨부되었습니다.';
            }, { write: true });
        });
        /** [Role] Reuses the existing authenticated CSV preview token, never asks the model to parse a raw file. */
        $('ai-csv-form').addEventListener('submit', async event => {
            event.preventDefault(); if (fileBusy || filePanel !== 'csv-import') return;
            csvToken = null; $('ai-csv-confirm').hidden = true; $('ai-csv-preview').hidden = true;
            const file = $('ai-csv-file').files[0], version = ++csvFileVersion;
            if (!file || file.size > 1024 * 1024) { fileNotice('1MiB 이하 CSV 파일을 선택해 주세요.'); return; }
            const form = new FormData(); form.append('file', file);
            await fileOperation('CSV 파일의 등록 전 내용을 확인하고 있습니다.', async current => {
                const result = await api('/api/ai/csv/preview', { method: 'POST', form });
                if (!current() || version !== csvFileVersion || file !== $('ai-csv-file').files[0]) return;
                $('ai-csv-preview').textContent = csvPreviewText(result);
                $('ai-csv-preview').hidden = false; csvToken = typeof result.token === 'string' && result.token ? result.token : null; $('ai-csv-confirm').hidden = !csvToken;
                fileNotice(csvToken ? '등록 전 내용을 확인한 뒤 아래 버튼을 눌러 주세요.' : 'CSV 내용을 확인해 주세요. 오류가 있는 파일은 등록할 수 없습니다.');
            });
        });
        $('ai-csv-file').addEventListener('change', () => { ++csvFileVersion; csvToken = null; $('ai-csv-confirm').hidden = true; $('ai-csv-preview').hidden = true; });
        $('ai-csv-confirm').addEventListener('click', async () => {
            if (!csvToken || fileBusy || filePanel !== 'csv-import') return;
            const token = csvToken;
            await fileOperation('확인한 CSV 장비를 등록하고 있습니다.', async current => {
                try {
                    const result = await api('/api/ai/csv/commit', { method: 'POST', data: { token } });
                    if (current()) { csvToken = null; $('ai-csv-confirm').hidden = true; }
                    return `${result.count}개 장비가 등록되었습니다.`;
                } catch (error) {
                    if (current()) { csvToken = null; $('ai-csv-confirm').hidden = true; }
                    return error.outcomeUnknown ? 'CSV 등록 결과를 확인하지 못했습니다. 내 장비에서 반영 여부를 확인해 주세요. 자동으로 다시 등록하지 않습니다.' : error.message;
                }
            }, { write: true });
        });

        /** [Role] Treats cross-tab storage/channel data only as a hint to authenticated rereads. */
        function lifecycleHint(hint) {
            if (!hint || !accountContext || hint.account !== accountContext || disposed) return;
            if (lifecycleBusy || openingConversation || syncingLifecycle) { invalidationPending = true; return; }
            refreshLifecycle().catch(error => notice(error.message));
        }
        if (typeof BroadcastChannel !== 'undefined') {
            lifecycleChannel = new BroadcastChannel('eqmgmt-ai-lifecycle');
            lifecycleChannel.addEventListener('message', event => lifecycleHint(event.data));
        }
        window.addEventListener('storage', event => { if (event.key === 'eqmgmt.ai.lifecycle') { try { lifecycleHint(JSON.parse(event.newValue)); } catch (_) { /* Malformed hints have no authority. */ } } });
        window.addEventListener('pagehide', () => { disposed = true; disposeViewport(); clearTimeout(timer); clearInterval(identityTimer); lifecycleChannel?.close(); controller.abort(); }, { once: true });
        window.addEventListener('pageshow', event => { if (event.persisted) window.location.reload(); });
        window.addEventListener('focus', checkIdentity);
        document.addEventListener('visibilitychange', () => { if (!document.hidden) checkIdentity(); });
        try {
            capabilities = await api('/api/ai/capabilities');
            if (capabilities.reasoning_version !== 2) throw Error('AI 서버와 화면의 추론 설정 버전이 다릅니다. 화면과 서버를 함께 갱신해 주세요.');
            storageNotice(capabilities.storage);
            root.querySelectorAll('[data-write]').forEach(button => { button.hidden = !capabilities.writes; });
            root.querySelectorAll('[data-tool]').forEach(button => {
                button.hidden = !(capabilities.tools || []).includes(button.dataset.tool) || button.dataset.own === 'true' && !(capabilities.scopes || []).includes('my');
            });
            if (!capabilities.writes) notice('현재 조회와 대화 기능을 사용할 수 있습니다. 변경 제안은 운영 설정에서 비활성 상태입니다.');
            await loadModels();
            const list = await conversations(); if (list.length) await open(list[0].id);
            identityTimer = setInterval(checkIdentity, 10000);
        } catch (error) { notice(error.message); $('ai-send').disabled = true; }
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true });
    else initialize();
})();
