/* [MINI-COMMENT: ASSISTANT.CLIENT]
 * [EN rev.5]
 * [Role] Renders owner chat, separate streamed reasoning and frozen server confirmation cards.
 * [Dependencies] Vanilla DOM/fetch and /api/ai; existing file/CSV APIs retain their own authorization.
 * [Impact] Keeps turn-wide reasoning state, paged owner history, storage notices and persistent stop reasons without trusting model HTML or browser roles.
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

    /** [Role] Builds a safe small Markdown subset using DOM text nodes, without innerHTML/eval/remote media. */
    function markdown(target, value) {
        const doc = target.ownerDocument;
        const fragment = doc.createDocumentFragment();
        let code = null;
        for (const line of value.split('\n')) {
            if (line.startsWith('```')) {
                if (code) { fragment.append(code); code = null; }
                else code = doc.createElement('pre');
                continue;
            }
            if (code) { code.append(doc.createTextNode(line + '\n')); continue; }
            const heading = /^(#{1,4})\s+(.+)$/.exec(line);
            const bullet = /^\s*(?:[-*]|\d+\.)\s+(.+)$/.exec(line);
            const block = doc.createElement(heading ? 'h3' : bullet ? 'li' : 'p');
            const source = heading ? heading[2] : bullet ? bullet[1] : line;
            for (const part of source.split(/(\*\*[^*\n]+\*\*|\[[^\]\n]{1,200}\]\(\/[^\s)\n]{1,200}\))/g)) {
                const link = /^\[([^\]]+)\]\((\/[^)]+)\)$/.exec(part);
                if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
                    const strong = doc.createElement('strong'); strong.textContent = part.slice(2, -2); block.append(strong);
                } else if (link && /^(?:\/api\/ai\/equipment\/[1-9]\d*\/files\/[1-9]\d*\/download|\/api\/ai\/csv\/export\?scope=(?:my|public)|\/(?:my_equipment|public_equipment|my_approvals|mypage))$/.test(link[2])) {
                    const anchor = doc.createElement('a'); anchor.href = link[2]; anchor.textContent = link[1]; block.append(anchor);
                } else block.append(doc.createTextNode(part || ''));
            }
            fragment.append(block);
        }
        if (code) fragment.append(code);
        target.replaceChildren(fragment);
    }

    if (typeof module !== 'undefined' && module.exports) module.exports = { mergeStream, markdown };
    if (typeof document === 'undefined') return;

    /** [Role] Initializes this standalone screen, preserving drafts/details/scroll across incremental polling. */
    async function initialize() {
        const root = document.getElementById('equipment-ai');
        if (!root) return;
        const $ = id => document.getElementById(id);
        const csrf = root.dataset.csrf;
        const nodes = new Map(), streams = new Map(), cards = new Map();
        const history = new Map();
        const terminal = new Set(['done', 'failed', 'cancelled', 'waiting_confirmation']);
        let conversation = null, activeJob = null, timer = null, disposed = false, polling = false;
        let selection = 0, requestKey = null, csvToken = null, retryDelay = 1500, accountContext = null, identityTimer = null, checkingIdentity = false;
        let historyCursor = null, historyExtended = false, nextBefore = null, loadingHistory = false;
        let modelChoices = [], modelId = null, defaultModel = null, modelRevision = 0, modelUnavailable = false, changingModel = false, openingConversation = false, unattributedSelection = false, capabilities = null;
        const controller = new AbortController();
        const labels = { equipment_create: '내 장비 등록', equipment_update: '내 장비 정보 수정', equipment_status: '내 장비 상태 변경',
            catalog_request: '카탈로그 등록 신청', option_request: '옵션 등록 신청', preferences: '내 설정 변경', csv_export: 'CSV 내보내기' };
        const fields = { equipment_id: '장비 번호', name: '장비 이름', option_id: '옵션 번호', serial_number: '시리얼 번호', purchase_date: '구입일',
            warranty_end_date: '보증 종료일', replacement_due_date: '교체 예정일', memo: '메모', is_public: '공개 여부', is_draft: '임시저장',
            status: '상태', reason: '변경 사유', kind: '신청 종류', category_id: '카테고리 번호', manufacturer_id: '제조사 번호', parent_id: '상위 노드 번호',
            lineup_node_id: '모델 노드 번호', option_name: '옵션 이름', specs: '사양', theme: '테마', layout_skin: '화면 구성', deadline_email_opt_in: '기한 알림 수신', scope: '조회 범위' };

        /** [Role] Shows safe server feedback, never embedding an exception/model message as HTML. */
        function notice(message = '') { $('ai-notice').textContent = message; $('ai-notice').hidden = !message; }

        /** [Role] Renders only published opaque choices and restores conversation-specific supported reasoning.
         * [Dependencies] Safe server projections; no provider URL/key/raw metadata reaches this screen.
         * [Impact] A saved unavailable model remains visibly unavailable instead of being silently replaced.
         */
        function modelControls(restoredLevel) {
            if (disposed) return;
            restoredLevel ??= $('ai-level').value;
            const fragment = document.createDocumentFragment();
            for (const model of modelChoices) {
                const option = document.createElement('option'); option.value = model.id;
                option.textContent = `${model.provider} / ${model.label}${!model.available ? ' · 사용 불가' : model.tools ? ' · 장비 업무 가능' : ' · 대화 전용'}`;
                option.disabled = !model.available; fragment.append(option);
            }
            const model = modelChoices.find(item => item.id === modelId);
            if (modelId && !model) {
                const missing = document.createElement('option'); missing.value = modelId; missing.textContent = '이 대화의 이전 모델 · 다시 선택 필요'; missing.disabled = true; fragment.append(missing);
            }
            $('ai-model').replaceChildren(fragment); $('ai-model').value = modelId || '';
            const levels = model && model.available ? model.levels || [] : [];
            const options = document.createDocumentFragment();
            if (!levels.length) {
                const option = document.createElement('option'); option.value = 'default'; option.textContent = '모델 기본값'; options.append(option);
                restoredLevel = 'default';
            }
            for (const level of reasoningLevels) {
                const option = document.createElement('option'); option.value = level;
                option.disabled = !levels.includes(level);
                const reason = model && model.level_reasons && model.level_reasons[level] || '사용 불가';
                option.textContent = level + (option.disabled ? ` · ${reason}` : ''); options.append(option);
            }
            $('ai-level').replaceChildren(options); $('ai-level').value = restoredLevel;
            modelUnavailable = !model || !model.available || (levels.length ? !levels.includes($('ai-level').value) : $('ai-level').value !== 'default');
            $('ai-level').disabled = !levels.length || changingModel || openingConversation;
            $('ai-level-help').textContent = reasoningHelp[$('ai-level').value] || '지원하며 허용된 추론 수준을 선택해 주세요.';
            $('ai-model').disabled = changingModel || openingConversation;
            $('ai-model-caption').textContent = model ? `${model.provider} / ${model.label}` : '사용 가능한 모델 없음';
            $('ai-model-status').textContent = modelUnavailable ? model && model.reason || '이 대화의 모델/추론 설정을 복원할 수 없습니다. 모델과 지원 추론을 다시 선택해 주세요.' :
                `${model.tools ? '장비 업무 가능' : '대화 전용 · 장비 업무는 지원 모델 또는 수동 화면을 이용해 주세요.'}${activeJob ? ' · 변경은 다음 요청부터 적용됩니다. 접수된 요청은 기존 모델을 사용합니다.' : ''}`;
            if (unattributedSelection) $('ai-model-status').textContent += ' · 이전 모델 기록이 없습니다. 표시한 기본 모델은 다음 요청에 적용됩니다.';
            if (capabilities) root.querySelectorAll('[data-tool]').forEach(button => {
                button.hidden = !model || !model.tools || !(capabilities.tools || []).includes(button.dataset.tool) || button.dataset.write && !capabilities.writes || button.dataset.own === 'true' && !(capabilities.scopes || []).includes('my');
            });
            $('ai-send').disabled = modelUnavailable || changingModel || openingConversation || Boolean(activeJob);
        }

        /** [Role] Refreshes backend inventory while keeping an existing saved choice intact.
         * [Dependencies] Sanitized same-origin models API and current conversation selection.
         * [Impact] Inventory changes never silently replace a saved unavailable model.
         */
        async function loadModels() {
            const result = await api('/api/ai/models'); modelChoices = result.models; defaultModel = result.default_model;
            if (!modelId) { modelId = result.default_model; const model = modelChoices.find(item => item.id === modelId); modelControls(initialLevel(model)); }
            else modelControls();
        }

        /** [Role] Persists next-turn selection with optimistic concurrency; an in-flight request is unaffected. */
        async function saveSelection() {
            requestKey = null;
            if (!conversation) { modelControls(); return; }
            changingModel = true; $('ai-model').disabled = true; $('ai-send').disabled = true;
            try {
                const result = await api(`/api/ai/conversations/${conversation}/selection`, { method: 'POST', data: { selection_id: modelId, level: $('ai-level').value, revision: modelRevision, reasoning_version: 2 } });
                modelRevision = result.revision;
                unattributedSelection = false;
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
            const response = await fetch(path, { method, headers, body: form || (data === undefined ? undefined : JSON.stringify(data)),
                credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal });
            const context = response.headers.get('X-Assistant-Account');
            if (response.status === 401 || response.status === 403 && method === 'GET' && !context || context && accountContext && context !== accountContext) {
                disposed = true; clearTimeout(timer); nodes.clear(); streams.clear(); cards.clear(); root.replaceChildren();
                window.location.assign(response.status === 401 ? '/login' : response.status === 403 ? '/portal' : '/assistant');
                throw new Error('로그인 상태가 변경되었습니다.');
            }
            if (context) accountContext = context;
            let result;
            try { result = await response.json(); } catch (_) { throw new Error('응답을 읽을 수 없습니다. 연결 상태를 확인해 주세요.'); }
            if (!response.ok || result.success === false || result.error && result.success !== true) throw new Error(result.message || result.error || '요청을 처리하지 못했습니다.');
            return result;
        }

        /** [Role] Follows new output only when the reader is already near the bottom. */
        function follow(action) {
            const pane = $('ai-scroll');
            const near = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 100;
            action();
            if (near) pane.scrollTop = pane.scrollHeight;
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
         * [EN rev.1]
         * [Role] Renders server proposals with operation-specific field labels; confirms only an opaque ID.
         * [Dependencies] Frozen payload kind and the server-owned operation, never model HTML.
         * [Impact] Catalog names cannot be mislabeled as equipment; confirmation authority remains unchanged.
         */
        function proposalCard(proposal) {
            const previous = cards.get(proposal.id);
            const version = proposal.state + (proposal.result || '');
            if (previous && previous.version === version) return;
            const card = previous?.element || document.createElement('section'); card.className = 'ai-proposal';
            const title = document.createElement('h3'); title.textContent = labels[proposal.operation] || '작업 내용 확인';
            const note = document.createElement('p');
            const applied = proposal.state === 'applied';
            note.textContent = applied ? '장비관리 서버에서 처리한 실제 결과입니다.' : proposal.state === 'pending' ? '아직 적용되지 않았습니다. 내용을 확인한 뒤 실행해 주세요.' : proposal.state === 'superseded' ? '수정한 새 확인 카드로 대체되었습니다. 이 항목은 실행할 수 없습니다.' : '확인 기한이 만료되었거나 취소된 항목입니다. 새로 요청해 주세요.';
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
                if (/^\/api\/ai\/csv\/export\?scope=(my|public)$/.test(result.download_url || '')) {
                    const link = document.createElement('a'); link.href = result.download_url; link.className = 'ai-button'; link.textContent = 'CSV 다운로드'; card.append(link);
                }
            } else if (proposal.state === 'pending') {
                const execute = document.createElement('button'); execute.type = 'button'; execute.className = 'ai-confirm'; execute.textContent = '이 내용으로 실행';
                execute.disabled = proposal.expires * 1000 < Date.now();
                execute.addEventListener('click', async () => {
                    const selected = selection;
                    execute.disabled = true; notice();
                    try {
                        const result = await api(`/api/ai/proposals/${proposal.id}/confirm`, { method: 'POST', data: {} });
                        if (selected === selection) proposalCard({ ...proposal, state: 'applied', result: JSON.stringify(result.result) });
                    } catch (error) { if (selected === selection) notice(error.message); execute.disabled = false; }
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
            $('ai-send').disabled = busy || modelUnavailable || changingModel || openingConversation;
            $('ai-input').disabled = false;
            $('ai-progress').querySelector('.ai-pulse').hidden = !['queued','running'].includes(job.state);
        }

        /** [Role] Pages owner conversation titles and retains already loaded older entries.
         * [Dependencies] Server next_cursor and a cache cleared with the authenticated account context.
         * [Impact] Refreshing the selected chat cannot hide an older page the user already loaded.
         */
        async function conversations(more = false) {
            const cursor = more ? historyCursor : null;
            if (more && !cursor) return [];
            const result = await api('/api/ai/conversations' + (cursor ? '?cursor=' + encodeURIComponent(cursor) : ''));
            for (const item of result.conversations) history.set(item.id, item);
            if (more || !historyExtended) historyCursor = result.next_cursor || null;
            if (more) historyExtended = true;
            const fragment = document.createDocumentFragment();
            for (const item of [...history.values()].sort((a,b) => (b.updated || 0) - (a.updated || 0) || b.id.localeCompare(a.id))) {
                const button = document.createElement('button'); button.type = 'button'; button.className = 'ai-conversation';
                button.textContent = item.title; button.title = item.title; button.setAttribute('aria-current', String(item.id === conversation));
                button.addEventListener('click', () => open(item.id).catch(error => notice(error.message))); fragment.append(button);
            }
            $('ai-conversations').replaceChildren(fragment);
            $('ai-more-conversations').hidden = !historyCursor;
            return result.conversations;
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
                const result = await api(`/api/ai/conversations/${cid}/messages?before=${nextBefore}`);
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

        /** [Role] Changes conversation without leaking cached messages or allowing a stale poll to repopulate it. */
        async function open(cid) {
            const selected = ++selection; clearTimeout(timer); activeJob = null; nextBefore = null;
            openingConversation = true; root.setAttribute('aria-busy', 'true'); modelControls();
            try {
            $('ai-more-messages').hidden = true;
            const result = await api(`/api/ai/conversations/${cid}/messages`);
            if (selected !== selection || disposed) return;
            conversation = cid; nodes.clear(); streams.clear(); cards.clear(); requestKey = null;
            unattributedSelection = !result.conversation.selection_id;
            modelId = result.conversation.selection_id || defaultModel;
            modelRevision = result.conversation.selection_revision || 0;
            modelControls(result.conversation.next_level || 'medium');
            nextBefore = result.next_before; $('ai-more-messages').hidden = !nextBefore; storageNotice(result.storage);
            $('ai-messages').replaceChildren(); $('ai-proposals').replaceChildren(); $('ai-title').textContent = result.conversation.title;
            $('ai-welcome').hidden = Boolean(result.messages.length); $('ai-progress').hidden = true; $('ai-send').disabled = false;
            for (const message of result.messages) hydrate(message);
            for (const item of result.proposals) proposalCard(item);
            const job = result.jobs.find(item => !terminal.has(item.state));
            for (const item of result.jobs) {
                const stream = streams.get(item.id);
                if (stream) stream.generation = item.steps + (['running','draining','recovery_required'].includes(item.state) ? 1 : 0);
                if (stream) stream.answerStarted ||= Boolean(item.answer_started);
                if (stream) sourceLabel(stream.messageId, item.source);
                if (stream && stream.reasoning && !stream.answerStarted && ['running','draining'].includes(item.state)) nodes.get(stream.messageId).details.open = true;
            }
            if (job) { activeJob = job.id; progress(job); schedule(100); }
            else if (result.jobs[0]) progress(result.jobs[0]);
            modelControls(result.conversation.next_level || 'medium');
            $('ai-scroll').scrollTop = $('ai-scroll').scrollHeight;
            $('ai-sidebar').classList.remove('is-open'); $('ai-menu-toggle').setAttribute('aria-expanded', 'false');
            await conversations();
            } finally {
                if (selected === selection) { openingConversation = false; root.setAttribute('aria-busy', 'false'); modelControls(); }
            }
        }

        /** [Role] Schedules at most one poll; hidden tabs back off and terminal jobs stop polling. */
        function schedule(delay = 1500) { clearTimeout(timer); if (!disposed && activeJob) timer = setTimeout(poll, document.hidden ? Math.max(5000, delay) : delay); }

        /** [MINI-COMMENT: ASSISTANT.CLIENT.STREAM]
         * [EN rev.2]
         * [Role] Applies separate deltas while preserving user-opened thoughts and scroll.
         * [Dependencies] Server generation/code-point cursors.
         * [Impact] Automatic close occurs once per turn; later reasoning and manual reopening survive tool steps.
         */
        async function poll() {
            if (polling || !activeJob || disposed) { schedule(); return; }
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
                    if (next.content !== node.content) { markdown(node.answer, next.content); node.content = next.content; }
                    sourceLabel(result.message_id, result.source);
                    for (const item of result.proposals) proposalCard(item);
                });
                progress(result); retryDelay = 1500;
                if (terminal.has(result.state) && next.r >= result.reasoning_length && next.c >= result.content_length) { activeJob = null; modelControls(); }
                else schedule(next.r < result.reasoning_length || next.c < result.content_length ? 100 : 1500);
            } catch (error) {
                if (!disposed && selected === selection) { notice(error.message); retryDelay = Math.min(retryDelay * 2, 15000); schedule(retryDelay); }
            } finally { polling = false; }
        }

        /** [Role] Creates a new account-local conversation only on explicit user intent. */
        async function newConversation() { const result = await api('/api/ai/conversations', { method: 'POST', data: {} }); await open(result.id); $('ai-input').focus(); }

        /** [Role] Revalidates idle/returning screens too, so a different login cannot retain a prior account's DOM. */
        async function checkIdentity() {
            if (disposed || checkingIdentity || document.hidden) return;
            checkingIdentity = true;
            try { const result = await api('/api/ai/capabilities'); storageNotice(result.storage); }
            catch (error) { if (!disposed) notice(error.message); }
            finally { checkingIdentity = false; }
        }

        $('ai-new').addEventListener('click', () => newConversation().catch(error => notice(error.message)));
        $('ai-more-conversations').addEventListener('click', async () => {
            $('ai-more-conversations').disabled = true;
            try { await conversations(true); } catch (error) { notice(error.message); }
            finally { $('ai-more-conversations').disabled = false; }
        });
        $('ai-more-messages').addEventListener('click', () => olderMessages().catch(error => notice(error.message)));
        $('ai-menu-toggle').addEventListener('click', () => { const show = $('ai-sidebar').classList.toggle('is-open'); $('ai-menu-toggle').setAttribute('aria-expanded', String(show)); });
        $('ai-input').addEventListener('input', () => { requestKey = null; $('ai-input').style.height = 'auto'; $('ai-input').style.height = Math.min($('ai-input').scrollHeight, 160) + 'px'; });
        $('ai-level').addEventListener('change', () => { requestKey = null; $('ai-level-help').textContent = reasoningHelp[$('ai-level').value] || ''; saveSelection().catch(error => { modelUnavailable = true; $('ai-send').disabled = true; notice(error.message); }); });
        $('ai-model').addEventListener('change', () => { if (openingConversation || changingModel) return; modelId = $('ai-model').value; const model = modelChoices.find(item => item.id === modelId); modelControls(initialLevel(model)); saveSelection().catch(error => { modelUnavailable = true; $('ai-send').disabled = true; notice(error.message); }); });
        $('ai-model-refresh').addEventListener('click', () => loadModels().catch(error => notice(error.message)));
        $('ai-input').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!$('ai-send').disabled) $('ai-form').requestSubmit(); } });
        root.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => { $('ai-input').value = button.dataset.prompt; requestKey = null; $('ai-input').focus(); }));
        $('ai-form').addEventListener('submit', async event => {
            event.preventDefault(); if ($('ai-send').disabled) return;
            const content = $('ai-input').value.trim(); if (!content) return;
            $('ai-send').disabled = true; notice();
            try {
                if (!conversation) { const result = await api('/api/ai/conversations', { method: 'POST', data: {} }); conversation = result.id; modelRevision = result.selection_revision || 1; await saveSelection(); }
                requestKey ||= crypto.randomUUID().replaceAll('-', '');
                await api(`/api/ai/conversations/${conversation}/turns`, { method: 'POST', data: { content, level: $('ai-level').value, client_key: requestKey, selection_id: modelId, reasoning_version: 2 } });
                $('ai-input').value = ''; requestKey = null; await open(conversation);
            } catch (error) { notice(error.message); $('ai-send').disabled = false; }
        });
        $('ai-cancel').addEventListener('click', async () => { if (!activeJob) return; try { await api(`/api/ai/jobs/${activeJob}/cancel`, { method: 'POST', data: {} }); schedule(50); } catch (error) { notice(error.message); } });

        /** [Role] Sends only a user-selected file to the existing own-equipment attachment endpoint. */
        $('ai-upload-form').addEventListener('submit', async event => {
            event.preventDefault(); const id = Number($('ai-upload-equipment').value), file = $('ai-upload-file').files[0];
            if (!Number.isSafeInteger(id) || id < 1 || !file || file.size > 10 * 1024 * 1024) { notice('장비 번호와 10MiB 이하 파일을 선택해 주세요.'); return; }
            const form = new FormData(); form.append('file', file); const button = event.currentTarget.querySelector('button'); button.disabled = true;
            try { await api(`/api/ai/equipment/${id}/files`, { method: 'POST', form }); notice('선택한 파일이 첨부되었습니다.'); $('ai-upload-file').value = ''; } catch (error) { notice(error.message); } finally { button.disabled = false; }
        });
        /** [Role] Reuses the existing authenticated CSV preview token, never asks the model to parse a raw file. */
        $('ai-csv-form').addEventListener('submit', async event => {
            event.preventDefault(); csvToken = null; $('ai-csv-confirm').hidden = true;
            const file = $('ai-csv-file').files[0]; if (!file || file.size > 1024 * 1024) { notice('1MiB 이하 CSV 파일을 선택해 주세요.'); return; }
            const form = new FormData(); form.append('file', file);
            try { const result = await api('/api/ai/csv/preview', { method: 'POST', form });
                $('ai-csv-preview').textContent = csvPreviewText(result);
                $('ai-csv-preview').hidden = false; csvToken = result.token; $('ai-csv-confirm').hidden = !csvToken;
            } catch (error) { notice(error.message); }
        });
        $('ai-csv-file').addEventListener('change', () => { csvToken = null; $('ai-csv-confirm').hidden = true; $('ai-csv-preview').hidden = true; });
        $('ai-csv-confirm').addEventListener('click', async () => {
            if (!csvToken) return; $('ai-csv-confirm').disabled = true;
            try { const result = await api('/api/ai/csv/commit', { method: 'POST', data: { token: csvToken } }); notice(`${result.count}개 장비가 등록되었습니다.`); csvToken = null; $('ai-csv-confirm').hidden = true; }
            catch (error) { notice(error.message); } finally { $('ai-csv-confirm').disabled = false; }
        });

        window.addEventListener('pagehide', () => { disposed = true; clearTimeout(timer); clearInterval(identityTimer); controller.abort(); }, { once: true });
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
            root.querySelector('.ai-file-tools').hidden = !capabilities.file_tools;
            if (!capabilities.writes) notice('현재 조회와 대화 기능을 사용할 수 있습니다. 변경 제안은 운영 설정에서 비활성 상태입니다.');
            await loadModels();
            const list = await conversations(); if (list.length) await open(list[0].id);
            identityTimer = setInterval(checkIdentity, 10000);
        } catch (error) { notice(error.message); $('ai-send').disabled = true; }
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true });
    else initialize();
})();
